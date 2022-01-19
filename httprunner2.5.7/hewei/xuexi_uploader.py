import os
import sys


try:
    import filetype
    from requests_toolbelt import MultipartEncoder
except ImportError:
    msg = """
    请先安装拓展依赖
    pip install requests_toolbelt filetype
    """
    print(msg)
    sys.exit(0)

from httprunner.exceptions import ParamsError


def prepare_upload_test(test_dict):
    """
    上传测试的预处理
    :param test_dict:
    :return:
        test_dict (dict):

            {
                "variables": {},
                "request": {
                    "url": "http://httpbin.org/upload",
                    "method": "POST",
                    "headers": {
                        "Cookie": "session=AAA-BBB-CCC"
                    },
                    "upload": {
                        "file": "data/file_to_upload"
                        "md5": "123"
                    }
                }
            }
    """
    upload_json = test_dict["request"].pop("upload",{})
    if not upload_json:
        raise ParamsError("invalid upload info:{}".format(upload_json))

    params_list = []
    for key, value in upload_json.items():
        test_dict["variables"][key] = value
        params_list.append("{}=${}".format(key, key))

    params_str = ", ".join(params_list)
    test_dict["variables"]["m_enconder"] = "${multipart_enconder("+ params_str +")}"

    test_dict["request"].setdefault("headers",{})
    test_dict["request"]["headers"]["Content-Type"] = "${multipart_content_type($m_encoder)}"

    test_dict["request"]["data"] = "$m_encoder"


def multipart_encoder(**kwargs):
    """
    用上传字段初始化 MultipartEncoder
    :param kwargs:
    :return:
    """

    def get_filetype(file_path):
        file_type = filetype.guess(file_path)
        if file_type:
            return file_type.mime
        else:
            return "text/html"

    fields_dict = {}
    for key, value in kwargs.items():
        if os.path.isabs(value):
            _file_path = value
            is_exists_file = os.path.isfile(value)
        else:
            from httprunner.loader import get_pwd
            _file_path = os.path.join(get_pwd(), value)
            is_exists_file = os.path.isfile(_file_path)

        if is_exists_file:
            filename = os.path.basename(_file_path)
            mime_type = get_filetype(_file_path)
            file_handler = open(_file_path, "rb")
            fields_dict[key] = (filename, file_handler, mime_type)
        else:
            fields_dict[key] = value

    return MultipartEncoder(fields=fields_dict)


def multipart_content_type(m_encoder):
    """
    为请求头准备内容类型
    :param m_encoder:
    :return:
    """
    return m_encoder.content_type

