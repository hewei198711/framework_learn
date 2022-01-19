import json
import time

import requests
import urllib3
from loguru import logger
from requests import Request, Response
from requests.exceptions import (
    InvalidSchema,
    InvalidURL,
    MissingSchema,
    RequestException,
)

from httprunner.models import RequestData, ResponseData
from httprunner.models import SessionData, ReqRespData
from httprunner.utils import lower_dict_keys, omit_long_data

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Api响应
class ApiResponse(Response):
    def raise_for_status(self):
        if hasattr(self, "error") and self.error:
            raise self.error
        Response.raise_for_status(self)

# 从response（）对象获取请求和响应信息。
def get_req_resp_record(resp_obj: Response) -> ReqRespData:
    """ get request and response info from Response() object.
    """

    def log_print(req_or_resp, r_type):
        msg = f"\n================== {r_type} details ==================\n"
        for key, value in req_or_resp.dict().items():
            if isinstance(value, dict) or isinstance(value, list):
                value = json.dumps(value, indent=4, ensure_ascii=False)

            msg += "{:<8} : {}\n".format(key, value)
        logger.debug(msg)

    # record actual request info
    # 记录实际请求信息
    # 获取请求头成字典
    request_headers = dict(resp_obj.request.headers)
    # 获取请求cookies
    request_cookies = resp_obj.request._cookies.get_dict()
    # 获取请求body
    request_body = resp_obj.request.body
    if request_body is not None:
        try:
            # 请求体转换为字典
            request_body = json.loads(request_body)
        except json.JSONDecodeError:
            # str: a=1&b=2
            pass
        except UnicodeDecodeError:
            # bytes/bytearray: request body in protobuf
            pass
        except TypeError:
            # neither str nor bytes/bytearray, e.g. <MultipartEncoder>
            pass
        # # 将dict中的键转换为小写,获取请求类型
        request_content_type = lower_dict_keys(request_headers).get("content-type")
        if request_content_type and "multipart/form-data" in request_content_type:
            # upload file type 上载文件类型
            request_body = "upload file stream (OMITTED)"
    # 获取请求数据体
    request_data = RequestData(
        method=resp_obj.request.method,
        url=resp_obj.request.url,
        headers=request_headers,
        cookies=request_cookies,
        body=request_body,
    )

    # log request details in debug mode
    # 在调试模式下记录请求详细信息，打印请求信息
    log_print(request_data, "request")

    # record response info
    # 记录响应信息
    # 获取响应头
    resp_headers = dict(resp_obj.headers)
    # 响应头转小写
    lower_resp_headers = lower_dict_keys(resp_headers)
    # 获取响应数据类型
    content_type = lower_resp_headers.get("content-type", "")

    if "image" in content_type:
        # response is image type, record bytes content only
        # 响应为图像类型，仅记录字节内容
        response_body = resp_obj.content
    else:
        try:
            # try to record json data
            # 尝试记录json数据
            response_body = resp_obj.json()
        except ValueError:
            # only record at most 512 text charactors
            resp_text = resp_obj.text
            # 最多只能记录512个文本字符
            response_body = omit_long_data(resp_text)
    # 获取请求信息结构体
    response_data = ResponseData(
        status_code=resp_obj.status_code,
        cookies=resp_obj.cookies or {},
        encoding=resp_obj.encoding,
        headers=resp_headers,
        content_type=content_type,
        body=response_body,
    )

    # log response details in debug mode
    # 在调试模式下记录响应详细信息
    log_print(response_data, "response")
    # 获取请求信息和响应信息
    req_resp_data = ReqRespData(request=request_data, response=response_data)
    return req_resp_data

