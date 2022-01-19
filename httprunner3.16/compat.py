"""
This module handles compatibility issues between testcase format v2 and v3.
"""
import os
import sys
from typing import List, Dict, Text, Union, Any

from loguru import logger

from httprunner import exceptions
from httprunner.loader import load_project_meta, convert_relative_project_root_dir
from httprunner.parser import parse_data
from httprunner.utils import sort_dict_by_custom_order

# 返回variables的字典格式{"var1": 1,"var2": 2}
def convert_variables(
    raw_variables: Union[Dict, List, Text], test_path: Text
) -> Dict[Text, Any]:
    # 如果已经是字典格式
    if isinstance(raw_variables, Dict):
        return raw_variables
    # 如果是[{"var1": 1}, {"var2": 2}]格式
    if isinstance(raw_variables, List):
        # [{"var1": 1}, {"var2": 2}]
        variables: Dict[Text, Any] = {}
        for var_item in raw_variables:
            if not isinstance(var_item, Dict) or len(var_item) != 1:
                raise exceptions.TestCaseFormatError(
                    f"Invalid variables format: {raw_variables}"
                )

            variables.update(var_item)

        return variables

    elif isinstance(raw_variables, Text):
        # get variables by function, e.g. ${get_variables()}
        # 按函数获取变量，例如${get_variables()}
        project_meta = load_project_meta(test_path)
        # 使用求值变量映射解析原始数据。
        # 注意：变量映射不应包含任何变量或函数。
        variables = parse_data(raw_variables, {}, project_meta.functions)

        return variables

    else:
        raise exceptions.TestCaseFormatError(
            f"Invalid variables format: {raw_variables}"
        )

# 将 content.xx/json.xx 变为 body.xx，headers.Content-Type => headers."Content-Type"
# 将 lst.0.name to lst[0].name
def _convert_jmespath(raw: Text) -> Text:
    if not isinstance(raw, Text):
        raise exceptions.TestCaseFormatError(f"Invalid jmespath extractor: {raw}")

    # content.xx/json.xx => body.xx
    if raw.startswith("content"):
        raw = f"body{raw[len('content'):]}"
    elif raw.startswith("json"):
        raw = f"body{raw[len('json'):]}"

    raw_list = []
    # 遍历list，将 headers.Content-Type => headers."Content-Type"
    # 将 lst.0.name to lst[0].name
    for item in raw.split("."):
        if "-" in item:
            # add quotes for field with separator
            # e.g. headers.Content-Type => headers."Content-Type"
            item = item.strip('"')
            raw_list.append(f'"{item}"')
        # 判断是否是数字
        elif item.isdigit():
            # convert lst.0.name to lst[0].name
            if len(raw_list) == 0:
                logger.error(f"Invalid jmespath: {raw}")
                sys.exit(1)

            last_item = raw_list.pop()
            item = f"{last_item}[{item}]"
            raw_list.append(item)
        else:
            raw_list.append(item)

    return ".".join(raw_list)

# 将提取列表（v2）转换为dict（v3）
# [{"varA": "content.varA"}, {"varB": "json.varB"}]
# =>{"varA": "body.varA", "varB": "body.varB"}
def _convert_extractors(extractors: Union[List, Dict]) -> Dict:
    """ convert extract list(v2) to dict(v3)
        将提取列表（v2）转换为dict（v3）
    Args:
        extractors: [{"varA": "content.varA"}, {"varB": "json.varB"}]

    Returns:
        {"varA": "body.varA", "varB": "body.varB"}

    """
    v3_extractors: Dict = {}

    if isinstance(extractors, List):
        # [{"varA": "content.varA"}, {"varB": "json.varB"}]
        for extractor in extractors:
            if not isinstance(extractor, Dict):
                logger.error(f"Invalid extractor: {extractors}")
                sys.exit(1)
            for k, v in extractor.items():
                v3_extractors[k] = v
    elif isinstance(extractors, Dict):
        # {"varA": "body.varA", "varB": "body.varB"}
        v3_extractors = extractors
    else:
        logger.error(f"Invalid extractor: {extractors}")
        sys.exit(1)

    for k, v in v3_extractors.items():
        v3_extractors[k] = _convert_jmespath(v)

    return v3_extractors

# 断言转化器
def _convert_validators(validators: List) -> List:
    for v in validators:
        if "check" in v and "expect" in v:
            # format1: {"check": "content.abc", "assert": "eq", "expect": 201}
            v["check"] = _convert_jmespath(v["check"])

        elif len(v) == 1:
            # format2: {'eq': ['status_code', 201]}
            comparator = list(v.keys())[0]
            v[comparator][0] = _convert_jmespath(v[comparator][0])

    return validators

# 按自定义进行请求排序
def _sort_request_by_custom_order(request: Dict) -> Dict:
    custom_order = [
        "method",
        "url",
        "params",
        "headers",
        "cookies",
        "data",
        "json",
        "files",
        "timeout",
        "allow_redirects",
        "proxies",
        "verify",
        "stream",
        "auth",
        "cert",
    ]
    return sort_dict_by_custom_order(request, custom_order)

