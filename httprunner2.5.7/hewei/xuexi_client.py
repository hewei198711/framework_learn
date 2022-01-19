# encoding: utf-8

import time

import requests
import urllib3
from requests import Request, Response
from requests.exceptions import (InvalidSchema, InvalidURL,MissingSchema,RequestException)


from httprunner import logger, response
from httprunner.utils import lower_dict_keys, omit_long_data

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_req_resp_record(resp_obj):
    """
    从response()对象中获取请求和响应信息
    """
    def log_print(req_resp_dict, r_type):
        msg = "\n================= {} details ====================\n".format(r_type)
        for key, value in req_resp_dict[r_type].items()
            




