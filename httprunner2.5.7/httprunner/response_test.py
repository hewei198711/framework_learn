# encoding:utf-8

import re
from collections import OrderedDict
from attr import attributes

import jsonpath

from httprunner import exceptions, logger, utils
from httprunner.compat import basestring, is_py2


text_extractor_regexp_compile = re.compile(r".*\(.*\).*")


class ResponseObject:
    
    def __init__(self, resp_obj):
        self.resp_obj = resp_obj
    
    def __getattr__(self, key):
        try:
            if key == "json":
                value = self.resp_obj.json()
            elif key == "cookies":
                value = self.resp_obj.cookies.get_dict()
            else:
                value = getattr(self.resp_obj, key)
            
            self.__dict__[key] = value
            return value
        except AttributeError:
            err_msg = f"ResponseObject does not have attribute: {key}"
            logger.log_error(err_msg)
            raise exceptions.ParamsError(err_msg)
    
    def _extract_field_with_jsonpath(self, field):
        
        try:
            body = self.json
        except exceptions.JSONDecodeError:
            body = self.text
        
        result = jsonpath.jsonpath(body, field)
        if result:
            return result
        else:
            raise exceptions.ExtractFailure(f"\tjsonpath {field} get nothing\n")
    
    def _extract_field_with_regex(self, field):
        metched = re.search(field, self.text)
        if not metched:
            err_msg = f"Faild to extract data with regex! => {field}\n"
            err_msg += f"response body: {self.text}"
            logger.log_error(err_msg)
            raise exceptions.ExtractFailure(err_msg)
        return metched.group(1)
    
    def _extract_field_with_delimiter(self, field):
        try:
            top_query, sub_query = field.split(".", 1)
        except ValueError:
            top_query = field
            sub_query = None
        
        if top_query in ["status_code", "encoding", "ok", "reson", "url"]:
            if sub_query:
                err_msg = f"Failed to extract: {field}\n"
                logger.log_error(err_msg)
                raise exceptions.ParamsError(err_msg)
            return getattr(self, top_query)
        elif top_query == "cookies":
            cookies = self.cookies
            if not sub_query:
                return cookies
            
            try:
                return cookies[sub_query]
            except KeyError:
                err_msg = f"Failed to extract cookie! => {field}\n"
                err_msg += f"response cookies: {cookies}"
                logger.log_error(err_msg)
                raise exceptions.ExtractFailure(err_msg)
        
        elif top_query == "elapsed":
            available_attributes = "available attributes: days, seconds, microseconds, total_seconds"
            if not sub_query:
                err_msg = "elapsed is datetime.timedelta instance, attribute should also be specified!\n"
                err_msg += available_attributes
                logger.log_error(err_msg)
                raise exceptions.ParamsError(err_msg)
            elif sub_query in ["days", "seconds", "microseconds"]:
                return getattr(self.elapsed, sub_query)
            elif sub_query == "total_seconds":
                return self.elapsed.total_seconds()
            else:
                err_msg = f"{sub_query} is not valid datetime.timedelta attribute.\n"
                err_msg += available_attributes
                logger.log_error(err_msg)
                raise exceptions.ParamsError(err_msg)
            
        elif top_query == "headers":
            headers = self.headers
            if not sub_query:
                return headers
            
            try:
                return headers[sub_query]
            except KeyError:
                err_msg = f"Failed to extract headers! => {field}"
                err_msg += f"response headers: {headers}\n"
                logger.log_error(err_msg)
                raise exceptions.ExtractFailure(err_msg)
        
        elif top_query in ["body", "content", "text", "json"]:
            try:
                body = self.json
            except exceptions.JSONDecodeError:
                body = self.text
            
            if not sub_query:
                return body
            
            if isinstance(body, (dict, list)):
                return utils.query_json(body, sub_query)
            elif sub_query.isdigit():
                return utils.query_json(body, sub_query)
            else:
                err_msg = f"Failed to extract attribute from response body! => {field}"
                err_msg += f"response body: {body}"
                logger.log_error(err_msg)
                raise exceptions.ExtractFailure(err_msg)
        
        elif top_query in self.__dict__:
            attributes = self.__dict__[top_query]

            if not sub_query:
                return attributes
            
            if isinstance(attributes, (dict, list)):
                return utils.query_json(attributes, sub_query)
            elif sub_query.isdigit():
                return utils.query_json(attributes, sub_query)
            else:
                err_msg = f"Failed to extract cumstom set attribute from teardown hooks! => {field}\n"
                err_msg += f"response set attributes: {attributes}\n"
                logger.log_error(err_msg)
                raise exceptions.TeardownHooksFailure(err_msg)
        
        else:
            err_msg = u"Failed to extract attribute from response! => {}\n".format(field)
            err_msg += u"available response attributes: status_code, cookies, elapsed, headers, content, " \
                       u"text, json, encoding, ok, reason, url.\n\n"
            err_msg += u"If you want to set attribute in teardown_hooks, take the following example as reference:\n"
            err_msg += u"response.new_attribute = 'new_attribute_value'\n"
            logger.log_error(err_msg)
            raise exceptions.ParamsError(err_msg)
            
    def extract_field(self, field):
        if not isinstance(field, basestring):
            err_msg = f"Invalid extractor! => {field}\n"       
            logger.log_error(err_msg)
            raise exceptions.ParamsError(err_msg)
        
        msg = f"extract: {field}"

        if field.startswith("$"):
            value = self._extract_field_with_jsonpath(field)
        elif text_extractor_regexp_compile.match(field):
            value = self._extract_field_with_regex(field)
        else:
            value = self._extract_field_with_delimiter(field)
        
        msg += f"\t=> {value}"
        logger.log_debug(msg)
    
    def extract_response(self, extractors):
        if not extractors:
            return {}
        
        logger.log_debug("start to extract from response object.")

        extracted_variables_mapping = OrderedDict()
        extract_binds_order_dict = utils.ensure_mapping_format(extractors)

        for key, field in extract_binds_order_dict.items():
            extracted_variables_mapping[key] = self.extract_field(field)

        return extracted_variables_mapping


        
        