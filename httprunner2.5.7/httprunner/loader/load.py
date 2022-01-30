import csv
import io
import json
import os
import types

import yaml

from httprunner import builtin
from httprunner import exceptions, logger, utils
from httprunner.loader.locate import get_project_working_directory

try:
    # PyYAML version >= 5.1
    # ref: https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation
    yaml.warnings({'YAMLLoadWarning': False})
except AttributeError:
    pass


def _load_yaml_file(yaml_file):
    """ load yaml file and check file content format
    """
    with io.open(yaml_file, 'r', encoding='utf-8') as stream:
        try:
            yaml_content = yaml.load(stream)
        except yaml.YAMLError as ex:
            logger.log_error(str(ex))
            raise exceptions.FileFormatError

        return yaml_content


def _load_json_file(json_file):
    """ load json file and check file content format
    """
    with io.open(json_file, encoding='utf-8') as data_file:
        try:
            json_content = json.load(data_file)
        except exceptions.JSONDecodeError:
            err_msg = u"JSONDecodeError: JSON file format error: {}".format(json_file)
            logger.log_error(err_msg)
            raise exceptions.FileFormatError(err_msg)

        return json_content


def load_csv_file(csv_file):
    """ load csv file and check file content format

    Args:
        csv_file (str): csv file path, csv file content is like below:

    Returns:
        list: list of parameters, each parameter is in dict format

    Examples:
        >>> cat csv_file
        username,password
        test1,111111
        test2,222222
        test3,333333

        >>> load_csv_file(csv_file)
        [
            {'username': 'test1', 'password': '111111'},
            {'username': 'test2', 'password': '222222'},
            {'username': 'test3', 'password': '333333'}
        ]

    """
    # os.path.isabs
    if not os.path.isabs(csv_file):
        pwd = get_project_working_directory()
        # make compatible with Windows/Linux
        csv_file = os.path.join(pwd, *csv_file.split("/"))

    if not os.path.isfile(csv_file):
        # file path not exist 文件路径不存在
        raise exceptions.CSVNotFound(csv_file)

    csv_content_list = []

    with io.open(csv_file, encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            csv_content_list.append(row)

    return csv_content_list


def load_file(file_path):
    if not os.path.isfile(file_path):
        raise exceptions.FileNotFound("{} does not exist.".format(file_path))
    # os.path.splitext(path) 分割路径，返回路径名和文件扩展名的元组
    file_suffix = os.path.splitext(file_path)[1].lower()
    if file_suffix == '.json':
        return _load_json_file(file_path)
    elif file_suffix in ['.yaml', '.yml']:
        return _load_yaml_file(file_path)
    elif file_suffix == ".csv":
        return load_csv_file(file_path)
    else:
        # '' or other suffix
        err_msg = u"Unsupported file format: {}".format(file_path)
        logger.log_warning(err_msg)
        return []


def load_folder_files(folder_path, recursive=True):
    """ load folder path, return all files endswith yml/yaml/json in list.

    Args:
        folder_path (str): specified folder path to load
        recursive (bool): load files recursively if True

    Returns:
        list: files endswith yml/yaml/json
    """
    if isinstance(folder_path, (list, set)):
        files = []
        for path in set(folder_path):
            files.extend(load_folder_files(path, recursive))

        return files
    # os.path.exists(path) 如果路径 path 存在，返回 True；如果路径 path 不存在，返回 False
    if not os.path.exists(folder_path):
        return []

    file_list = []
    # os.walk(top) top是你所要遍历的目录的地址, 返回的是一个三元组(root,dirs,files)
    # root 所指的是当前正在遍历的这个文件夹的本身的地址
    # dirs 是一个 list ，内容是该文件夹中所有的目录的名字(不包括子目录)
    # files 同样是 list , 内容是该文件夹中所有的文件(不包括子目录)
    for dirpath, dirnames, filenames in os.walk(folder_path):
        filenames_list = []

        for filename in filenames:
            if not filename.endswith(('.yml', '.yaml', '.json')):
                continue

            filenames_list.append(filename)

        for filename in filenames_list:
            file_path = os.path.join(dirpath, filename)
            file_list.append(file_path)

        if not recursive:
            break

    return file_list


def load_dot_env_file(dot_env_path):
    """ load .env file.

    Args:
        dot_env_path (str): .env file path

    Returns:
        dict: environment variables mapping

            {
                "UserName": "debugtalk",
                "Password": "123456",
                "PROJECT_KEY": "ABCDEFGH"
            }

    Raises:
        exceptions.FileFormatError: If .env file format is invalid.

    """
    if not os.path.isfile(dot_env_path):
        return {}

    logger.log_info("Loading environment variables from {}".format(dot_env_path))
    env_variables_mapping = {}

    with io.open(dot_env_path, 'r', encoding='utf-8') as fp:
        for line in fp:
            # maxsplit=1

            if line.startswith("#"):
                continue
            if "=" in line:
                # split() 切片，如果参数 num 有指定值，则分隔 num+1 个子字符串
                variable, value = line.split("=", 1)
            elif ":" in line:
                variable, value = line.split(":", 1)
            else:
                raise exceptions.FileFormatError(".env format error")
            # strip() 方法用于移除字符串头尾指定的字符（默认为空格或换行符）
            env_variables_mapping[variable.strip()] = value.strip()

    utils.set_os_environ(env_variables_mapping)
    return env_variables_mapping


def load_module_functions(module):
    """ load python module functions.加载python模块函数

    Args:
        module: python module

    Returns:
        dict: functions mapping for specified python module
            指定python模块的函数映射

            {
                "func1_name": func1,
                "func2_name": func2
            }

    """
    module_functions = {}
    # vars() 函数返回对象object的属性和属性值的字典对象
    for name, item in vars(module).items():
        if isinstance(item, types.FunctionType):
            module_functions[name] = item

    return module_functions


def load_builtin_functions():
    """ load builtin module functions
        加载内置模块函数
    """
    return load_module_functions(builtin)