# 按自定义进行请求排序
def _sort_step_by_custom_order(step: Dict) -> Dict:
    custom_order = [
        "name",
        "variables",
        "request",
        "testcase",
        "setup_hooks",
        "teardown_hooks",
        "extract",
        "validate",
        "validate_script",
    ]
    return sort_dict_by_custom_order(step, custom_order)

# 确保步骤连接的方法
def _ensure_step_attachment(step: Dict) -> Dict:
    test_dict = {
        "name": step["name"],
    }

    # 获取variables(全局变量)
    if "variables" in step:
        test_dict["variables"] = step["variables"]

    # 获取setup_hooks（请求前的钩子）
    if "setup_hooks" in step:
        test_dict["setup_hooks"] = step["setup_hooks"]

    # 获取teardown_hooks（请求后的钩子）
    if "teardown_hooks" in step:
        test_dict["teardown_hooks"] = step["teardown_hooks"]
    # 获取extract（用于关联取值）
    if "extract" in step:
        test_dict["extract"] = _convert_extractors(step["extract"])
    # 获取暴露的关联参数
    if "export" in step:
        test_dict["export"] = step["export"]
    # 获取validate值，用于断言验证
    if "validate" in step:
        if not isinstance(step["validate"], List):
            raise exceptions.TestCaseFormatError(
                f'Invalid teststep validate: {step["validate"]}'
            )
        test_dict["validate"] = _convert_validators(step["validate"])
    # 获取validate_script值，用于验证脚本
    if "validate_script" in step:
        test_dict["validate_script"] = step["validate_script"]

    return test_dict

# 将v2中的api转换为testcase格式v3
def ensure_testcase_v3_api(api_content: Dict) -> Dict:
    logger.info("convert api in v2 to testcase format v3")

    teststep = {
        # 按自定义进行请求排序
        "request": _sort_request_by_custom_order(api_content["request"]),
    }
    # 确保步骤连接的方法，并更新到teststep中
    teststep.update(_ensure_step_attachment(api_content))

    # 按自定义进行请求排序
    teststep = _sort_step_by_custom_order(teststep)

    config = {"name": api_content["name"]}
    extract_variable_names: List = list(teststep.get("extract", {}).keys())
    if extract_variable_names:
        config["export"] = extract_variable_names
    # 格式化后并返回测试用例
    return {
        "config": config,
        "teststeps": [teststep],
    }

# 确保与testcase格式v2兼容
def ensure_testcase_v3(test_content: Dict) -> Dict:
    """

    :param test_content:
                {
                    "config": {
                        "name": "testcase description",
                        "variables": {},
                        "path":"api/test",
                    },
                    "teststeps": [
                        {
                            "name": "/api/user/login",
                            "request": {
                                "url": "http://127.0.0.1:8000/api/user/login",
                                "method": "POST",
                                "headers": {
                                    "Content-Type": "application/json;charset=UTF-8",
                                    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36",
                                },
                                "json": {
                                    "username": "1",
                                    "password": "2"
                                }
                            },
                            "validate": [
                                {
                                    "eq": [
                                        "status_code",
                                        200
                                    ]
                                },
                            ]
                        },
                    ]
                }
    :return:
    """
    logger.info("ensure compatibility with testcase format v2")
    # 确保与testcase格式v2兼容
    # 初始化v3_content
    v3_content = {"config": test_content["config"], "teststeps": []}

    # 判断是否有测试步骤teststeps
    if "teststeps" not in test_content:
        logger.error(f"Miss teststeps: {test_content}")
        sys.exit(1)

    # 判断测试步骤是否是list
    if not isinstance(test_content["teststeps"], list):
        logger.error(
            f'teststeps should be list type, got {type(test_content["teststeps"])}: {test_content["teststeps"]}'
        )
        sys.exit(1)

    # 遍历测试步骤
    for step in test_content["teststeps"]:
        #初始化测试步骤
        teststep = {}
        # 判断测试步骤类型
        if "request" in step:
            # 将字典进行按要求排序
            teststep["request"] = _sort_request_by_custom_order(step.pop("request"))
        elif "api" in step:
            teststep["testcase"] = step.pop("api")
        elif "testcase" in step:
            teststep["testcase"] = step.pop("testcase")
        else:
            raise exceptions.TestCaseFormatError(f"Invalid teststep: {step}")
        # 将断言的字典重新写入teststep字典
        teststep.update(_ensure_step_attachment(step))
        # teststep字典按自定义进行请求排序
        teststep = _sort_step_by_custom_order(teststep)
        # 将测试步骤加入teststeps的list里
        v3_content["teststeps"].append(teststep)

    return v3_content