# 请求会话。
class HttpSession(requests.Session):
    """
    类，用于执行HTTP请求和在请求之间保存（会话）cookies（以便能够登录和注销网站）。
    记录每个请求，以便HttpRunner可以显示统计信息。

    这是` python请求'的稍微扩展版本<http://python-requests.org>`_'s
    ：py:class:`requests.Session`类，而且这个类的工作原理基本相同。
    Class for performing HTTP requests and holding (session-) cookies between requests (in order
    to be able to log in and out of websites). Each request is logged so that HttpRunner can
    display statistics.

    This is a slightly extended version of `python-request <http://python-requests.org>`_'s
    :py:class:`requests.Session` class and mostly this class works exactly the same.
    """

    def __init__(self):
        super(HttpSession, self).__init__()
        # 获取对象，包括请求、响应、验证器和stat数据
        self.data = SessionData()

    # 从response（）对象更新请求和响应信息。
    def update_last_req_resp_record(self, resp_obj):
        """
        update request and response info from Response() object.
        """
        # TODO: fix
        self.data.req_resps.pop()# 请求信息删除最新一个
        # 添加一个新的请求和响应信息
        self.data.req_resps.append(get_req_resp_record(resp_obj))
    # 接口请求方法
    def request(self, method, url, name=None, **kwargs):
        """
        构造并发送一个：py:class:`requests.Request`。
        返回：py:class:`requests.Response`对象。
        Constructs and sends a :py:class:`requests.Request`.
        Returns :py:class:`requests.Response` object.

        :param method:
            请求方法
            method for the new :class:`Request` object.
        :param url:
            请求url
            URL for the new :class:`Request` object.
        :param name: (optional)
            占位符，使其与Lcust's HttpSession兼容
            Placeholder, make compatible with Locust's HttpSession
        :param params: (optional)
            请求参数
            Dictionary or bytes to be sent in the query string for the :class:`Request`.
        :param data: (optional)
            请求data
            Dictionary or bytes to send in the body of the :class:`Request`.
        :param headers: (optional)
            请求头
            Dictionary of HTTP Headers to send with the :class:`Request`.
        :param cookies: (optional)
            请求cookies
            Dict or CookieJar object to send with the :class:`Request`.
        :param files: (optional)
            “文件名”字典：用于多部分编码上载的类似文件的对象。
            Dictionary of ``'filename': file-like-objects`` for multipart encoding upload.
        :param auth: (optional)
            验证元组或可调用以启用基本/摘要/自定义HTTP验证。
            Auth tuple or callable to enable Basic/Digest/Custom HTTP Auth.
        :param timeout: (optional)
            超时时间
            How long to wait for the server to send data before giving up, as a float, or \
            a (`connect timeout, read timeout <user/advanced.html#timeouts>`_) tuple.
            :type timeout: float or tuple
        :param allow_redirects: (optional)
            允许重定向，默认设置为True。
            Set to True by default.
        :type allow_redirects: bool
        :param proxies: (optional)
            字典映射协议到代理的URL。
            Dictionary mapping protocol to the URL of the proxy.
        :param stream: (optional)
            是否立即下载响应内容。默认值为“False”。
            whether to immediately download the response content. Defaults to ``False``.
        :param verify: (optional)
            if ``True``, the SSL cert will be verified. A CA_BUNDLE path can also be provided.
        :param cert: (optional)
            如果“True”，则将验证SSL证书。还可以提供CA_BUNDLE路径。
            if String, path to ssl client cert file (.pem). If Tuple, ('cert', 'key') pair.
        """
        # 获取对象，包括请求、响应、验证器和stat数据
        self.data = SessionData()

        # timeout default to 120 seconds
        # 超时默认为120秒
        kwargs.setdefault("timeout", 120)

        # set stream to True, in order to get client/server IP/Port
        # 将stream设置为True，以获取客户端/服务器IP/端口
        kwargs["stream"] = True
        # 获取开始时间
        start_timestamp = time.time()
        # 发送请求，获取请求响应信息
        response = self._send_request_safe_mode(method, url, **kwargs)
        # 获取响应时间
        response_time_ms = round((time.time() - start_timestamp) * 1000, 2)

        try:
            # 获取客户端ip和端口，并保存
            client_ip, client_port = response.raw.connection.sock.getsockname()
            self.data.address.client_ip = client_ip
            self.data.address.client_port = client_port
            logger.debug(f"client IP: {client_ip}, Port: {client_port}")
        except AttributeError as ex:
            # 无法获取客户端地址信息
            logger.warning(f"failed to get client address info: {ex}")

        try:
            # 获取服务器ip和端口，并保存
            server_ip, server_port = response.raw.connection.sock.getpeername()
            self.data.address.server_ip = server_ip
            self.data.address.server_port = server_port
            logger.debug(f"server IP: {server_ip}, Port: {server_port}")
        except AttributeError as ex:
            # 无法获取服务器地址信息
            logger.warning(f"failed to get server address info: {ex}")

        # get length of the response content 获取响应内容的长度
        content_size = int(dict(response.headers).get("content-length") or 0)

        # record the consumed time 记录消耗的时间
        self.data.stat.response_time_ms = response_time_ms
        self.data.stat.elapsed_ms = response.elapsed.microseconds / 1000.0
        self.data.stat.content_size = content_size

        # record request and response histories, include 30X redirection
        # 记录请求和响应历史记录，包括30X重定向
        response_list = response.history + [response]
        self.data.req_resps = [
            # 从response（）对象获取请求和响应信息。
            get_req_resp_record(resp_obj) for resp_obj in response_list
        ]

        try:
            # 根据请求状态，引发错误
            response.raise_for_status()
        except RequestException as ex:
            logger.error(f"{str(ex)}")
        else:
            logger.info(
                f"status_code: {response.status_code}, "
                f"response_time(ms): {response_time_ms} ms, "
                f"response_length: {content_size} bytes"
            )
        # 返回请求信息
        return response
    # 发送http请求，并捕获由于连接问题可能发生的任何异常。
    def _send_request_safe_mode(self, method, url, **kwargs):
        """
        发送HTTP请求，并捕获由于连接问题可能发生的任何异常。
        安全模式已从请求1.x中删除。
        Send a HTTP request, and catch any exception that might occur due to connection problems.
        Safe mode has been removed from requests 1.x.
        """
        try:
            return requests.Session.request(self, method, url, **kwargs)
        except (MissingSchema, InvalidSchema, InvalidURL):
            raise
        except RequestException as ex:
            resp = ApiResponse()
            resp.error = ex
            resp.status_code = 0  # with this status_code, content returns None
            resp.request = Request(method, url).prepare()
            return resp
