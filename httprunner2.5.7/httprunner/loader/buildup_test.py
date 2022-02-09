import importlib
import os

from httprunner import exceptions, logger, utils
from httprunner.loader.check import JsonSchemaChecker
from httprunner.loader.load import load_module_functions, load_file, load_dot_env_file, load_folder_files
from httprunner.loader.locate import init_project_working_directory, get_project_working_directory


tests_def_mapping = {
    "api": {},
    "testcases": {}
    }


def load_debugtalk_functions():
    imported_module = importlib.import_module("debugtalk")
    return load_module_functions(imported_module)


def __extend_with_api_ref(raw_testinfo):
    api_name  = raw_testinfo["api"]
    if not os.path.isabs(api_name):
        pwd = get_project_working_directory()
        api_path = os.path.join(pwd, *api_name.split("/"))
        
        if os.path.isfile(api_path):
            api_name = api_path
    
    if api_name in tests_def_mapping["api"]:
        block = tests_def_mapping["api"][api_name]
    elif not os.path.isfile(api_name):
        raise exceptions.ApiNotFound(f"{api_name} not found!")
    else:
        block = load_file(api_name)
        
    raw_testinfo["api_def"] = utils.deepcopy_dict(block)
    tests_def_mapping["api"][api_name] = block


def __extend_with_testcase_ref(raw_testinfo):
    testcase_path = raw_testinfo["testcase"]
    
    if testcase_path not in tests_def_mapping["testcases"]:
        pwd = get_project_working_directory()
        testcase_path = os.path.join(pwd, *testcase_path.split("/"))
        loaded_testcase = load_file(testcase_path)
        
        if isinstance(loaded_testcase, list):
            testcase_dict = load_testcase(loaded_testcase)
        elif isinstance(loaded_testcase, dict) and "teststeps" in loaded_testcase:
            testcase_dict = load_testcase_v2(loaded_testcase)
        else:
            raise exceptions.FileFormatError(f"Invalid format testcase: {testcase_path}")
        
        tests_def_mapping["testcases"][testcase_path] = testcase_dict
    else:
        testcase_dict = tests_def_mapping["testcases"][testcase_path]
    
    raw_testinfo["testcase_def"] = testcase_dict

    
def load_teststep(raw_testinfo):
    if "api" in raw_testinfo:
        __extend_with_api_ref(raw_testinfo)
    elif "testcase" in raw_testinfo:
        __extend_with_testcase_ref(raw_testinfo)
    else:
        pass
    
    return raw_testinfo
 
 
def load_testcase(raw_testcase):
    JsonSchemaChecker.validate_testcase_v1_format(raw_testcase)
    config = {}
    tests = []

    for item in raw_testcase:
        key, test_block = item.popitem()
        if key == "config":
            config.update(test_block)
        elif key == "test":
            tests.append(load_teststep(test_block))
        else:
            logger.log_warning(f"unexpected block key: {key}. block key should only be 'config' or 'test'.")
    return {"config":config, "teststeps":tests}
 
 
def load_testcase_v2(raw_testcase):
    JsonSchemaChecker.validate_testcase_v2_format(raw_testcase)
    raw_teststeps = raw_testcase.pop("teststeps")
    raw_testcase["teststeps"] = [load_teststep(teststep) for teststep in raw_teststeps]
    return raw_testcase


def load_testsuite(raw_testsuite):
    raw_testcases = raw_testsuite["testcases"]
    
    if isinstance(raw_testcases, dict):
        JsonSchemaChecker.validate_testsuite_v1_format(raw_testsuite)
        raw_testsuite["testcases"] = {}
        for name, raw_testcase in raw_testcases.items():
            __extend_with_testcase_ref(raw_testcase)
            raw_testcase.setdefault("name", name)
            raw_testsuite["testcases"][name] = raw_testcase
    
    elif isinstance(raw_testcases, list):
        JsonSchemaChecker.validate_testsuite_v2_format(raw_testsuite)
        raw_testsuite["testcases"] = {}
        for raw_testcase in raw_testcases:
            __extend_with_testcase_ref(raw_testcase)
            testcase_name = raw_testcase["name"]
            raw_testsuite["testcases"][testcase_name] = raw_testcase
    
    else:
        raise exceptions.FileFormatError("Invalid testsuite format!")
    
    return raw_testsuite


def load_test_file(path):
    raw_content = load_file(path)

    if isinstance(raw_content, dict):
        
        if "testcases" in raw_content:
            loaded_content = load_testsuite(raw_content)
            loaded_content["path"] = path
            loaded_content["type"] = "testsuite"
        elif "teststeps" in raw_content:
            loaded_content = load_testcase_v2(raw_content)
            loaded_content["path"] = path
            loaded_content["type"] = "testcase"
        
        elif "request" in raw_content:
            JsonSchemaChecker.validate_api_format(raw_content)
            loaded_content = raw_content
            loaded_content["path"] = path
            loaded_content["type"] = "api"
        else:
            raise exceptions.FileFormatError("Invalid test file format!")
    elif isinstance(raw_content, list) and len(raw_content) > 0:
        loaded_content = load_testcase(raw_content)
        loaded_content["path"] = path
        loaded_content["type"] = "testcase"
    else:
        raise exceptions.FileFormatError("Invalid test file format!")
    
    return loaded_content





