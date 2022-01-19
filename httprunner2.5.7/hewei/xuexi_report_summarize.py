import sys
from base64 import b64encode
from collections.abc import Iterable

from jinja2 import escape
from prettyprinter import pprint
from requests.cookies import RequestsCookieJar

from httprunner.compat import basestring, bytes, json, numeric_types, JSONDecodeError
from httprunner.report.stringify import dumps_json, detect_encoding

request_data = {
                "url": "http://127.0.0.1:5000/api/get-token",
                "method": "POST",
                "headers": {
                    "User-Agent": "python-requests/2.20.0",
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "*/*",
                    "Connection": "keep-alive",
                    "user_agent": "iOS/10.3",
                    "device_sn": "TESTCASE_CREATE_XXX",
                    "os_platform": "ios",
                    "app_version": "2.8.6",
                    "Content-Type": "application/json",
                    "Content-Length": "52"
                },
                "body": b'{"sign": "cb9d60acd09080ea66c8e63a1c78c6459ea00168"}',
                "verify": False
            }


def stringify_request(request_data):
    """ stringfy HTTP request data

    Args:
        request_data (dict): HTTP request data in dict.

            {
                "url": "http://127.0.0.1:5000/api/get-token",
                "method": "POST",
                "headers": {
                    "User-Agent": "python-requests/2.20.0",
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "*/*",
                    "Connection": "keep-alive",
                    "user_agent": "iOS/10.3",
                    "device_sn": "TESTCASE_CREATE_XXX",
                    "os_platform": "ios",
                    "app_version": "2.8.6",
                    "Content-Type": "application/json",
                    "Content-Length": "52"
                },
                "body": b'{"sign": "cb9d60acd09080ea66c8e63a1c78c6459ea00168"}',
                "verify": false
            }

    """
    for key, value in request_data.items():

        if isinstance(value, (list, dict)):
            value = dumps_json(value)

        elif isinstance(value, bytes):
            try:
                encoding = detect_encoding(value)
                value = value.decode(encoding)
                if key == "body":
                    try:
                        # request body is in json format
                        value = json.loads(value)
                        value = dumps_json(value)
                    except JSONDecodeError:
                        pass
                value = escape(value)
            except UnicodeDecodeError:
                pass

        elif not isinstance(value, (basestring, numeric_types, Iterable)):
            # class instance, e.g. MultipartEncoder()
            value = repr(value)

        elif isinstance(value, RequestsCookieJar):
            value = value.get_dict()

        request_data[key] = value
    return request_data


b = stringify_request(request_data)
pprint(b)




