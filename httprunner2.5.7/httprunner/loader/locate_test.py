import os
import sys

from httprunner import exceptions, logger


project_working_directory = None


def locate_file(start_path, file_name):
    """
    locate filename and return absolute file path.

    Args:
        start_path ([type]): [description]
        file_name ([type]): [description]
    """
    if os.path.isfile(start_path):
        start_dir_path = os.path.dirname(start_path)
    elif os.path.isdir(start_path):
        start_dir_path = start_path
    else:
        raise exceptions.FileNotFound(f"invalid path : {start_path}")
    
    file_path = os.path.join(start_dir_path, file_name)
    if os.path.isfile(file_path):
        return os.path.abspath(file_path)
    
    if os.path.abspath(start_dir_path) == os.getcwd():
        raise exceptions.FileNotFound(f"{file_name} not found in {start_path}")
    
    parent_dir = os.path.dirname(start_dir_path)
    if parent_dir == start_dir_path:
        raise exceptions.FileNotFound(f"{file_name} not found in {start_path}")
    
    return locate_file(parent_dir, file_name)


def locate_debugtalk_py(start_path):
    """locate debugtalk.py file"""
    try:
        debugtalk_path = locate_file(start_path, "debugtalk.py")
    except exceptions.FileNotFound:
        debugtalk_path = None
    
    return debugtalk_path


def init_project_working_directory(test_path):
    """this should be called at startup"""
    
    def prepare_path(path):
        if not os.path.exists(path):
            err_msg = f"path not exist: {path}"
            logger.log_error(err_msg)
            raise exceptions.FileNotFound(err_msg)
        
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        
        return path
    
    test_path = prepare_path(test_path)
    
    debugtalk_path = locate_debugtalk_py(test_path)
    
    global project_working_directory
    if debugtalk_path:
        project_working_directory = os.path.dirname(debugtalk_path)
    else:
        project_working_directory = os.getcwd()
    
    sys.path.insert(0, project_working_directory)

    return debugtalk_path, project_working_directory


def get_project_working_directory():
    global project_working_directory
    if project_working_directory is None:
        raise exceptions.MyBaseFailure("loader.load_cases() has not been called!")
    
    return project_working_directory