# 确保与v2中不推荐使用的cli参数兼容，返回v3的命令
def ensure_cli_args(args: List) -> List:
    """ ensure compatibility with deprecated cli args in v2
    """
    # remove deprecated --failfast
    # 删除不推荐的--failfast
    if "--failfast" in args:
        logger.warning(f"remove deprecated argument: --failfast")
        args.pop(args.index("--failfast"))

    # convert --report-file to --html
    # 将--报表文件转换为--html
    if "--report-file" in args:
        logger.warning(f"replace deprecated argument --report-file with --html")
        # 找出--report-file的索引
        index = args.index("--report-file")
        args[index] = "--html"
        # 最后添加--self-contained-html
        args.append("--self-contained-html")

    # keep compatibility with --save-tests in v2
    # 保持与--save-tests in v2的兼容性
    if "--save-tests" in args:
        logger.warning(
            f"generate conftest.py keep compatibility with --save-tests in v2"
        )
        # 找到--save-tests的索引并移除
        args.pop(args.index("--save-tests"))
        _generate_conftest_for_summary(args)

    return args

# 生成摘要的测试文件conftest.py
def _generate_conftest_for_summary(args: List):

    for arg in args:
        # 如果路径存在
        if os.path.exists(arg):
            test_path = arg
            # FIXME: several test paths maybe specified
            break
    else:
        logger.error(f"No valid test path specified! \nargs: {args}")
        sys.exit(1)

    conftest_content = '''# NOTICE: Generated By HttpRunner.
import json
import os
import time

import pytest
from loguru import logger

from httprunner.utils import get_platform, ExtendJSONEncoder


@pytest.fixture(scope="session", autouse=True)
def session_fixture(request):
    """setup and teardown each task"""
    logger.info(f"start running testcases ...")

    start_at = time.time()

    yield

    logger.info(f"task finished, generate task summary for --save-tests")

    summary = {
        "success": True,
        "stat": {
            "testcases": {"total": 0, "success": 0, "fail": 0},
            "teststeps": {"total": 0, "failures": 0, "successes": 0},
        },
        "time": {"start_at": start_at, "duration": time.time() - start_at},
        "platform": get_platform(),
        "details": [],
    }

    for item in request.node.items:
        testcase_summary = item.instance.get_summary()
        summary["success"] &= testcase_summary.success

        summary["stat"]["testcases"]["total"] += 1
        summary["stat"]["teststeps"]["total"] += len(testcase_summary.step_datas)
        if testcase_summary.success:
            summary["stat"]["testcases"]["success"] += 1
            summary["stat"]["teststeps"]["successes"] += len(
                testcase_summary.step_datas
            )
        else:
            summary["stat"]["testcases"]["fail"] += 1
            summary["stat"]["teststeps"]["successes"] += (
                len(testcase_summary.step_datas) - 1
            )
            summary["stat"]["teststeps"]["failures"] += 1

        testcase_summary_json = testcase_summary.dict()
        testcase_summary_json["records"] = testcase_summary_json.pop("step_datas")
        summary["details"].append(testcase_summary_json)

    summary_path = "{{SUMMARY_PATH_PLACEHOLDER}}"
    summary_dir = os.path.dirname(summary_path)
    os.makedirs(summary_dir, exist_ok=True)

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4, ensure_ascii=False, cls=ExtendJSONEncoder)

    logger.info(f"generated task summary: {summary_path}")

'''
    # 加载项目
    project_meta = load_project_meta(test_path)
    # 获取项目的所在路径
    project_root_dir = project_meta.RootDir
    # 获取"conftest.py"的路径
    conftest_path = os.path.join(project_root_dir, "conftest.py")
    # 获取文件的完整路径
    test_path = os.path.abspath(test_path)
    # 获取日志的完整路径
    logs_dir_path = os.path.join(project_root_dir, "logs")
    # 基于project_meta.RootDir将绝对路径转换为相对路径
    test_path_relative_path = convert_relative_project_root_dir(test_path)
    # 如果是路径
    if os.path.isdir(test_path):
        file_foder_path = os.path.join(logs_dir_path, test_path_relative_path)
        # 转储文件名
        dump_file_name = "all.summary.json"
    else:
        # 获取文件路径和文件名
        file_relative_folder_path, test_file = os.path.split(test_path_relative_path)
        # 获取保存日志的路径
        file_foder_path = os.path.join(logs_dir_path, file_relative_folder_path)
        # 获取文件名和后缀名
        test_file_name, _ = os.path.splitext(test_file)
        # 转储文件名
        dump_file_name = f"{test_file_name}.summary.json"
    # 测试摘要文件的全路径
    summary_path = os.path.join(file_foder_path, dump_file_name)
    # SUMMARY_PATH_PLACEHOLDER 替换为测试摘要路径
    conftest_content = conftest_content.replace(
        "{{SUMMARY_PATH_PLACEHOLDER}}", summary_path
    )
    # 去掉"conftest.py"的文件名，返回目录
    dir_path = os.path.dirname(conftest_path)
    # 如果路径不存在
    if not os.path.exists(dir_path):
        # 创建文件夹
        os.makedirs(dir_path)
    # 把conftest_content写入conftest.py文件中
    with open(conftest_path, "w", encoding="utf-8") as f:
        f.write(conftest_content)

    logger.info("generated conftest.py to generate summary.json")

# 确保linux和windows的不同路径分隔符兼容
def ensure_path_sep(path: Text) -> Text:
    """ ensure compatibility with different path separators of Linux and Windows
    """
    if "/" in path:
        path = os.sep.join(path.split("/"))

    if "\\" in path:
        path = os.sep.join(path.split("\\"))

    return path
