import json
import os
import platform
from unittest import TestSuite

import jsonschema

from httprunner import exceptions, logger

from pprint import pprint as print


schemas_root_dir = os.path.join(os.path.dirname(__file__), "schemas")
common_schema_path = os.path.join(schemas_root_dir, "common.schema.json")
api_schema_path = os.path.join(schemas_root_dir, "api.schema.json")
testcase_schema_v1_path = os.path.join(schemas_root_dir,"testcase.schema.v1.json")
testcase_schema_v2_path = os.path.join(schemas_root_dir, "testcase.schema.v2.json")
testSuite_schema_v1_path = os.path.join(schemas_root_dir, "testsuite.schema.v1.json")
testSuite_schema_v2_path = os.path.join(schemas_root_dir, "testsuite.schema.v2.json")


with open(api_schema_path, encoding="utf-8") as f:
    api_schema = json.load(f)


with open(common_schema_path, encoding="utf-8") as f:
    if platform.system() == "Windows":
        absolute_base_path = "file:///" + os.path.abspath(schemas_root_dir).replace("\\", "/") + "/"
    else:
        absolute_base_path = "file://" +os.path.abspath(schemas_root_dir) + "/"
    common_schema = json.load(f)
    resolver = jsonschema.RefResolver(absolute_base_path, common_schema)


with open(testcase_schema_v1_path, encoding="utf-8") as f:
    testcase_schema_v1 = json.load(f)


with open(testcase_schema_v2_path, encoding="utf-8") as f:
    testcase_schema_v2 = json.load(f)


with open(testSuite_schema_v1_path, encoding="utf-8") as f:
    testSuite_schema_v1 = json.load(f)


with open(testSuite_schema_v2_path, encoding="utf-8") as f:
    testSuite_schema_v2 = json.load(f)


class JsonSchemaChecker:
    
    @staticmethod
    def validate_format(content, scheme):
        """check api/testcase/testsuite format if valid"""
        try:
            jsonschema.validate(content, scheme, resolver=resolver)
        except jsonschema.exceptions.ValidationError as ex:
            logger.log_error(str(ex))
            raise exceptions.FileFormatError
        
        return True
    
    @staticmethod
    def validate_api_format(content):
        """check api format if valid"""
        return JsonSchemaChecker.validate_format(content, api_schema)
    
    @staticmethod
    def validate_testcase_v1_format(content):
        """check testcase format v1 if valid"""
        return JsonSchemaChecker.validate_format(content, testcase_schema_v1)
    
    @staticmethod
    def validate_testcase_v2_format(content):
        """check testcase format v2 if valid"""
        return JsonSchemaChecker.validate_format(content, testcase_schema_v2)
    
    @staticmethod
    def validate_testsuite_v1_format(content):
        """check testsuite format v1 if valid"""
        return JsonSchemaChecker.validate_format(content, testSuite_schema_v1)
    
    @staticmethod
    def validate_testsuite_v2_format(content):
        """check testsuite format v2 if valid"""
        return JsonSchemaChecker.validate_format(content, testSuite_schema_v2)


def is_test_path(path):
    if not isinstance(path, (str, list, tuple)):
        return False
    
    elif isinstance(path, (list, tuple)):
        for p in path:
            if not is_test_path(p):
                return False
        return True
    else:
        if not os.path.exists(path):
            return False
        
        if os.path.isfile(path):
            file_suffix = os.path.splitext(path)[1].lower()
            if file_suffix not in [".json", ".yaml", ".yml"]:
                return False
            else:
                return True
        elif os.path.isdir(path):
            return True
        else:
            return False
    

