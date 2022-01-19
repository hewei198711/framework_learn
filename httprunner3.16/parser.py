import ast
import builtins
import re
import os
from typing import Any, Set, Text, Callable, List, Dict, Union

from loguru import logger
from sentry_sdk import capture_exception

from httprunner import loader, utils, exceptions
from httprunner.models import VariablesMapping, FunctionsMapping

absolute_http_url_regexp = re.compile(r"^https?://", re.I)

# use $$ to escape $ notation 使用$$转义$符号
dolloar_regex_compile = re.compile(r"\$\$")
# variable notation, e.g. ${var} or $var 变量表示法，例如${var}或$var
variable_regex_compile = re.compile(r"\$\{(\w+)\}|\$(\w+)")
# function notation, e.g. ${func1($var_1, $var_3)} 函数表示法，例如${func1（$was_1，$was_3）}
function_regex_compile = re.compile(r"\$\{(\w+)\(([\$\w\.\-/\s=,]*)\)\}")

# 转换字符串数据类型 "123" => 123, "12.2" => 12.3, "abc" => "abc", "$var" => "$var"
def parse_string_value(str_value: Text) -> Any:
    """ parse string to number if possible
    e.g. "123" => 123
         "12.2" => 12.3
         "abc" => "abc"
         "$var" => "$var"
    """
    try:
        return ast.literal_eval(str_value)
    except ValueError:
        return str_value
    except SyntaxError:
        # e.g. $var, ${func}
        return str_value

# 在url前面加上base_url，除非它已经是绝对url
def build_url(base_url, path):
    """ prepend url with base_url unless it's already an absolute URL """
    # 用正则判断是否是绝对路径
    if absolute_http_url_regexp.match(path):
        return path
    elif base_url:
        # 拼接并返回
        return "{}/{}".format(base_url.rstrip("/"), path.lstrip("/"))
    else:
        raise exceptions.ParamsError("base url missed!")

# 正则表达式查找所有变量，返回 从字符串内容中提取的变量列表
def regex_findall_variables(raw_string: Text) -> List[Text]:
    """ extract all variable names from content, which is in format $variable

    Args:
        raw_string (str): string content

    Returns:
        list: variables list extracted from string content

    Examples:
        >>> regex_findall_variables("$variable")
        ["variable"]

        >>> regex_findall_variables("/blog/$postid")
        ["postid"]

        >>> regex_findall_variables("/$var1/$var2")
        ["var1", "var2"]

        >>> regex_findall_variables("abc")
        []

    """
    try:
        # 获取“$”所在索引
        match_start_position = raw_string.index("$", 0)
    except ValueError:
        return []

    vars_list = []
    # 判断"$"的索引是否是在最后
    while match_start_position < len(raw_string):

        # Notice: notation priority
        # $$ > $var

        # search $$ 正则表达式查找"$$"，返回“$$”始终位置
        dollar_match = dolloar_regex_compile.match(raw_string, match_start_position)
        if dollar_match:
            # 获取$$的终索引
            match_start_position = dollar_match.end()
            continue

        # search variable like ${var} or $var 搜索变量，如${var}或$var
        var_match = variable_regex_compile.match(raw_string, match_start_position)
        if var_match:
            # 获取变量
            var_name = var_match.group(1) or var_match.group(2)
            vars_list.append(var_name)
            # 获取下一段$的索引位置，进行查找$
            match_start_position = var_match.end()
            continue

        curr_position = match_start_position
        try:
            # find next $ location  查找下一个$location ，继续遍历
            match_start_position = raw_string.index("$", curr_position + 1)
        except ValueError:
            # break while loop 中断循环
            break

    return vars_list

# 从字符串内容中提取所有函数，格式为${fun（）}
# "/api/${add(1, 2)}?_t=${get_timestamp()}" 返回 [('add', '1, 2'), ('get_timestamp', '')]
def regex_findall_functions(content: Text) -> List[Text]:
    """ extract all functions from string content, which are in format ${fun()}

    Args:
        content (str): string content

    Returns:
        list: functions list extracted from string content

    Examples:
        >>> regex_findall_functions("${func(5)}")
        ["func(5)"]

        >>> regex_findall_functions("${func(a=1, b=2)}")
        ["func(a=1, b=2)"]

        >>> regex_findall_functions("/api/1000?_t=${get_timestamp()}")
        ["get_timestamp()"]

        >>> regex_findall_functions("/api/${add(1, 2)}")
        ["add(1, 2)"]

        >>> regex_findall_functions("/api/${add(1, 2)}?_t=${get_timestamp()}")
        ["add(1, 2)", "get_timestamp()"]

    """
    try:
        return function_regex_compile.findall(content)
    except TypeError as ex:
        capture_exception(ex)
        return []

