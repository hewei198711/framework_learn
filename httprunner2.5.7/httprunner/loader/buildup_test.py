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
        block = tests_def_mapping["api"]["api_name"]
    elif not os.path.isfile(api_name):
        raise exceptions.ApiNotFound(f"{api_name} not found!")
    else:
        block = load_file(api_name)
        
    raw_testinfo["api_def"] = utils.deepcopy_dict(block)
    tests_def_mapping["api"][api_name] = block

