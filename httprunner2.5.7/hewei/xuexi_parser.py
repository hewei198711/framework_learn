# encoding: utf-8

import ast
import builtins
import _collections
import json
import re

from httprunner import exceptions, utils, loader
from httprunner import logger
from httprunner.compat import basestring, numeric_types, str
from httprunner.parser import extract_variables, LazyString, regex_findall_variables

dolloar_regex_compile = re.compile((r"\$\$"))
variable_regex_compile = re.compile(r"\$\{(\w+)\}|\$(\w+)")
function_regex_compile = re.compile(r"\$\{(\w+)\(([\$\w\.\-/\s=,]*)\)\}")

parse_failed_testfiles = {}

def get_parse_failed_testfiles():
    return parse_failed_testfiles

def parse_string_value(str_value):
    """
    将纯数字的字符串解析成数字
    :param str_value:
    :return: int,float
    """
    try:
        return ast.literal_eval(str_value)
    except ValueError:
        return str_value
    except SyntaxError:
        return str_value

def is_var_or_func_exist(content):
    """
    找出引用的变量和函数
    :param content:
    :return:
    """
    if not isinstance(content, basestring):
        return False

    try:
        match_start_position = content.index("$", 0)
    except ValueError:
        return False

    while match_start_position < len(content):

        dolloar_match = dolloar_regex_compile.match(content, match_start_position)
        if dolloar_match:
            match_start_position = dolloar_match.end()
            continue

        func_match = function_regex_compile.match(content, match_start_position)
        if func_match:
            return True

        var_match = variable_regex_compile.match(content, match_start_position)
        if var_match:
            return True

        return False

def parse_parameters(parameters, variables_mapping=None, functions_mapping=None):
    """ parse parameters and generate cartesian product.
        解析参数并生成笛卡尔积

    Args:
        parameters (list) parameters: parameter name and value in list参数(列表)参数:列表中的参数名称和值
            parameter value may be in three types:参数值可以有三种类型
                (1) data list, e.g. ["iOS/10.1", "iOS/10.2", "iOS/10.3"]
                (2) call built-in parameterize function, "${parameterize(account.csv)}"
                (3) call custom function in debugtalk.py, "${gen_app_version()}"

        variables_mapping (dict): variables mapping loaded from testcase config从testcase配置加载的变量映射
        functions_mapping (dict): functions mapping loaded from debugtalk.py函数映射:从debugtalk.py加载的函数映射

    Returns:
        list: cartesian product list笛卡儿产品列表

    Examples:
        >>> parameters = [
            {"user_agent": ["iOS/10.1", "iOS/10.2", "iOS/10.3"]},
            {"username-password": "${parameterize(account.csv)}"},
            {"app_version": "${gen_app_version()}"}
        ]
        >>> parse_parameters(parameters)

    """
    variables_mapping = variables_mapping or {}
    functions_mapping = functions_mapping or {}
    parsed_parameters_list = []

    parameters = utils.ensure_mapping_format(parameters)  # 确保映射的格式是字典
    for parameter_name, parameter_content in parameters.items():
        parameter_name_list = parameter_name.split("-")

        if isinstance(parameter_content, list):
            # (1) data list
            # e.g. {"app_version": ["2.8.5", "2.8.6"]}
            #       => [{"app_version": "2.8.5", "app_version": "2.8.6"}]
            # e.g. {"username-password": [["user1", "111111"], ["test2", "222222"]}
            #       => [{"username": "user1", "password": "111111"}, {"username": "user2", "password": "222222"}]
            parameter_content_list = []
            for parameter_item in parameter_content:
                if not isinstance(parameter_item, (list, tuple)):
                    # "2.8.5" => ["2.8.5"]
                    parameter_item = [parameter_item]

                # ["app_version"], ["2.8.5"] => {"app_version": "2.8.5"}
                # ["username", "password"], ["user1", "111111"] => {"username": "user1", "password": "111111"}
                parameter_content_dict = dict(zip(parameter_name_list, parameter_item))

                parameter_content_list.append(parameter_content_dict)

        elif:
            parsed_variables_mapping = parse_variables_mapping(
                variables_mapping
            )
    return

def parse_variables_mapping(variables_mapping):
    """
    把每个引用变量的值解析出来
    :param variables_mapping:
    :return:
    """
    run_times = 0
    parsed_variables_mapping = {}

    while len(parsed_variables_mapping) != len(variables_mapping):
        for var_name in variables_mapping:

            run_times += 1
            if run_times > len(variables_mapping) * 4:
                not_found_variables = {
                    key:variables_mapping[key]
                    for key in variables_mapping
                    if key not in parsed_variables_mapping
                }
                raise exceptions.VariableNotFound(not_found_variables)

            if var_name in parsed_variables_mapping:
                continue

            value = variables_mapping[var_name]
            variables = extract_variables(value)

    return


def extract_variables(content):
    """
    递归提取单个引用变量的值
    :param content:
    :return:
    """
    if isinstance(content,(list, set, tuple)):
        variables = set()
        for item in content:
            variables = variables | extract_variables(item)
            return variables

    elif isinstance(content, dict):
        variables = set()
        for key, value in content.items():
            variables = variables | extract_variables(value)
        return variables

    elif isinstance(content, LazyString):
        return set(regex_findall_variables(content.raw_string))

    return set()

class LazyString(object):
    """
    惰性计算字符串
    """

    def __init__(self, raw_string, functions_mapping=None, check_variables_set=None, cached=False):
        """
        把原始字符串作为惰性对象，函数映射
        :param raw_string:
        :param functions_mapping:
        :param check_variables_set:
        :param cached:
        """
        self.raw_string = raw_string
        self.functions_mapping = functions_mapping
        self.check_variables_set = check_variables_set
        self.cached = cached
        self.__parse(raw_string)

    def __parse(self, raw_string):
        """
        解析原始字符串，用{}替换引用的函数和变量
        :param raw_string:
        :return:
        """
        self._args = []

        def escape_braces(origin_string):
            return origin_string.replace("{", "{{").replace("}", "}}")

        try:
            match_start_position = raw_string.index("$", 0)
            begin_string =raw_string[0:match_start_position]
            self._string = escape_braces(begin_string)
        except ValueError:
            self._string = escape_braces(raw_string)
            return
        