# 递归提取内容中的所有变量。
def extract_variables(content: Any) -> Set:
    """ extract all variables in content recursively.
    """
    # 判断是否是列表、字典、集合、元组
    if isinstance(content, (list, set, tuple)):
        variables = set()
        # 遍历取并集
        for item in content:
            variables = variables | extract_variables(item)
        return variables
    # 如果是字典
    elif isinstance(content, dict):
        variables = set()
        # 遍历字典，取字典value的并集
        for key, value in content.items():
            variables = variables | extract_variables(value)
        return variables
    # 如果是str类型
    elif isinstance(content, str):
        return set(regex_findall_variables(content))

    return set()

# 将函数参数解析为args和kwargs。返回方法对应的类型字典
#  "1, 2, a=3, b=4" 返回 {"args": [1,2],"kwargs": {"a":3,"b":4}}
def parse_function_params(params: Text) -> Dict:
    """ parse function params to args and kwargs.

    Args:
        params (str): function param in string

    Returns:
        dict: function meta dict

            {
                "args": [],
                "kwargs": {}
            }

    Examples:
        >>> parse_function_params("")
        {'args': [], 'kwargs': {}}

        >>> parse_function_params("5")
        {'args': [5], 'kwargs': {}}

        >>> parse_function_params("1, 2")
        {'args': [1, 2], 'kwargs': {}}

        >>> parse_function_params("a=1, b=2")
        {'args': [], 'kwargs': {'a': 1, 'b': 2}}

        >>> parse_function_params("1, 2, a=3, b=4")
        {'args': [1, 2], 'kwargs': {'a':3, 'b':4}}

    """
    function_meta = {"args": [], "kwargs": {}}

    # 移除字符串头尾的换行符和空格符
    params_str = params.strip()
    if params_str == "":
        return function_meta
    # 进行“,”号切割为数组
    args_list = params_str.split(",")
    for arg in args_list:
        # 移除字符串头尾的换行符和空格符
        arg = arg.strip()
        if "=" in arg:
            # 进行“=”号切割
            key, value = arg.split("=")
            # 解析字符串值对应的数据类型值，并存入function_meta["kwargs"]的字典中
            function_meta["kwargs"][key.strip()] = parse_string_value(value.strip())
        else:
            # 解析字符串值对应的数据类型值，并存入function_meta["args"]的列表中
            function_meta["args"].append(parse_string_value(arg))

    return function_meta

# 从变量映射中获取变量。
def get_mapping_variable(
    variable_name: Text, variables_mapping: VariablesMapping
) -> Any:
    """ get variable from variables_mapping.

    Args:
        variable_name (str): variable name
        variables_mapping (dict): variables mapping

    Returns:
        mapping variable value.

    Raises:
        exceptions.VariableNotFound: variable is not found.

    """
    # TODO: get variable from debugtalk module and environ
    try:
        return variables_mapping[variable_name]
    except KeyError:
        raise exceptions.VariableNotFound(
            f"{variable_name} not found in {variables_mapping}"
        )

# 从函数映射中获取函数，如果未找到，则尝试检查内置功能是否正常。
def get_mapping_function(
    function_name: Text, functions_mapping: FunctionsMapping
) -> Callable:
    """ get function from functions_mapping,
        if not found, then try to check if builtin function.

    Args:
        function_name (str): function name
        functions_mapping (dict): functions mapping

    Returns:
        mapping function object.

    Raises:
        exceptions.FunctionNotFound: function is neither defined in debugtalk.py nor builtin.

    """
    # 如果存在，则返回映射方法
    if function_name in functions_mapping:
        return functions_mapping[function_name]
    # 如果是"parameterize"或 "P"，则是读取csv文件
    elif function_name in ["parameterize", "P"]:
        return loader.load_csv_file
    # 如果是"environ"或"ENV"，则是读取.env文件
    elif function_name in ["environ", "ENV"]:
        return utils.get_os_environ
    # 如果是"multipart_encoder" 或 "multipart_content_type" ，则导入扩展方法
    elif function_name in ["multipart_encoder", "multipart_content_type"]:
        # extension for upload test
        from httprunner.ext import uploader
        # 返回扩展方法的属性（方法）
        return getattr(uploader, function_name)

    try:
        # check if HttpRunner builtin functions
        # 检查HttpRunner是否具有内置方法，如果有便返回
        built_in_functions = loader.load_builtin_functions()
        return built_in_functions[function_name]
    except KeyError:
        pass

    try:
        # check if Python builtin functions
        # 检查Python内置函数是否正确，如果正确便返回
        return getattr(builtins, function_name)
    except AttributeError:
        pass

    raise exceptions.FunctionNotFound(f"{function_name} is not found.")

