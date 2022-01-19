import os
from enum import Enum
from typing import Any
from typing import Dict, Text, Union, Callable
from typing import List

from pydantic import BaseModel, Field
from pydantic import HttpUrl

Name = Text
Url = Text
BaseUrl = Union[HttpUrl, Text]
VariablesMapping = Dict[Text, Any]
FunctionsMapping = Dict[Text, Callable]
Headers = Dict[Text, Text]
Cookies = Dict[Text, Text]
Verify = bool
Hooks = List[Union[Text, Dict[Text, Text]]]
Export = List[Text]
Validators = List[Dict]
Env = Dict[Text, Any]

# 定义请求方法的枚举
class MethodEnum(Text, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    PATCH = "PATCH"

# 定义config结构体
class TConfig(BaseModel):
    name: Name
    verify: Verify = False
    base_url: BaseUrl = ""
    # Text: prepare variables in debugtalk.py, ${gen_variables()}
    variables: Union[VariablesMapping, Text] = {}
    parameters: Union[VariablesMapping, Text] = {}
    # setup_hooks: Hooks = []
    # teardown_hooks: Hooks = []
    export: Export = []
    path: Text = None
    weight: int = 1

# 定义Request结构体
class TRequest(BaseModel):
    """requests.Request model"""

    method: MethodEnum
    url: Url
    params: Dict[Text, Text] = {}
    headers: Headers = {}
    req_json: Union[Dict, List, Text] = Field(None, alias="json")
    data: Union[Text, Dict[Text, Any]] = None
    cookies: Cookies = {}
    timeout: float = 120
    allow_redirects: bool = True
    verify: Verify = False
    upload: Dict = {}  # used for upload files  用于上传文件

# 定义测试步骤step结构体
class TStep(BaseModel):
    name: Name
    request: Union[TRequest, None] = None
    testcase: Union[Text, Callable, None] = None
    variables: VariablesMapping = {}
    setup_hooks: Hooks = []
    teardown_hooks: Hooks = []
    # used to extract request's response field 用于提取请求的响应字段
    extract: VariablesMapping = {}
    # used to export session variables from referenced testcase
    # 用于从引用的testcase导出会话变量
    export: Export = []
    validators: Validators = Field([], alias="validate")
    validate_script: List[Text] = []

# 定义测试用例TestCase结构体
class TestCase(BaseModel):
    config: TConfig
    teststeps: List[TStep]

# 定义项目元结构体
class ProjectMeta(BaseModel):
    debugtalk_py: Text = ""  # debugtalk.py file content debugtalk.py文件内容
    debugtalk_path: Text = ""  # debugtalk.py file path  debugtalk.py文件路径
    dot_env_path: Text = ""  # .env file path  .env文件路径
    functions: FunctionsMapping = {}  # functions defined in debugtalk.py  debugtalk.py中定义的函数
    env: Env = {} # .env文件定义的字典
    # 项目根目录（确保绝对），位于路径debugtalk.py
    RootDir: Text = os.getcwd()  # project root directory (ensure absolute), the path debugtalk.py located

# 定义测试映射结构体
class TestsMapping(BaseModel):
    project_meta: ProjectMeta
    testcases: List[TestCase]

# 定义测试用例时间结构体
class TestCaseTime(BaseModel):
    start_at: float = 0
    start_at_iso_format: Text = ""
    duration: float = 0

# 定义测试用例输入输出结构体
class TestCaseInOut(BaseModel):
    config_vars: VariablesMapping = {}
    export_vars: Dict = {}

# 定义请求统计结构体
class RequestStat(BaseModel):
    content_size: float = 0
    response_time_ms: float = 0
    elapsed_ms: float = 0

# 定义地址数据结构体
class AddressData(BaseModel):
    client_ip: Text = "N/A"
    client_port: int = 0
    server_ip: Text = "N/A"
    server_port: int = 0

#  定义请求数据结构体，method默认为GET
class RequestData(BaseModel):
    method: MethodEnum = MethodEnum.GET
    url: Url
    headers: Headers = {}
    cookies: Cookies = {}
    body: Union[Text, bytes, List, Dict, None] = {}

#  定义数据响应结构体
class ResponseData(BaseModel):
    status_code: int
    headers: Dict
    cookies: Cookies
    encoding: Union[Text, None] = None
    content_type: Text
    body: Union[Text, bytes, List, Dict]

# 定义请求与响应数据结构体
class ReqRespData(BaseModel):
    request: RequestData
    response: ResponseData

# 定义请求会话数据结构体，包括请求、响应、验证器和stat数据
class SessionData(BaseModel):
    """request session data, including request, response, validators and stat data"""

    success: bool = False
    # in most cases, req_resps only contains one request & response
    # while when 30X redirect occurs, req_resps will contain multiple request & response
    # 在大多数情况下，req_resps只包含一个请求和响应
    # 当30x重定向发生时，请求响应将包含多个请求和响应
    req_resps: List[ReqRespData] = []
    stat: RequestStat = RequestStat()
    address: AddressData = AddressData()
    validators: Dict = {}

# 定义测试步骤数据结构体，每个步骤可能对应一个请求或一个测试用例
class StepData(BaseModel):
    """teststep data, each step maybe corresponding to one request or one testcase"""

    success: bool = False   # 是否成功
    name: Text = ""  # teststep name 步骤名称
    data: Union[SessionData, List['StepData']] = None   # 请求数据，包括请求、响应、验证器和stat数据
    export_vars: VariablesMapping = {} # 提取的变量

        
StepData.update_forward_refs()

# 定义测试用例摘要结构体
class TestCaseSummary(BaseModel):
    name: Text
    success: bool
    case_id: Text
    time: TestCaseTime
    in_out: TestCaseInOut = {}
    log: Text = ""
    step_datas: List[StepData] = []

# 定义版本信息结构体
class PlatformInfo(BaseModel):
    httprunner_version: Text
    python_version: Text
    platform: Text

# 定义TestCaseRef结构体
class TestCaseRef(BaseModel):
    name: Text
    base_url: Text = ""
    testcase: Text
    variables: VariablesMapping = {}

# 定义测试套件结构体
class TestSuite(BaseModel):
    config: TConfig
    testcases: List[TestCaseRef]

# 定义统计结构体
class Stat(BaseModel):
    total: int = 0
    success: int = 0
    fail: int = 0


# 定义测试套件摘要结构体
class TestSuiteSummary(BaseModel):
    success: bool = False
    stat: Stat = Stat()
    time: TestCaseTime = TestCaseTime()
    platform: PlatformInfo
    testcases: List[TestCaseSummary]
