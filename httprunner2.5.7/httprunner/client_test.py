# encoding: utf-8

import time
from flask import request

import requests
import urllib3
from requests import Request, Response
from requests.exceptions import (InvalidSchema, InvalidURL, MissingSchema, RequestException)

from httprunner import logger, response
from httprunner.utils import lower_dict_keys, omit_long_data

urllib3.disable_warnings(urllib3.exceptions.InsecurePlatformWarning)


def get_req_resp_record(resp_obj):
    
    def log_print(req_resp_dict, r_type):
        msg = f"\n=============== {r_type} details ======================\n"
        for key, value in req_resp_dict[r_type].items():
            msg += f"{key:<16} : {repr(value)}"
        logger.log_debug(msg)
    
    req_resp_dict = {
        "request": {},
        "response": {}
    }
    
    req_resp_dict["request"]["url"] = resp_obj.request.url
    req_resp_dict["request"]["method"] = resp_obj.request.method
    req_resp_dict["request"]["headers"] = dict(resp_obj.request.headers)
    
    request_body = resp_obj.request.body
    if request_body:
        request_content_type = lower_dict_keys(req_resp_dict["request"]["headers"]).get("content-type")
        if request_content_type and "multipart/form-data" in request_content_type:
            req_resp_dict["request"]["body"] = "upload file stream (OMITTED)"    
        else:
            req_resp_dict["request"]["body"] = request_body
    
    log_print(req_resp_dict, "request")

    req_resp_dict["response"]["ok"] = resp_obj.ok
    req_resp_dict["response"]["url"] = resp_obj.url
    req_resp_dict["response"]["status_code"] = resp_obj.status_code
    req_resp_dict["response"]["reason"] = resp_obj.reason
    req_resp_dict["response"]["cookies"] = resp_obj.cookies or {}
    req_resp_dict["response"]["encoding"] = resp_obj.encoding
    req_resp_dict["response"]["headers"] = dict(resp_obj.headers)

    lower_resp_headers = lower_dict_keys(dict(resp_obj.headers))
    content_type = lower_resp_headers.get("content-type", "")
    req_resp_dict["response"]["content-type"] = content_type
    
    if "image" in content_type:
        req_resp_dict["response"]["body"] = resp_obj.content
    else:
        try:
            if isinstance(resp_obj, response.ResponseObject):
                req_resp_dict["response"]["body"] = resp_obj.json
            else:
                req_resp_dict["response"]["body"] = resp_obj.json()
        except ValueError:
            resp_text = resp_obj.text
            req_resp_dict["response"]["body"] = omit_long_data(resp_text)
    
    log_print(req_resp_dict, "response")

    return req_resp_dict


class ApiResponse(Response):
    
    def raise_for_status(self):
        if hasattr(self, "error") and self.error:
            raise self.error
        Response.raise_for_status(self)


class HttpSession(requests.Session):
    
    def __init__(self):
        super().__init__()
        self.init_meta_data()
    
    def init_meta_data(self):
        self.meta_data = {
            "name": "",
            "data": [
                {
                    "request": {
                        "url": "N/A",
                        "method": "N/A",
                        "headers": {}
                    },
                    "response": {
                        "status_code": "N/A",
                        "headers": {},
                        "encoding": None,
                        "content_type": ""
                    }
                }
            ],
            "stat": {
                "content_size": "N/A",
                "response_time_ms": "N/A",
                "elapsed_ms": "N/A"
            }
        }
    
    def update_last_req_resp_record(self, resp_obj):
        self.meta_data["data"].pop()
        self.meta_data["data"].append(get_req_resp_record(resp_obj))
    
    def request(self, method, url, name=None, **kwargs):
        self.init_meta_data()
        
        self.meta_data["name"] = name
        
        self.meta_data["data"][0]["request"]["url"] = url
        self.meta_data["data"][0]["request"]["method"] = method
        kwargs.setdefault("timeout", 120)
        self.meta_data["data"][0]["request"].update(kwargs)

        start_timestamp = time.time()
        response = self._send_request_safe_mode(method, url, **kwargs)
        response_time_ms = round((time.time() - start_timestamp) * 1000, 2)
        
        if kwargs.get("stream", False):
            content_size = int(dict(response.headers).get("content-length") or 0)
        else:
            content_size = len(response.content or "")
        
        self.meta_data["stat"] = {
            "content_size": content_size,
            "response_time_ms": response_time_ms,
            "elapsed_ms": response.elapsed.microseconds / 1000
        }
        
        response_list = response.history + [response]
        self.meta_data["data"] = [get_req_resp_record(resp_obj) for resp_obj in response_list]

        try:
            response.raise_for_status()
        except RequestException as e:
            logger.log_error(f"{str(e)}")
        else:
            logger.log_info(f"status_code: {response.status_code}, response_time(ms): {response_tiem_ms}ms, response_length: {content_size}")
        
        return response

    def _send_request_safe_mode(self, method, url, **kwargs):
        
        try:
            msg = "processed request:\n"
            msg += f"> {method} {url}\n"
            msg += f"> kwargs: {kwargs}"
            logger.log_debug(msg)
            return requests.Session.request(method, url, **kwargs)
        except (MissingSchema, InvalidSchema, InvalidURL):
            raise
        except RequestException as ex:
            resp = ApiResponse()
            resp.error = ex
            resp.status_code = 0
            resp.request = Request(method, url).prepare()
            return resp

    
    