# 使用变量和函数映射解析字符串内容。
def parse_string(
    raw_string: Text,
    variables_mapping: VariablesMapping,
    functions_mapping: FunctionsMapping,
) -> Any:
    """ parse string content with variables and functions mapping.

    Args:
        raw_string: raw string content to be parsed. 要解析的原始字符串内容
        variables_mapping: variables mapping.  参数的字典
        functions_mapping: functions mapping.  方法的字典

    Returns:
        str: parsed string content.

    Examples:例子
        >>> raw_string = "abc${add_one($num)}def"
        >>> variables_mapping = {"num": 3}
        >>> functions_mapping = {"add_one": lambda x: x + 1}
        >>> parse_string(raw_string, variables_mapping, functions_mapping)
            "abc4def"

    """
    try:
        # 获取$的索引位置
        match_start_position = raw_string.index("$", 0)
        # 获取非参数化和方法的字符串
        parsed_string = raw_string[0:match_start_position]
    except ValueError:
        parsed_string = raw_string
        # 没有参数和方法直接返回
        return parsed_string
    # 判断索引的位置是否小于字符串，逐步搜索参数和方法
    while match_start_position < len(raw_string):

        # Notice: notation priority
        # $$ > ${func($a, $b)} > $var

        # search $$ 搜索$$的位置
        dollar_match = dolloar_regex_compile.match(raw_string, match_start_position)
        if dollar_match:
            match_start_position = dollar_match.end()
            # 字符串再加上一个“$”
            parsed_string += "$"
            continue

        # search function like ${func($a, $b)}  类似${func（$a，$b）}的搜索函数
        func_match = function_regex_compile.match(raw_string, match_start_position)
        if func_match:
            # 获取方法名
            func_name = func_match.group(1)
            # 从映射中获取方法
            func = get_mapping_function(func_name, functions_mapping)
            # 获取方法的参数
            func_params_str = func_match.group(2)
            # 将函数参数解析为args和kwargs。返回方法对应的类型字典
            function_meta = parse_function_params(func_params_str)
            args = function_meta["args"]
            kwargs = function_meta["kwargs"]
            parsed_args = parse_data(args, variables_mapping, functions_mapping)
            parsed_kwargs = parse_data(kwargs, variables_mapping, functions_mapping)

            try:
                func_eval_value = func(*parsed_args, **parsed_kwargs)
            except Exception as ex:
                logger.error(
                    f"call function error:\n"
                    f"func_name: {func_name}\n"
                    f"args: {parsed_args}\n"
                    f"kwargs: {parsed_kwargs}\n"
                    f"{type(ex).__name__}: {ex}"
                )
                raise

            func_raw_str = "${" + func_name + f"({func_params_str})" + "}"
            if func_raw_str == raw_string:
                # raw_string is a function, e.g. "${add_one(3)}", return its eval value directly
                return func_eval_value

            # raw_string contains one or many functions, e.g. "abc${add_one(3)}def"
            parsed_string += str(func_eval_value)
            match_start_position = func_match.end()
            continue

        # search variable like ${var} or $var
        var_match = variable_regex_compile.match(raw_string, match_start_position)
        if var_match:
            var_name = var_match.group(1) or var_match.group(2)
            var_value = get_mapping_variable(var_name, variables_mapping)

            if f"${var_name}" == raw_string or "${" + var_name + "}" == raw_string:
                # raw_string is a variable, $var or ${var}, return its value directly
                return var_value

            # raw_string contains one or many variables, e.g. "abc${var}def"
            parsed_string += str(var_value)
            match_start_position = var_match.end()
            continue

        curr_position = match_start_position
        try:
            # find next $ location
            match_start_position = raw_string.index("$", curr_position + 1)
            remain_string = raw_string[curr_position:match_start_position]
        except ValueError:
            remain_string = raw_string[curr_position:]
            # break while loop
            match_start_position = len(raw_string)

        parsed_string += remain_string

    return parsed_string

