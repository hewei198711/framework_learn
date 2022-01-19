import base64
import json
import os
import sys
import urllib.parse as urlparse
from typing import Text

from httprunner.compat import ensure_path_sep
from loguru import logger
from sentry_sdk import capture_exception

from httprunner.ext.har2case import utils
from httprunner.make import make_testcase, format_pytest_with_black

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

# 确保har的路径正确
def ensure_file_path(path: Text) -> Text:
    # 如果路径不正确或者不是har文件，则报错
    if not path or not path.endswith(".har"):
        logger.error("HAR file not specified.")
        sys.exit(1)
    # 确保linux和windows的不同路径分隔符兼容，并判断是否是图片
    path = ensure_path_sep(path)
    if not os.path.isfile(path):
        logger.error(f"HAR file not exists: {path}")
        sys.exit(1)
    # 判断是否是绝对路径，不是则加上当前路径
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)

    return path

# Har文件解析器
class HarParser(object):
    def __init__(self, har_file_path, filter_str=None, exclude_str=None):
        self.har_file_path = ensure_file_path(har_file_path)
        self.filter_str = filter_str
        self.exclude_str = exclude_str or ""

    # 解析har的entry，并生成setstep的url和params
    def __make_request_url(self, teststep_dict, entry_json):
        """ parse HAR entry request url and queryString, and make teststep url and params

        Args:
            entry_json (dict):
                {
                    "request": {
                        "url": "https://httprunner.top/home?v=1&w=2",
                        "queryString": [
                            {"name": "v", "value": "1"},
                            {"name": "w", "value": "2"}
                        ],
                    },
                    "response": {}
                }

        Returns:
            {
                "name: "/home",
                "request": {
                    url: "https://httprunner.top/home",
                    params: {"v": "1", "w": "2"}
                }
            }

        """
        # 获取请求的params
        request_params = utils.convert_list_to_dict(
            entry_json["request"].get("queryString", [])
        )

        # 获取请求的url
        url = entry_json["request"].get("url")
        # url不存在则提示“请求中缺少url”
        if not url:
            logger.exception("url missed in request.")
            sys.exit(1)
        # 解析url成一个对象
        parsed_object = urlparse.urlparse(url)
        if request_params:
            # 把对象里的query设置为空
            parsed_object = parsed_object._replace(query="")
            # 重新获取url，并保存到teststep_dict中
            teststep_dict["request"]["url"] = parsed_object.geturl()
            # 获取params，并保存到teststep_dict中
            teststep_dict["request"]["params"] = request_params
        else:
            # 保存无参数的url
            teststep_dict["request"]["url"] = url
        # 接口名字为请求url
        teststep_dict["name"] = parsed_object.path

    # 解析har的entry，并生成teststep的method
    def __make_request_method(self, teststep_dict, entry_json):
        """ parse HAR entry request method, and make teststep method.
        """
        method = entry_json["request"].get("method")
        # 判断是否有请求方式
        if not method:
            logger.exception("method missed in request.")
            sys.exit(1)

        teststep_dict["request"]["method"] = method

    # 解析har的entry，并生成teststep的cookies
    def __make_request_cookies(self, teststep_dict, entry_json):
        cookies = {}
        # 遍历kooies，并name--value进行保存
        for cookie in entry_json["request"].get("cookies", []):
            cookies[cookie["name"]] = cookie["value"]

        # 判断cookies是否为空
        if cookies:
            teststep_dict["request"]["cookies"] = cookies

    # 解析HAR的entry请求头，并生成teststep头。忽略\u请求\u标头中的标头将被忽略。
    def __make_request_headers(self, teststep_dict, entry_json):
        """ parse HAR entry request headers, and make teststep headers.
            header in IGNORE_REQUEST_HEADERS will be ignored.

        Args:
            entry_json (dict):
                {
                    "request": {
                        "headers": [
                            {"name": "Host", "value": "httprunner.top"},
                            {"name": "Content-Type", "value": "application/json"},
                            {"name": "User-Agent", "value": "iOS/10.3"}
                        ],
                    },
                    "response": {}
                }

        Returns:
            {
                "request": {
                    headers: {"Content-Type": "application/json"}
            }

        """
        teststep_headers = {}
        for header in entry_json["request"].get("headers", []):
            if header["name"] == "cookie" or header["name"].startswith(":"):
                continue

            teststep_headers[header["name"]] = header["value"]

        if teststep_headers:
            teststep_dict["request"]["headers"] = teststep_headers

    # 解析HAR的 entry请求数据，并生成teststep请求数据data
    def _make_request_data(self, teststep_dict, entry_json):
        """ parse HAR entry request data, and make teststep request data

        Args:
            entry_json (dict):
                {
                    "request": {
                        "method": "POST",
                        "postData": {
                            "mimeType": "application/x-www-form-urlencoded; charset=utf-8",
                            "params": [
                                {"name": "a", "value": 1},
                                {"name": "b", "value": "2"},
                                ]
                            }
                        },
                    },
                    "response": {...}
                }


        Returns:
            {
                "request": {
                    "method": "POST",
                    "data": {"v": "1", "w": "2"}
                }
            }

        """
        method = entry_json["request"].get("method")
        # 判断请求方式
        if method in ["POST", "PUT", "PATCH"]:
            postData = entry_json["request"].get("postData", {})
            # 获取请求参数格式
            mimeType = postData.get("mimeType")

            # Note that text and params fields are mutually exclusive.
            # 如果是 text类型，text类型与params类型是互斥的
            if "text" in postData:
                post_data = postData.get("text")
            else:
                # 获取请求的params
                params = postData.get("params", [])
                # 转化为字典格式
                post_data = utils.convert_list_to_dict(params)

            request_data_key = "data"
            # 如果为空
            if not mimeType:
                pass
            # 如果请求是json请求
            elif mimeType.startswith("application/json"):
                # 转换为json
                try:
                    post_data = json.loads(post_data)
                    request_data_key = "json"
                except JSONDecodeError:
                    pass
            elif mimeType.startswith("application/x-www-form-urlencoded"):
                # 将application/x-www-form-urlencoded格式转为字典，将a=1&b=2 转化为{'a':'1','b':'2'}
                post_data = utils.convert_x_www_form_urlencoded_to_dict(post_data)
            else:
                # TODO: make compatible with more mimeType
                pass
            # 保存请求体data
            teststep_dict["request"][request_data_key] = post_data

    # 解析HAR条目响应并进行teststep的断言
    def _make_validate(self, teststep_dict, entry_json):
        """ parse HAR entry response and make teststep validate.

        Args:
            entry_json (dict):
                {
                    "request": {},
                    "response": {
                        "status": 200,
                        "headers": [
                            {
                                "name": "Content-Type",
                                "value": "application/json; charset=utf-8"
                            },
                        ],
                        "content": {
                            "size": 71,
                            "mimeType": "application/json; charset=utf-8",
                            "text": "eyJJc1N1Y2Nlc3MiOnRydWUsIkNvZGUiOjIwMCwiTWVzc2FnZSI6bnVsbCwiVmFsdWUiOnsiQmxuUmVzdWx0Ijp0cnVlfX0=",
                            "encoding": "base64"
                        }
                    }
                }

        Returns:
            {
                "validate": [
                    {"eq": ["status_code", 200]}
                ]
            }

        """
        # 获取响应状态码，并存入断言中
        teststep_dict["validate"].append(
            {"eq": ["status_code", entry_json["response"].get("status")]}
        )

        # 获取响应体
        resp_content_dict = entry_json["response"].get("content")

        # 将请求头的参数转化为字典
        headers_mapping = utils.convert_list_to_dict(
            entry_json["response"].get("headers", [])
        )

        # 如果返回了Content-Type值
        if "Content-Type" in headers_mapping:
            # 断言中加入Content-Type的断言
            teststep_dict["validate"].append(
                {"eq": ["headers.Content-Type", headers_mapping["Content-Type"]]}
            )

        text = resp_content_dict.get("text")
        # 如果响应体里text为空（表示body为空），则返回
        if not text:
            return
        # 获取响应类型
        mime_type = resp_content_dict.get("mimeType")
        if mime_type and mime_type.startswith("application/json"):

            # 获取返回编码类型
            encoding = resp_content_dict.get("encoding")
            if encoding and encoding == "base64":
                # base64解码
                content = base64.b64decode(text)
                try:
                    # utf-8解码
                    content = content.decode("utf-8")
                except UnicodeDecodeError:
                    logger.warning(f"failed to decode base64 content with utf-8 !")
                    return
            else:
                content = text

            try:
                # 转为字典格式
                resp_content_json = json.loads(content)
            except JSONDecodeError:
                logger.warning(f"response content can not be loaded as json: {content}")
                return
            # 如果resp_content_json不是字典格式
            if not isinstance(resp_content_json, dict):
                # e.g. ['a', 'b']
                return
            # 遍历字典
            for key, value in resp_content_json.items():
                # 判断是否是嵌套字典
                if isinstance(value, (dict, list)):
                    continue
                # 把body里非字典的值加入断言
                teststep_dict["validate"].append({"eq": ["body.{}".format(key), value]})

    # 从extract中提取请求到teststep中
    def _prepare_teststep(self, entry_json):
        """ extract info from entry dict and make teststep

        Args:
            entry_json (dict):
                {
                    "request": {
                        "method": "POST",
                        "url": "https://httprunner.top/api/v1/Account/Login",
                        "headers": [],
                        "queryString": [],
                        "postData": {},
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "content": {}
                    }
                }

        """
        # 初始teststep_dict的结构
        teststep_dict = {"name": "", "request": {}, "validate": []}
        # 获取url
        self.__make_request_url(teststep_dict, entry_json)
        # 获取请求方式
        self.__make_request_method(teststep_dict, entry_json)
        # 获取请求cookies
        self.__make_request_cookies(teststep_dict, entry_json)
        # 获取请求头
        self.__make_request_headers(teststep_dict, entry_json)
        # 获取请求数据
        self._make_request_data(teststep_dict, entry_json)
        # 获取响应的断言
        self._make_validate(teststep_dict, entry_json)

        return teststep_dict

    # 测试用例的配置提取
    def _prepare_config(self):
        """ prepare config block.
        """
        return {"name": "testcase description", "variables": {}, "verify": False}

    # 准备测试用例的，测试步骤从har中解析出来
    def _prepare_teststeps(self):
        """ make teststep list.
            teststeps list are parsed from HAR log entries list.

        """

        def is_exclude(url, exclude_str):
            exclude_str_list = exclude_str.split("|")
            for exclude_str in exclude_str_list:
                if exclude_str and exclude_str in url:
                    return True

            return False

        teststeps = []
        # 获取har文件，log下的entries列表
        log_entries = utils.load_har_log_entries(self.har_file_path)
        # 遍历log_entries，并解析
        for entry_json in log_entries:
            # 获取url
            url = entry_json["request"].get("url")
            # 判断初始链接filter_str不为空，且初始链接filter_str不在url内
            if self.filter_str and self.filter_str not in url:
                continue
            # 判断url是否被排除列表中
            if is_exclude(url, self.exclude_str):
                continue
            # 把api添加到测试步骤中
            teststeps.append(self._prepare_teststep(entry_json))

        return teststeps
    # 将har文件内容提取，准备给测试用例
    def _make_testcase(self):
        """ Extract info from HAR file and prepare for testcase
        """
        logger.info("Extract info from HAR file and prepare for testcase.")

        config = self._prepare_config()
        teststeps = self._prepare_teststeps()
        # 组成测试用例的字典格式
        testcase = {"config": config, "teststeps": teststeps}
        return testcase

    # 生成测试用例
    def gen_testcase(self, file_type="pytest"):
        logger.info(f"Start to generate testcase from {self.har_file_path}")
        # 获取har文件
        harfile = os.path.splitext(self.har_file_path)[0]
        # 生成测试用例，失败报错
        try:
            testcase = self._make_testcase()
        except Exception as ex:
            capture_exception(ex)
            raise
        # 判断文件类型，并生成对应文件
        if file_type == "JSON":
            # 生成 json格式的测试用例
            output_testcase_file = f"{harfile}.json"
            utils.dump_json(testcase, output_testcase_file)
        elif file_type == "YAML":
            # 生成 yaml格式的测试用例
            output_testcase_file = f"{harfile}.yml"
            utils.dump_yaml(testcase, output_testcase_file)
        else:
            # 默认生成pytest文件 default to generate pytest file
            # 把路径放入testcase，便于后面生成py文件
            testcase["config"]["path"] = self.har_file_path
            # 将有效的testcase dict转换为pytest文件路径
            output_testcase_file = make_testcase(testcase)
            # 将_pytest_格式化为黑色
            format_pytest_with_black(output_testcase_file)

        logger.info(f"generated testcase: {output_testcase_file}")
