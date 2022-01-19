import csv
import importlib
import json
import os
import sys
import types
from typing import Tuple, Dict, Union, Text, List, Callable

import yaml
from loguru import logger
from pydantic import ValidationError

from httprunner import builtin, utils
from httprunner import exceptions
from httprunner.models import TestCase, ProjectMeta, TestSuite

try:
    # PyYAML version >= 5.1
    # ref: https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation
    yaml.warnings({"YAMLLoadWarning": False})
except AttributeError:
    pass


project_meta: Union[ProjectMeta, None] = None

# 加载yaml文件并检查文件内容格式
def _load_yaml_file(yaml_file: Text) -> Dict:
    """ load yaml file and check file content format
    """
    # 读取yaml文件
    with open(yaml_file, mode="rb") as stream:
        try:
            yaml_content = yaml.load(stream)
        except yaml.YAMLError as ex:
            err_msg = f"YAMLError:\nfile: {yaml_file}\nerror: {ex}"
            logger.error(err_msg)
            raise exceptions.FileFormatError

        return yaml_content

# 加载json文件并检查文件内容格式
def _load_json_file(json_file: Text) -> Dict:
    """ load json file and check file content format
    """
    # 读取json文件
    with open(json_file, mode="rb") as data_file:
        try:
            json_content = json.load(data_file)
        except json.JSONDecodeError as ex:
            err_msg = f"JSONDecodeError:\nfile: {json_file}\nerror: {ex}"
            raise exceptions.FileFormatError(err_msg)

        return json_content

# 加载testcase/testsuite文件内容
def load_test_file(test_file: Text) -> Dict:
    """load testcase/testsuite file content"""
    # 判断是否是文件
    if not os.path.isfile(test_file):
        raise exceptions.FileNotFound(f"test file not exists: {test_file}")
    # 获取后缀名
    file_suffix = os.path.splitext(test_file)[1].lower()
    # 判断后缀名
    if file_suffix == ".json":
        test_file_content = _load_json_file(test_file)
    elif file_suffix in [".yaml", ".yml"]:
        test_file_content = _load_yaml_file(test_file)
    else:
        # '' or other suffix
        raise exceptions.FileFormatError(
            f"testcase/testsuite file should be YAML/JSON format, invalid format file: {test_file}"
        )

    return test_file_content

# 加载测试用例
def load_testcase(testcase: Dict) -> TestCase:
    try:
        # validate with pydantic TestCase model 使用pydantic测试用例模型进行验证
        testcase_obj = TestCase.parse_obj(testcase)
    except ValidationError as ex:
        err_msg = f"TestCase ValidationError:\nerror: {ex}\ncontent: {testcase}"
        raise exceptions.TestCaseFormatError(err_msg)

    return testcase_obj

# 加载测试用例文件并使用pydantic模型进行验证
def load_testcase_file(testcase_file: Text) -> TestCase:
    """load testcase file and validate with pydantic model"""
    testcase_content = load_test_file(testcase_file)
    testcase_obj = load_testcase(testcase_content)
    testcase_obj.config.path = testcase_file
    return testcase_obj

# 加载测试套件
def load_testsuite(testsuite: Dict) -> TestSuite:
    path = testsuite["config"]["path"]
    try:
        # validate with pydantic TestCase model
        # 使用pydantic测试用例模型进行验证
        testsuite_obj = TestSuite.parse_obj(testsuite)
    except ValidationError as ex:
        err_msg = f"TestSuite ValidationError:\nfile: {path}\nerror: {ex}"
        raise exceptions.TestSuiteFormatError(err_msg)

    return testsuite_obj

# 加载.env文件返回字典
def load_dot_env_file(dot_env_path: Text) -> Dict:
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

    logger.info(f"Loading environment variables from {dot_env_path}")
    env_variables_mapping = {}

    with open(dot_env_path, mode="rb") as fp:
        for line in fp:
            # maxsplit=1
            if b"=" in line:
                variable, value = line.split(b"=", 1)
            elif b":" in line:
                variable, value = line.split(b":", 1)
            else:
                raise exceptions.FileFormatError(".env format error")

            env_variables_mapping[
                variable.strip().decode("utf-8")
            ] = value.strip().decode("utf-8")

    utils.set_os_environ(env_variables_mapping)
    return env_variables_mapping