# 使用求值变量映射解析原始数据。
# 注意：变量映射不应包含任何变量或函数。
def parse_data(
    raw_data: Any,
    variables_mapping: VariablesMapping = None,
    functions_mapping: FunctionsMapping = None,
) -> Any:
    """ parse raw data with evaluated variables mapping.
        Notice: variables_mapping should not contain any variable or function.
    """
    # 判断是否是字符串
    if isinstance(raw_data, str):
        # content in string format may contains variables and functions
        variables_mapping = variables_mapping or {}
        functions_mapping = functions_mapping or {}
        # only strip whitespaces and tabs, \n\r is left because they maybe used in changeset
        # 只剩下带空白和制表符，\n\r，因为它们可能在变更集中使用
        raw_data = raw_data.strip(" \t")
        # 返回映射值
        return parse_string(raw_data, variables_mapping, functions_mapping)
    # 如果是列表、集合、元组，应进行返回一个列表
    elif isinstance(raw_data, (list, set, tuple)):
        return [
            parse_data(item, variables_mapping, functions_mapping) for item in raw_data
        ]
    # 如果是字典，key和value都要进行映射取值
    elif isinstance(raw_data, dict):
        parsed_data = {}
        for key, value in raw_data.items():
            parsed_key = parse_data(key, variables_mapping, functions_mapping)
            parsed_value = parse_data(value, variables_mapping, functions_mapping)
            parsed_data[parsed_key] = parsed_value

        return parsed_data

    else:
        # other types, e.g. None, int, float, bool
        # 其他类型，如无、整数、浮点、布尔
        return raw_data

# 解析变量映射
def parse_variables_mapping(
    variables_mapping: VariablesMapping, functions_mapping: FunctionsMapping = None
) -> VariablesMapping:

    parsed_variables: VariablesMapping = {}
    # 判断两个字典长度是否相等
    while len(parsed_variables) != len(variables_mapping):
        for var_name in variables_mapping:

            if var_name in parsed_variables:
                continue

            var_value = variables_mapping[var_name]
            # 递归提取内容中的所有变量。
            variables = extract_variables(var_value)

            # check if reference variable itself
            if var_name in variables:
                # e.g.
                # variables_mapping = {"token": "abc$token"}
                # variables_mapping = {"key": ["$key", 2]}
                raise exceptions.VariableNotFound(var_name)

            # check if reference variable not in variables_mapping
            not_defined_variables = [
                v_name for v_name in variables if v_name not in variables_mapping
            ]
            if not_defined_variables:
                # e.g. {"varA": "123$varB", "varB": "456$varC"}
                # e.g. {"varC": "${sum_two($a, $b)}"}
                raise exceptions.VariableNotFound(not_defined_variables)

            try:
                parsed_value = parse_data(
                    var_value, parsed_variables, functions_mapping
                )
            except exceptions.VariableNotFound:
                continue

            parsed_variables[var_name] = parsed_value

    return parsed_variables

