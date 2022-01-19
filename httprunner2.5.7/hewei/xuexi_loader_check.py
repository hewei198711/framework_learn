import io
import json
import os
import platform
import jsonschema
from prettyprinter import pprint

from httprunner import exceptions, logger

schemas_root_dir = os.path.join(os.path.dirname(__file__),"schemas")
common_schema_path = os.path.join(schemas_root_dir, "common.schema.json")
api_schema_path = os.path.join(schemas_root_dir, "api.schema.json")
testcase_schema_v1_path = os.path.join(schemas_root_dir, "testcase.schema.v1.json")
testcase_schema_v2_path = os.path.join(schemas_root_dir, "testcase.schema.v2.json")
testsuite_schema_v1_path = os.path.join(schemas_root_dir, "testsuite.schema.v1.json")
testsuite_schema_v2_path = os.path.join(schemas_root_dir, "testsuite.schema.v2.json")