# 加载csv文件，返回字典
def load_csv_file(csv_file: Text) -> List[Dict]:
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
    if not os.path.isabs(csv_file):
        global project_meta
        if project_meta is None:
            raise exceptions.MyBaseFailure("load_project_meta() has not been called!")

        # make compatible with Windows/Linux
        csv_file = os.path.join(project_meta.RootDir, *csv_file.split("/"))

    if not os.path.isfile(csv_file):
        # file path not exist
        raise exceptions.CSVNotFound(csv_file)

    csv_content_list = []

    with open(csv_file, encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            csv_content_list.append(row)

    return csv_content_list

# 加载文件夹路径，返回列表中的所有文件结尾为.yml/.yaml/.json/_test.py。
def load_folder_files(folder_path: Text, recursive: bool = True) -> List:
    """ load folder path, return all files endswith .yml/.yaml/.json/_test.py in list.

    Args:
        folder_path (str): specified folder path to load
        recursive (bool): load files recursively if True

    Returns:
        list: files endswith yml/yaml/json
    """
    # 判断是否是元组或列表
    if isinstance(folder_path, (list, set)):
        files = []
        # 利用集合去重
        for path in set(folder_path):
            # 遍历路径，把文件加入文件列表中
            files.extend(load_folder_files(path, recursive))

        return files
    # 如果文件不存在
    if not os.path.exists(folder_path):
        return []

    file_list = []
    # 遍历路径
    # root 表示当前正在访问的文件夹路径
    # dirs 表示该文件夹下的子目录名list
    # files 表示该文件夹下的文件list
    for dirpath, dirnames, filenames in os.walk(folder_path):
        filenames_list = []
        # 遍历文件，把文件名结尾为.yml/.yaml/.json/_test.py添加到文件名列表
        for filename in filenames:
            if not filename.lower().endswith((".yml", ".yaml", ".json", "_test.py")):
                continue

            filenames_list.append(filename)
        # 遍历文件名列表，把文件名拼接成文件路径，加入文件列表中
        for filename in filenames_list:
            file_path = os.path.join(dirpath, filename)
            file_list.append(file_path)

        if not recursive:
            break

    return file_list

# 返回对象的字典{"func1_name": func1, "func2_name": func2}
def load_module_functions(module) -> Dict[Text, Callable]:
    """ load python module functions.

    Args:
        module: python module

    Returns:
        dict: functions mapping for specified python module

            {
                "func1_name": func1,
                "func2_name": func2
            }

    """
    module_functions = {}
    # 以方法名为key，方法为value
    for name, item in vars(module).items():
        if isinstance(item, types.FunctionType):
            module_functions[name] = item

    return module_functions

# 加载内置模块函数
def load_builtin_functions() -> Dict[Text, Callable]:
    """ load builtin module functions
    """
    return load_module_functions(builtin)

# 找到文件名并返回绝对文件路径。
# 搜索将向上递归，直到系统根目录。
def locate_file(start_path: Text, file_name: Text) -> Text:
    """ locate filename and return absolute file path.
        searching will be recursive upward until system root dir.

    Args:
        file_name (str): target locate file name
        start_path (str): start locating path, maybe file path or directory path

    Returns:
        str: located file path. None if file not found.

    Raises:
        exceptions.FileNotFound: If failed to locate file.

    """
    # 如果是文件
    if os.path.isfile(start_path):
        # 去掉文件名的路径
        start_dir_path = os.path.dirname(start_path)
    # 如果是文件夹路径
    elif os.path.isdir(start_path):
        start_dir_path = start_path
    else:
        raise exceptions.FileNotFound(f"invalid path: {start_path}")
    # 路径加上文件名,形成文件路径
    file_path = os.path.join(start_dir_path, file_name)
    # 如果是文件
    if os.path.isfile(file_path):
        # ensure absolute，返回文件的绝对路径
        return os.path.abspath(file_path)

    # system root dir
    # Windows, e.g. 'E:\\'
    # Linux/Darwin, '/'
    # 再返回上一目录
    parent_dir = os.path.dirname(start_dir_path)
    # 如果无法再上一级目录，则已经是根目录了
    if parent_dir == start_dir_path:
        raise exceptions.FileNotFound(f"{file_name} not found in {start_path}")

    # locate recursive upward
    # 继续递归
    return locate_file(parent_dir, file_name)

# 找到debugtalk.py文件
def locate_debugtalk_py(start_path: Text) -> Text:
    """ locate debugtalk.py file

    Args:
        start_path (str): start locating path,
            maybe testcase file path or directory path

    Returns:
        str: debugtalk.py file path, None if not found

    """
    try:
        # locate debugtalk.py file.
        debugtalk_path = locate_file(start_path, "debugtalk.py")
    except exceptions.FileNotFound:
        debugtalk_path = None

    return debugtalk_path

# 将debugtalk.py路径定位为项目根目录
def locate_project_root_directory(test_path: Text) -> Tuple[Text, Text]:
    """ locate debugtalk.py path as project root directory

    Args:
        test_path: specified testfile path

    Returns:
        (str, str): debugtalk.py path, project_root_directory

    """
    # 返回绝对路径
    def prepare_path(path):
        # 判断文件是否存在
        if not os.path.exists(path):
            err_msg = f"path not exist: {path}"
            logger.error(err_msg)
            raise exceptions.FileNotFound(err_msg)
        # 判断是否是绝对路径，如果不是
        if not os.path.isabs(path):
            # 加上路径
            path = os.path.join(os.getcwd(), path)

        return path
    # 进行路径判断与转为绝对路径
    test_path = prepare_path(test_path)

    # locate debugtalk.py file 找到debugtalk.py文件
    debugtalk_path = locate_debugtalk_py(test_path)

    if debugtalk_path:
        # The folder contains debugtalk.py will be treated as project RootDir.
        # 包含debugtalk.py的文件夹将被视为project RootDir。
        project_root_directory = os.path.dirname(debugtalk_path)
    else:
        # debugtalk.py not found, use os.getcwd() as project RootDir.
        # 找不到debugtalk.py，请将os.getcwd（）用作项目RootDir。
        project_root_directory = os.getcwd()

    return debugtalk_path, project_root_directory

# 加载debugtalk里的方法到字典中
def load_debugtalk_functions() -> Dict[Text, Callable]:
    """ load project debugtalk.py module functions
        debugtalk.py should be located in project root directory.

    Returns:
        dict: debugtalk module functions mapping
            {
                "func1_name": func1,
                "func2_name": func2
            }

    """
    # load debugtalk.py module
    # 导入 debugtalk.py 的对象
    try:
        imported_module = importlib.import_module("debugtalk")
    except Exception as ex:
        logger.error(f"error occurred in debugtalk.py: {ex}")
        sys.exit(1)

    # reload to refresh previously loaded module
    # 重新加载debugtalk.py的对象
    imported_module = importlib.reload(imported_module)
    return load_module_functions(imported_module)

# 加载testcases、.env、debugtalk.py函数。testcases文件夹相对于项目根目录
# 默认情况下，除非将reload设置为true，否则project_meta将只加载一次。
def load_project_meta(test_path: Text, reload: bool = False) -> ProjectMeta:
    """ load testcases, .env, debugtalk.py functions.
        testcases folder is relative to project_root_directory
        by default, project_meta will be loaded only once, unless set reload to true.

    Args:
        test_path (str): test file/folder path, locate project RootDir from this path.
        reload: reload project meta if set true, default to false

    Returns:
        project loaded api/testcases definitions,
            environments and debugtalk.py functions.

    """
    global project_meta
    # 判断根目录不为空，且reload为false
    if project_meta and (not reload):
        return project_meta
    # 加载根目录
    project_meta = ProjectMeta()

    if not test_path:
        return project_meta
    # 获取debugtalk.py路径和项目根目录
    debugtalk_path, project_root_directory = locate_project_root_directory(test_path)

    # add project RootDir to sys.path
    # 将项目RootDir添加到sys.path
    sys.path.insert(0, project_root_directory)

    # load .env file
    # NOTICE:
    # environment variable maybe loaded in debugtalk.py
    # thus .env file should be loaded before loading debugtalk.py
    # 读取.env文件为字典存到project_meta.env，保存.env路径
    dot_env_path = os.path.join(project_root_directory, ".env")
    dot_env = load_dot_env_file(dot_env_path)
    if dot_env:
        project_meta.env = dot_env
        project_meta.dot_env_path = dot_env_path

    if debugtalk_path:
        # load debugtalk.py functions
        # 加载debugtalk.py的函数
        debugtalk_functions = load_debugtalk_functions()
    else:
        debugtalk_functions = {}

    # locate project RootDir and load debugtalk.py functions
    # 定位项目RootDir、debugtalk路径并加载debugtalk.py函数
    project_meta.RootDir = project_root_directory
    project_meta.functions = debugtalk_functions
    project_meta.debugtalk_path = debugtalk_path

    return project_meta

# 基于project_meta.RootDir将绝对路径转换为相对路径
def convert_relative_project_root_dir(abs_path: Text) -> Text:
    """ convert absolute path to relative path, based on project_meta.RootDir

    Args:
        abs_path: absolute path

    Returns: relative path based on project_meta.RootDir

    """
    # 获取project_meta
    _project_meta = load_project_meta(abs_path)
    if not abs_path.startswith(_project_meta.RootDir):
        raise exceptions.ParamsError(
            f"failed to convert absolute path to relative path based on project_meta.RootDir\n"
            f"abs_path: {abs_path}\n"
            f"project_meta.RootDir: {_project_meta.RootDir}"
        )
    # 截取相对于project_meta.RootDir的目录
    return abs_path[len(_project_meta.RootDir) + 1 :]
