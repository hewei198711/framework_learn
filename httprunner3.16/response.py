from typing import Dict, Text, Any, NoReturn

import jmespath
import requests
from jmespath.exceptions import JMESPathError
from loguru import logger

from httprunner import exceptions
from httprunner.exceptions import ValidationFailure, ParamsError
from httprunner.models import VariablesMapping, Validators, FunctionsMapping
from httprunner.parser import parse_data, parse_string_value, get_mapping_function

# 将比较器别名转换为统一名称
def get_uniform_comparator(comparator: Text):
    """ convert comparator alias to uniform name
        将比较器别名转换为统一名称
    """
    if comparator in ["eq", "equals", "equal"]:
        return "equal"
    elif comparator in ["lt", "less_than"]:
        return "less_than"
    elif comparator in ["le", "less_or_equals"]:
        return "less_or_equals"
    elif comparator in ["gt", "greater_than"]:
        return "greater_than"
    elif comparator in ["ge", "greater_or_equals"]:
        return "greater_or_equals"
    elif comparator in ["ne", "not_equal"]:
        return "not_equal"
    elif comparator in ["str_eq", "string_equals"]:
        return "string_equals"
    elif comparator in ["len_eq", "length_equal"]:
        return "length_equal"
    elif comparator in [
        "len_gt",
        "length_greater_than",
    ]:
        return "length_greater_than"
    elif comparator in [
        "len_ge",
        "length_greater_or_equals",
    ]:
        return "length_greater_or_equals"
    elif comparator in ["len_lt", "length_less_than"]:
        return "length_less_than"
    elif comparator in [
        "len_le",
        "length_less_or_equals",
    ]:
        return "length_less_or_equals"
    else:
        return comparator

# 统一验证器
def uniform_validator(validator):
    """ unify validator

    Args:
        validator (dict): validator maybe in two formats: 验证器可能有两种格式：

            format1: this is kept for compatibility with the previous versions.
                {"check": "status_code", "comparator": "eq", "expect": 201}
                {"check": "$resp_body_success", "comparator": "eq", "expect": True}
            format2: recommended new version, {assert: [check_item, expected_value]}
                {'eq': ['status_code', 201]}
                {'eq': ['$resp_body_success', True]}

    Returns
        dict: validator info

            {
                "check": "status_code",
                "expect": 201,
                "assert": "equals"
            }

    """
    if not isinstance(validator, dict):
        raise ParamsError(f"invalid validator: {validator}")
    # 第一种验证器
    if "check" in validator and "expect" in validator:
        # format1
        check_item = validator["check"]
        expect_value = validator["expect"]
        message = validator.get("message", "")
        comparator = validator.get("comparator", "eq")
    # 第二种验证器
    elif len(validator) == 1:
        # format2
        # 获取编辑器
        comparator = list(validator.keys())[0]
        # 获取编辑器的值
        compare_values = validator[comparator]
        # 判断比较器的值
        if not isinstance(compare_values, list) or len(compare_values) not in [2, 3]:
            raise ParamsError(f"invalid validator: {validator}")
        # 检查值
        check_item = compare_values[0]
        # 期望值
        expect_value = compare_values[1]
        if len(compare_values) == 3:
            # 错误信息
            message = compare_values[2]
        else:
            # len(compare_values) == 2
            message = ""

    else:
        raise ParamsError(f"invalid validator: {validator}")

    # uniform comparator, e.g. lt => less_than, eq => equals
    # 同一比较值
    assert_method = get_uniform_comparator(comparator)
    # 返回比较器
    return {
        "check": check_item,
        "expect": expect_value,
        "assert": assert_method,
        "message": message,
    }

