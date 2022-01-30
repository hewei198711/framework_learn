import csv
import os
import yaml
import json

from httprunner import logger, exceptions, utils
from httprunner.loader.locate import get_project_working_directory

from pprint import pprint as print


def _load_yaml_file(yaml_file):
    """load yaml file and check file content format"""
    with open(yaml_file, "r", encoding="utf-8") as stream:
        try:
            yaml_content = yaml.load(stream, Loader=yaml.CLoader)
        except yaml.YAMLError as ex:
            logger.log_error(str(ex))
            raise exceptions.FileFormatError
        
        return yaml_content


def _load_json_file(json_file):
    """load json file and check file content format"""
    with open(json_file, "r", encoding="utf-8") as data_file:
        try:
            json_content = json.load(data_file)
        except exceptions.JSONDecodeError:
            err_msg = f"JSONDecodeError: JSON file format error: {json_file}"
            logger.log_error(err_msg)
            raise exceptions.FileFormatError(err_msg)
        return json_content


def load_csv_file(csv_file):
    """load csv file and check file content format"""
    if not os.path.isabs(csv_file):
        pwd = get_project_working_directory()
        csv_file = os.path.join(pwd, *csv_file.split("/"))
    
    if not os.path.isfile(csv_file):
        raise exceptions.CSVNotFound(csv_file)
    
    csv_content_list = []

    with open(csv_file, "r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            csv_content_list.append(row)
    
    return csv_content_list


def load_file(file_path):
    if not os.path.isfile(file_path):
        raise exceptions.FileNotFound(f"{file_path} does not exist.")
    file_suffix = os.path.splitext(file_path)[1].lower()
    if file_suffix == ".json":
        return _load_json_file(file_path)
    elif file_suffix in [".yml", ".yaml"]:
        return _load_yaml_file(file_path)
    elif file_suffix == ".csv":
        return load_csv_file(file_path)
    else:
        err_msg = f"Unsupported file format: {file_path}"
        logger.log_error(err_msg)
        return []


def load_folder_files(folder_path, recursive=True):
    "load folder path, return all files endswith yml/yaml/json in list"
    if isinstance(folder_path, (list, set)):
        files = []
        for path in set(folder_path):
            files.extend(load_folder_files(path, recursive))
        return files
    if not os.path.exists(folder_path):
        return []
    
    file_list = []
    for dirpath, dirnames, filenames in os.walk(folder_path):
        filenames_list =[]
        for filename in filenames:
            if not filename.endswith((".yml", ".yaml", ".json")):
                continue
            filenames_list.append(filename)
            
        for filename in filenames_list:
            file_path = os.path.join(dirpath, filename)
            file_list.append(file_path)
        
        if not recursive:
            break
    
    return file_list


def load_dot_env_file(dot_env_path):
    """load .env file."""
    if not os.path.isfile(dot_env_path):
        return {}
    
    logger.log_info(f"Loading environment variables from {dot_env_path}")
    env_variables_mapping = {}

    with open(dot_env_path, "r", encoding="utf-8") as fp:
        for line in fp:
            if line.startswith(("#", "\n")):
                continue
            if "=" in line:
                variable, value = line.split("=", 1)
            elif ":" in line:
                variable, value = line.split(":", 1)
            else:
                raise exceptions.FileFormatError(".env format error")
            env_variables_mapping[variable.strip()] = value.strip()
    utils.set_os_environ(env_variables_mapping)
    print(os.environ.keys())
    return env_variables_mapping