# 解析参数并生成笛卡尔积。
def parse_parameters(parameters: Dict,) -> List[Dict]:
    """ parse parameters and generate cartesian product.
        解析参数并生成笛卡尔积。

    Args:参数
        parameters (Dict) parameters: parameter name and value mapping
        参数（Dict）参数：参数名称和值映射
            parameter value may be in three types:
            参数值可以有三种类型：
                (1) data list, e.g. ["iOS/10.1", "iOS/10.2", "iOS/10.3"]
                (1) 数据列表，例如[“IOS/10.1”，“IOS/10.2”，“IOS/10.3”]
                (2) call built-in parameterize function, "${parameterize(account.csv)}"
                (2) 调用内置的参数化函数“${parameterine（account.csv）}”
                (3) call custom function in debugtalk.py, "${gen_app_version()}"
                (3) 调用debugtalk.py中的自定义函数，“${gen_app_version()}”

    Returns:
        list: cartesian product list 笛卡尔乘积表

    Examples: 例子
        >>> parameters = {
            "user_agent": ["iOS/10.1", "iOS/10.2", "iOS/10.3"],
            "username-password": "${parameterize(account.csv)}",
            "app_version": "${gen_app_version()}",
        }
        >>> parse_parameters(parameters)

    """
    parsed_parameters_list: List[List[Dict]] = []

    # load project_meta functions  加载项目元函数
    project_meta = loader.load_project_meta(os.getcwd())
    # 获取debugtalk.py中的自定义函数
    functions_mapping = project_meta.functions
    # 遍历参数化字典
    for parameter_name, parameter_content in parameters.items():
        # 使用“-”分组
        parameter_name_list = parameter_name.split("-")
        # 如果参数内容是字典
        if isinstance(parameter_content, List):
            # (1) data list
            # e.g. {"app_version": ["2.8.5", "2.8.6"]}
            #       => [{"app_version": "2.8.5", "app_version": "2.8.6"}]
            # e.g. {"username-password": [["user1", "111111"], ["test2", "222222"]}
            #       => [{"username": "user1", "password": "111111"}, {"username": "user2", "password": "222222"}]
            parameter_content_list: List[Dict] = []
            for parameter_item in parameter_content:
                if not isinstance(parameter_item, (list, tuple)):
                    # "2.8.5" => ["2.8.5"]
                    parameter_item = [parameter_item]

                # ["app_version"], ["2.8.5"] => {"app_version": "2.8.5"}
                # ["username", "password"], ["user1", "111111"] => {"username": "user1", "password": "111111"}
                # 打包成元组，最后转为字典
                parameter_content_dict = dict(zip(parameter_name_list, parameter_item))
                parameter_content_list.append(parameter_content_dict)
        # 如果是字符串
        elif isinstance(parameter_content, Text):
            # (2) & (3)
            # 使用求值变量映射解析原始数据。
            parsed_parameter_content: List = parse_data(
                parameter_content, {}, functions_mapping
            )
            # 如果解析出来不是list，则报错提醒，参数内容应为列表类型
            if not isinstance(parsed_parameter_content, List):
                raise exceptions.ParamsError(
                    f"parameters content should be in List type, got {parsed_parameter_content} for {parameter_content}"
                )

            parameter_content_list: List[Dict] = []
            # 遍历list
            for parameter_item in parsed_parameter_content:
                # 如果元素是否是字典
                if isinstance(parameter_item, Dict):
                    # get subset by parameter name
                    # {"app_version": "${gen_app_version()}"}
                    # gen_app_version() => [{'app_version': '2.8.5'}, {'app_version': '2.8.6'}]
                    # {"username-password": "${get_account()}"}
                    # get_account() => [
                    #       {"username": "user1", "password": "111111"},
                    #       {"username": "user2", "password": "222222"}
                    # ]
                    # 提取字典中的参数值，形成新的字典
                    parameter_dict: Dict = {
                        key: parameter_item[key] for key in parameter_name_list
                    }
                # 如果元素是list或者元组
                elif isinstance(parameter_item, (List, tuple)):
                    # 判断参数长度与元素值长度是否一致
                    if len(parameter_name_list) == len(parameter_item):
                        # {"username-password": "${get_account()}"}
                        # get_account() => [("user1", "111111"), ("user2", "222222")]
                        # 形成新的字典
                        parameter_dict = dict(zip(parameter_name_list, parameter_item))
                    else:
                        # 参数名称长度不等于值长度
                        raise exceptions.ParamsError(
                            f"parameter names length are not equal to value length.\n"
                            f"parameter names: {parameter_name_list}\n"
                            f"parameter values: {parameter_item}"
                        )
                # 如果参数长度等于1
                elif len(parameter_name_list) == 1:
                    # {"user_agent": "${get_user_agent()}"}
                    # get_user_agent() => ["iOS/10.1", "iOS/10.2"]
                    # parameter_dict will get: {"user_agent": "iOS/10.1", "user_agent": "iOS/10.2"}
                    # 形成新的字典
                    parameter_dict = {parameter_name_list[0]: parameter_item}
                else:
                    raise exceptions.ParamsError(
                        f"Invalid parameter names and values:\n"
                        f"parameter names: {parameter_name_list}\n"
                        f"parameter values: {parameter_item}"
                    )
                # 把参数字典加入列表中
                parameter_content_list.append(parameter_dict)

        else:
            raise exceptions.ParamsError(
                f"parameter content should be List or Text(variables or functions call), got {parameter_content}"
            )
        # 把参数列表加入参数总列表中
        parsed_parameters_list.append(parameter_content_list)
    # 返回列表生成的笛卡尔乘积
    return utils.gen_cartesian_product(*parsed_parameters_list)