# 响应对象，进行相应的处理
class ResponseObject(object):
    def __init__(self, resp_obj: requests.Response):
        """ initialize with a requests.Response object
            使用requests.Response对象初始化
        Args:
            resp_obj (instance): requests.Response instance 请求.响应实例

        """
        self.resp_obj = resp_obj
        # 验证结果
        self.validation_results: Dict = {}

    def __getattr__(self, key):
        # 获取响应数据
        if key in ["json", "content", "body"]:
            try:
                value = self.resp_obj.json()
            except ValueError:
                value = self.resp_obj.content
        # 获取响应cookies
        elif key == "cookies":
            value = self.resp_obj.cookies.get_dict()
        else:
            try:
                value = getattr(self.resp_obj, key)
            except AttributeError:
                err_msg = "ResponseObject does not have attribute: {}".format(key)
                logger.error(err_msg)
                raise exceptions.ParamsError(err_msg)

        self.__dict__[key] = value
        return value
    # 利用jmespath提取响应里的值
    def _search_jmespath(self, expr: Text) -> Any:
        # 响应结构体
        resp_obj_meta = {
            "status_code": self.status_code,
            "headers": self.headers,
            "cookies": self.cookies,
            "body": self.body,
        }
        # 如果expr字符串的开头不在响应结构体里
        if not expr.startswith(tuple(resp_obj_meta.keys())):
            return expr
        
        try:
            # json搜索值
            check_value = jmespath.search(expr, resp_obj_meta)
        except JMESPathError as ex:
            logger.error(
                f"failed to search with jmespath\n"
                f"expression: {expr}\n"
                f"data: {resp_obj_meta}\n"
                f"exception: {ex}"
            )
            raise

        return check_value
    # 响应值映射提取器
    def extract(self, extractors: Dict[Text, Text]) -> Dict[Text, Any]:
        if not extractors:
            return {}

        extract_mapping = {}
        # 遍历提取器
        for key, field in extractors.items():
            field_value = self._search_jmespath(field)
            # 把提取值放到extract_mapping映射中
            extract_mapping[key] = field_value

        logger.info(f"extract mapping: {extract_mapping}")
        return extract_mapping

    # 响应的验证器
    def validate(
        self,
        validators: Validators,
        variables_mapping: VariablesMapping = None,
        functions_mapping: FunctionsMapping = None,
    ) -> NoReturn:

        variables_mapping = variables_mapping or {}
        functions_mapping = functions_mapping or {}

        self.validation_results = {}
        if not validators:
            return
        # 默认断言为pass
        validate_pass = True
        failures = []
        # 遍历验证器
        for v in validators:

            if "validate_extractor" not in self.validation_results:
                self.validation_results["validate_extractor"] = []
            # 统一校验器
            u_validator = uniform_validator(v)

            # check item 检查项
            check_item = u_validator["check"]
            if "$" in check_item:
                # check_item is variable or function
                # 检查项目是否为变量或函数，使用求值变量映射解析原始数据。
                check_item = parse_data(
                    check_item, variables_mapping, functions_mapping
                )
                # 转换字符串数据类型
                check_item = parse_string_value(check_item)
            # 如果检查值是字符串
            if check_item and isinstance(check_item, Text):
                # 利用jmespath提取响应里的值
                check_value = self._search_jmespath(check_item)
            else:
                # variable or function evaluation result is "" or not text
                # 变量或函数计算结果为“”或者不是文本
                check_value = check_item

            # comparator 比较器
            # 比较器的方法
            assert_method = u_validator["assert"]
            # 从函数映射中获取函数
            assert_func = get_mapping_function(assert_method, functions_mapping)

            # expect item 期望值
            expect_item = u_validator["expect"]
            # parse expected value with config/teststep/extracted variables 使用config/teststep/extracted变量解析期望值
            # 使用求值变量映射解析原始数据。
            expect_value = parse_data(expect_item, variables_mapping, functions_mapping)

            # message 提示信息
            message = u_validator["message"]
            # parse expected value with config/teststep/extracted variables 使用config/teststep/extracted变量解析期望值
            # 使用求值变量映射解析原始数据。
            message = parse_data(message, variables_mapping, functions_mapping)

            validate_msg = f"assert {check_item} {assert_method} {expect_value}({type(expect_value).__name__})"
            # 校验器的映射
            validator_dict = {
                "comparator": assert_method, # 校验方法
                "check": check_item, # 检查项
                "check_value": check_value, # 检查值
                "expect": expect_item, # 期望项
                "expect_value": expect_value, # 期望值
                "message": message, # 提示信息
            }

            try:
                # 进行断言
                assert_func(check_value, expect_value, message)
                validate_msg += "\t==> pass"
                logger.info(validate_msg)
                # 校验器的映射，加上校验结果
                validator_dict["check_result"] = "pass"
            except AssertionError as ex:
                validate_pass = False
                validator_dict["check_result"] = "fail"
                validate_msg += "\t==> fail"
                validate_msg += (
                    f"\n"
                    f"check_item: {check_item}\n"
                    f"check_value: {check_value}({type(check_value).__name__})\n"
                    f"assert_method: {assert_method}\n"
                    f"expect_value: {expect_value}({type(expect_value).__name__})"
                )
                message = str(ex)
                if message:
                    validate_msg += f"\nmessage: {message}"

                logger.error(validate_msg)
                # 失败信息存入失败列表
                failures.append(validate_msg)
            # 存入校验器列表
            self.validation_results["validate_extractor"].append(validator_dict)

        if not validate_pass:
            failures_string = "\n".join([failure for failure in failures])
            # 抛出失败异常
            raise ValidationFailure(failures_string)
