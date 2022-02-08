from email import contentmanager
import importlib
from httprunner.loader.buildup_test import _extend_with_api_ref
from pprint import pprint as print
from httprunner import builtin

import os


tests_def_mapping = {
    "api": {},
    "testcases": {}
}

raw_testinfo = {
    'api': '完美运营后台登陆.yml',
    'extract': [{'access_token': 'content.data.access_token'},{'token_type': 'content.data.token_type'}],
    'name': '前提条件：登录完美运营后台'
}


_extend_with_api_ref(raw_testinfo)