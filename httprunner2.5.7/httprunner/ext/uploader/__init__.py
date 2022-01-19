""" upload test extension.上传测试扩展

If you want to use this extension, you should install the following dependencies first.
如果您想使用这个扩展，您应该首先安装以下依赖项。

- requests_toolbelt
- filetype

Then you can write upload test script as below:
然后你可以写上传测试脚本如下:

    - test:
        name: upload file
        request:
            url: http://httpbin.org/upload
            method: POST
            headers:
                Cookie: session=AAA-BBB-CCC
            upload:
                file: "data/file_to_upload"
                field1: "value1"
                field2: "value2"
        validate:
            - eq: ["status_code", 200]

For compatibility, you can also write upload test script in old way:
为了兼容性，您也可以用旧的方式编写上载测试脚本

    - test:
        name: upload file
        variables:
            file: "data/file_to_upload"
            field1: "value1"
            field2: "value2"
            m_encoder: ${multipart_encoder(file=$file, field1=$field1, field2=$field2)}
        request:
            url: http://httpbin.org/upload
            method: POST
            headers:
                Content-Type: ${multipart_content_type($m_encoder)}
                Cookie: session=AAA-BBB-CCC
            data: $m_encoder
        validate:
            - eq: ["status_code", 200]

"""

import os
import sys

try:
    import filetype
    from requests_toolbelt import MultipartEncoder
except ImportError:
    msg = """
uploader extension dependencies uninstalled, install first and try again.
上传扩展依赖项已卸载，请先安装，然后重试
install with pip:
$ pip install requests_toolbelt filetype
"""
    print(msg)
    sys.exit(0)

from httprunner.exceptions import ParamsError


def prepare_upload_test(test_dict):
    """ preprocess for upload test
        上传测试的预处理
        replace `upload` info with MultipartEncoder
        用MultipartEncoder替换upload信息

    Args:
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
    upload_json = test_dict["request"].pop("upload", {})
    if not upload_json:
        raise ParamsError("invalid upload info: {}".format(upload_json))

    params_list = []
    for key, value in upload_json.items():
        test_dict["variables"][key] = value  # 把文件中的键值对添加到variables
        params_list.append("{}=${}".format(key, key))

    params_str = ", ".join(params_list)
    test_dict["variables"]["m_encoder"] = "${multipart_encoder(" + params_str + ")}"

    test_dict["request"].setdefault("headers", {})
    test_dict["request"]["headers"]["Content-Type"] = "${multipart_content_type($m_encoder)}"

    test_dict["request"]["data"] = "$m_encoder"


def multipart_encoder(**kwargs):
    """ initialize MultipartEncoder with uploading fields.
        用上传字段初始化 MultipartEncoder
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
            # value is absolute file path值是绝对文件路径
            _file_path = value
            is_exists_file = os.path.isfile(value)
        else:
            # value is not absolute file path, check if it is relative file path
            # 值不是绝对文件路径，检查是否是相对文件路径
            from httprunner.loader import get_pwd
            _file_path = os.path.join(get_pwd(), value)
            is_exists_file = os.path.isfile(_file_path)

        if is_exists_file:
            # value is file path to upload值为上传的文件路径
            filename = os.path.basename(_file_path)
            mime_type = get_filetype(_file_path)
            # TODO: fix ResourceWarning for unclosed file 修正未关闭文件的资源警告
            file_handler = open(_file_path, 'rb')
            fields_dict[key] = (filename, file_handler, mime_type)
        else:
            fields_dict[key] = value

    return MultipartEncoder(fields=fields_dict)


def multipart_content_type(m_encoder):
    """ prepare Content-Type for request headers
        为请求标头准备内容类型
    """
    return m_encoder.content_type
