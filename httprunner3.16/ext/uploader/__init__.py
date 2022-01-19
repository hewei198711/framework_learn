""" upload test extension.

If you want to use this extension, you should install the following dependencies first.
如果要使用此扩展，应首先安装以下依赖项。
- requests_toolbelt
- filetype

Then you can write upload test script as below:
然后您可以编写上传测试脚本，如下所示：
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
为了兼容性，您还可以用旧方法编写传载测试脚本：

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
from typing import Text, NoReturn

from httprunner.models import TStep, FunctionsMapping
from httprunner.parser import parse_variables_mapping
from loguru import logger

try:
    import filetype
    from requests_toolbelt import MultipartEncoder

    UPLOAD_READY = True
except ModuleNotFoundError:
    UPLOAD_READY = False

# 判断是否安装依赖
def ensure_upload_ready():
    if UPLOAD_READY:
        return

    msg = """
    uploader extension dependencies uninstalled, install first and try again.
    install with pip:
    $ pip install requests_toolbelt filetype

    or you can install httprunner with optional upload dependencies:
    $ pip install "httprunner[upload]"
    """
    logger.error(msg)
    sys.exit(1)

#上传测试的预处理
# 用multipartincoder替换“upload”信息
def prepare_upload_step(step: TStep, functions: FunctionsMapping) -> "NoReturn":
    """ preprocess for upload test
        replace `upload` info with MultipartEncoder

    Args:
        step: teststep
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
        functions: functions mapping

    """
    if not step.request.upload:
        return

    ensure_upload_ready()
    params_list = []
    # 遍历上传文件
    for key, value in step.request.upload.items():
        step.variables[key] = value
        params_list.append(f"{key}=${key}")
    # 列表转为字符串“file=$file,md5=$md5”
    params_str = ", ".join(params_list)
    step.variables["m_encoder"] = "${multipart_encoder(" + params_str + ")}"

    # parse variables
    # 解析变量
    step.variables = parse_variables_mapping(step.variables, functions)

    step.request.headers["Content-Type"] = "${multipart_content_type($m_encoder)}"

    step.request.data = "$m_encoder"

# 使用上传字段初始化多端口编码器。
def multipart_encoder(**kwargs):
    """ initialize MultipartEncoder with uploading fields.

    Returns:
        MultipartEncoder: initialized MultipartEncoder object

    """

    def get_filetype(file_path):
        file_type = filetype.guess(file_path)
        if file_type:
            return file_type.mime
        else:
            return "text/html"

    ensure_upload_ready()
    fields_dict = {}
    for key, value in kwargs.items():

        if os.path.isabs(value):
            # value is absolute file path
            _file_path = value
            is_exists_file = os.path.isfile(value)
        else:
            # value is not absolute file path, check if it is relative file path
            from httprunner.loader import load_project_meta

            project_meta = load_project_meta("")

            _file_path = os.path.join(project_meta.RootDir, value)
            is_exists_file = os.path.isfile(_file_path)

        if is_exists_file:
            # value is file path to upload
            filename = os.path.basename(_file_path)
            mime_type = get_filetype(_file_path)
            # TODO: fix ResourceWarning for unclosed file
            file_handler = open(_file_path, "rb")
            fields_dict[key] = (filename, file_handler, mime_type)
        else:
            fields_dict[key] = value

    return MultipartEncoder(fields=fields_dict)

# 为请求头准备内容类型
def multipart_content_type(m_encoder) -> Text:
    """ prepare Content-Type for request headers

    Args:
        m_encoder: MultipartEncoder object

    Returns:
        content type

    """
    ensure_upload_ready()
    return m_encoder.content_type
