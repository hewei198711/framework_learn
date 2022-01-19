import os
import time
import uuid
from datetime import datetime
from typing import List, Dict, Text, NoReturn

try:
    import allure

    USE_ALLURE = True
except ModuleNotFoundError:
    USE_ALLURE = False

from loguru import logger

from httprunner import utils, exceptions
from httprunner.client import HttpSession
from httprunner.exceptions import ValidationFailure, ParamsError
from httprunner.ext.uploader import prepare_upload_step
from httprunner.loader import load_project_meta, load_testcase_file
from httprunner.parser import build_url, parse_data, parse_variables_mapping
from httprunner.response import ResponseObject
from httprunner.testcase import Config, Step
from httprunner.utils import merge_variables
from httprunner.models import (
    TConfig,
    TStep,
    VariablesMapping,
    StepData,
    TestCaseSummary,
    TestCaseTime,
    TestCaseInOut,
    ProjectMeta,
    TestCase,
    Hooks,
)

# httprunner对象
class HttpRunner(object):
    config: Config # 配置对象类
    teststeps: List[Step] # 用例的步骤对象类的list

    success: bool = False  # indicate testcase execution result 指示测试用例执行结果
    __config: TConfig # config结构体
    __teststeps: List[TStep] # 测试步骤step结构体的list
    __project_meta: ProjectMeta = None # 测试的项目元
    __case_id: Text = "" # 用例id
    __export: List[Text] = [] # 导出的变量列表
    __step_datas: List[StepData] = [] # 用例数据结构体的list
    __session: HttpSession = None # 请求会话。
    __session_variables: VariablesMapping = {} # 参数映射
    # time
    __start_at: float = 0 # 开始时间
    __duration: float = 0 # 持续时间
    # log
    __log_path: Text = "" # 日志路径

    # 添加测试步骤
    def __init_tests__(self) -> NoReturn:
        self.__config = self.config.perform()
        self.__teststeps = []
        # 添加测试步骤
        for step in self.teststeps:
            self.__teststeps.append(step.perform())

    @property
    def raw_testcase(self) -> TestCase:
        # 判断是否有“__config”属性
        if not hasattr(self, "__config"):
            self.__init_tests__()
        # 返回测试用例TestCase结构体
        return TestCase(config=self.__config, teststeps=self.__teststeps)

    # 获取项目元
    def with_project_meta(self, project_meta: ProjectMeta) -> "HttpRunner":
        # 获取项目元
        self.__project_meta = project_meta
        return self

    # 获取session
    def with_session(self, session: HttpSession) -> "HttpRunner":
        # 获取session
        self.__session = session
        return self

    # 获取用例id
    def with_case_id(self, case_id: Text) -> "HttpRunner":
        self.__case_id = case_id
        return self

    # 获取变量映射字典
    def with_variables(self, variables: VariablesMapping) -> "HttpRunner":
        self.__session_variables = variables
        return self

    # 导出提取的变量
    def with_export(self, export: List[Text]) -> "HttpRunner":
        self.__export = export
        return self
    # 调用钩子操作
    def __call_hooks(
        self, hooks: Hooks, step_variables: VariablesMapping, hook_msg: Text,
    ) -> NoReturn:
        """ call hook actions. 调用钩子操作

        Args:
            hooks (list): each hook in hooks list maybe in two format.
                          钩子列表中的每个钩子可能有两种格式。
                format1 (str): only call hook functions. 仅调用钩子函数。
                    ${func()}
                format2 (dict): assignment, the value returned by hook function will be assigned to variable.
                                赋值时，钩子函数返回的值将被赋值给变量。
                    {"var": "${func()}"}

            step_variables: current step variables to call hook, include two special variables
                            当前要调用hook的步骤变量，包括两个特殊变量

                request: parsed request dict 解析请求dict
                response: ResponseObject for current response 当前响应的响应对象

            hook_msg: setup/teardown request/testcase

        """
        # 调用钩子操作
        logger.info(f"call hook actions: {hook_msg}")

        # 如果不是列表
        if not isinstance(hooks, List):
            # 无效的钩子格式
            logger.error(f"Invalid hooks format: {hooks}")
            return

        for hook in hooks:
            # 如果是字符串
            if isinstance(hook, Text):
                # format 1: ["${func()}"]
                logger.debug(f"call hook function: {hook}")
                #使用求值变量映射解析原始数据。
                parse_data(hook, step_variables, self.__project_meta.functions)
            elif isinstance(hook, Dict) and len(hook) == 1:
                # format 2: {"var": "${func()}"}
                var_name, hook_content = list(hook.items())[0]
                hook_content_eval = parse_data(
                    hook_content, step_variables, self.__project_meta.functions
                )
                logger.debug(
                    f"call hook function: {hook_content}, got value: {hook_content_eval}"
                )
                logger.debug(f"assign variable: {var_name} = {hook_content_eval}")
                # 使用求值变量映射解析原始数据,并赋值
                step_variables[var_name] = hook_content_eval
            else:
                logger.error(f"Invalid hook format: {hook}")
    # 运行teststep:request，返回请求的数据
    def __run_step_request(self, step: TStep) -> StepData:
        """run teststep: request"""
        # 步骤数据结构体
        step_data = StepData(name=step.name)

        # parse
        # #上传测试的预处理
        prepare_upload_step(step, self.__project_meta.functions)
        # Request的映射
        request_dict = step.request.dict()
        # 移除upload字典
        request_dict.pop("upload", None)
        # 使用求值变量映射解析原始数据。
        parsed_request_dict = parse_data(
            request_dict, step.variables, self.__project_meta.functions
        )
        # 如果HRUN-Request-ID键不存在于字典中，将会添加HRUN-Request-ID键并将值设为默认值。
        parsed_request_dict["headers"].setdefault(
            "HRUN-Request-ID",
            f"HRUN-{self.__case_id}-{str(int(time.time() * 1000))[-6:]}",
        )
        # 将请求字典存入变量映射
        step.variables["request"] = parsed_request_dict

        # setup hooks
        if step.setup_hooks:
            # 执行调用钩子方法
            self.__call_hooks(step.setup_hooks, step.variables, "setup request")

        # prepare arguments
        # 准备请求前的参数
        method = parsed_request_dict.pop("method")
        url_path = parsed_request_dict.pop("url")
        url = build_url(self.__config.base_url, url_path)
        parsed_request_dict["verify"] = self.__config.verify
        parsed_request_dict["json"] = parsed_request_dict.pop("req_json", {})

        # request
        # 请求会话。
        resp = self.__session.request(method, url, **parsed_request_dict)
        # 获取响应对象
        resp_obj = ResponseObject(resp)
        # 将响应对象存入响应字典中
        step.variables["response"] = resp_obj

        # teardown hooks
        # 执行卸载的钩子
        if step.teardown_hooks:
            self.__call_hooks(step.teardown_hooks, step.variables, "teardown request")
        # 日志请求和响应详细信息
        def log_req_resp_details():
            err_msg = "\n{} DETAILED REQUEST & RESPONSE {}\n".format("*" * 32, "*" * 32)

            # log request
            # 请求日志
            err_msg += "====== request details ======\n"
            err_msg += f"url: {url}\n"
            err_msg += f"method: {method}\n"
            headers = parsed_request_dict.pop("headers", {})
            err_msg += f"headers: {headers}\n"
            for k, v in parsed_request_dict.items():
                v = utils.omit_long_data(v)
                err_msg += f"{k}: {repr(v)}\n"

            err_msg += "\n"

            # log response
            # 响应日志
            err_msg += "====== response details ======\n"
            err_msg += f"status_code: {resp.status_code}\n"
            err_msg += f"headers: {resp.headers}\n"
            err_msg += f"body: {repr(resp.text)}\n"
            logger.error(err_msg)

        # extract
        # 提取返回值
        extractors = step.extract
        # 响应值提取后的映射
        extract_mapping = resp_obj.extract(extractors)
        # 测试步骤的data
        step_data.export_vars = extract_mapping

        variables_mapping = step.variables
        # 把提取值更新到变量映射中
        variables_mapping.update(extract_mapping)

        # validate
        # 验证
        validators = step.validators
        session_success = False
        try:
            # 请求响应的验证
            resp_obj.validate(
                validators, variables_mapping, self.__project_meta.functions
            )
            session_success = True
        except ValidationFailure:
            session_success = False
            # 打印错误信息
            log_req_resp_details()
            # log testcase duration before raise ValidationFailure
            # 在raise ValidationFailure之前记录测试用例持续时间
            self.__duration = time.time() - self.__start_at
            raise
        finally:
            self.success = session_success
            step_data.success = session_success

            if hasattr(self.__session, "data"):
                # httprunner.client.HttpSession, not locust.clients.HttpSession
                # httprunner.client.HttpSession, 不是 locust.clients.HttpSession
                # save request & response meta data
                # 保存请求和响应元数据
                self.__session.data.success = session_success
                # 保存响应元数据
                self.__session.data.validators = resp_obj.validation_results

                # save step data
                # 保存请求数据
                step_data.data = self.__session.data
        # 返回请求数据，包含是否成功、请求名称、请求数据、请求提取变量
        return step_data

    # 运行teststep：引用的testcase
    def __run_step_testcase(self, step: TStep) -> StepData:
        """run teststep: referenced testcase"""
        # 定义测试步骤数据结构体
        step_data = StepData(name=step.name)
        # 获取变量
        step_variables = step.variables
        # 导出会话变量
        step_export = step.export

        # setup hooks
        # 执行setup钩子
        if step.setup_hooks:
            self.__call_hooks(step.setup_hooks, step_variables, "setup testcase")

        if hasattr(step.testcase, "config") and hasattr(step.testcase, "teststeps"):
            testcase_cls = step.testcase
            case_result = (
                testcase_cls()
                .with_session(self.__session)
                .with_case_id(self.__case_id)
                .with_variables(step_variables)
                .with_export(step_export)
                .run()
            )

        elif isinstance(step.testcase, Text):
            if os.path.isabs(step.testcase):
                ref_testcase_path = step.testcase
            else:
                ref_testcase_path = os.path.join(
                    self.__project_meta.RootDir, step.testcase
                )

            case_result = (
                HttpRunner()
                .with_session(self.__session)
                .with_case_id(self.__case_id)
                .with_variables(step_variables)
                .with_export(step_export)
                .run_path(ref_testcase_path)
            )

        else:
            raise exceptions.ParamsError(
                f"Invalid teststep referenced testcase: {step.dict()}"
            )

        # teardown hooks
        if step.teardown_hooks:
            self.__call_hooks(step.teardown_hooks, step.variables, "teardown testcase")

        step_data.data = case_result.get_step_datas()  # list of step data
        step_data.export_vars = case_result.get_export_variables()
        
        # 为testcase引用添加额外的validate()

        
        
        step_data.success = case_result.success
        self.success = case_result.success

        if step_data.export_vars:
            logger.info(f"export variables: {step_data.export_vars}")

        
        return step_data

    # 运行teststep，teststep可能是一个请求或引用的testcase
    def __run_step(self, step: TStep) -> Dict:
        """run teststep, teststep maybe a request or referenced testcase"""
        logger.info(f"run step begin: {step.name} >>>>>>")

        if step.request:
            step_data = self.__run_step_request(step)
        elif step.testcase:
            step_data = self.__run_step_testcase(step)
        else:
            raise ParamsError(
                f"teststep is neither a request nor a referenced testcase: {step.dict()}"
            )

        # 把步骤请求数据存入列表
        self.__step_datas.append(step_data)
        logger.info(f"run step end: {step.name} <<<<<<\n")
        # 返回导出提取参数
        return step_data.export_vars

    # 解析配置
    def __parse_config(self, config: TConfig) -> NoReturn:
        # 更新配置
        config.variables.update(self.__session_variables)
        # 解析配置里的变量映射
        config.variables = parse_variables_mapping(
            config.variables, self.__project_meta.functions
        )
        # 解析配置名的原始数据。
        config.name = parse_data(
            config.name, config.variables, self.__project_meta.functions
        )
        # 解析base_url的原始数据
        config.base_url = parse_data(
            config.base_url, config.variables, self.__project_meta.functions
        )

    # 运行指定的测试用例（是在步骤中的）
    def run_testcase(self, testcase: TestCase) -> "HttpRunner":
        """run specified testcase

        Examples:
            >>> testcase_obj = TestCase(config=TConfig(...), teststeps=[TStep(...)])
            >>> HttpRunner().with_project_meta(project_meta).run_testcase(testcase_obj)

        """
        # 获取配置
        self.__config = testcase.config
        # 获取步骤
        self.__teststeps = testcase.teststeps

        # prepare 获取项目元
        self.__project_meta = self.__project_meta or load_project_meta(
            self.__config.path
        )
        # 解析配置
        self.__parse_config(self.__config)
        # 开始时间
        self.__start_at = time.time()
        #步骤数据
        self.__step_datas: List[StepData] = []
        # 请求会话。
        self.__session = self.__session or HttpSession()
        # save extracted variables of teststeps
        # 保存teststeps的提取变量
        extracted_variables: VariablesMapping = {}

        # run teststeps 变量步骤
        for step in self.__teststeps:
            # override variables
            # step variables > extracted variables from previous steps
            # 重写变量
            # 步骤变量>从先前步骤中提取的变量
            step.variables = merge_variables(step.variables, extracted_variables)
            # step variables > testcase config variables
            # 步骤变量>测试用例配置变量
            step.variables = merge_variables(step.variables, self.__config.variables)

            # parse variables
            # 解析变量
            step.variables = parse_variables_mapping(
                step.variables, self.__project_meta.functions
            )

            # run step 运行步骤，判断是否有安装allure
            if USE_ALLURE:
                with allure.step(f"step: {step.name}"):
                    extract_mapping = self.__run_step(step)
            else:
                extract_mapping = self.__run_step(step)

            # save extracted variables to session variables
            # 将提取的变量保存到会话变量
            extracted_variables.update(extract_mapping)
        # 更新变量
        self.__session_variables.update(extracted_variables)
        # 持续时间（响应时间）
        self.__duration = time.time() - self.__start_at
        return self
    # 运行测试用例路径
    def run_path(self, path: Text) -> "HttpRunner":
        if not os.path.isfile(path):
            raise exceptions.ParamsError(f"Invalid testcase path: {path}")
        # 加载测试用例文件
        testcase_obj = load_testcase_file(path)
        return self.run_testcase(testcase_obj)

    # 运行当前测试用例
    def run(self) -> "HttpRunner":
        """ run current testcase
            运行当前测试用例

        Examples:
            >>> TestCaseRequestWithFunctions().run()

        """
        # 添加测试步骤
        self.__init_tests__()
        # 测试用例结构体
        testcase_obj = TestCase(config=self.__config, teststeps=self.__teststeps)
        # 运行测试用例
        return self.run_testcase(testcase_obj)

    # 获取用例请求数据
    def get_step_datas(self) -> List[StepData]:
        return self.__step_datas

    # 使用步骤导出覆盖testcase导出变量
    def get_export_variables(self) -> Dict:
        # override testcase export vars with step export
        # 使用步骤导出覆盖testcase导出变量
        export_var_names = self.__export or self.__config.export
        export_vars_mapping = {}
        for var_name in export_var_names:
            if var_name not in self.__session_variables:
                raise ParamsError(
                    f"failed to export variable {var_name} from session variables {self.__session_variables}"
                )
            # 获取导出变量对应的值
            export_vars_mapping[var_name] = self.__session_variables[var_name]
        # 返回导出变量的映射字典
        return export_vars_mapping
    # 获取测试用例结果摘要
    def get_summary(self) -> TestCaseSummary:
        """get testcase result summary"""
        # 启动时间
        start_at_timestamp = self.__start_at
        # 启动时间用iso格式
        start_at_iso_format = datetime.utcfromtimestamp(start_at_timestamp).isoformat()
        # 返回摘要
        return TestCaseSummary(
            name=self.__config.name,
            success=self.success,
            case_id=self.__case_id,
            time=TestCaseTime(
                start_at=self.__start_at,
                start_at_iso_format=start_at_iso_format,
                duration=self.__duration,
            ),
            in_out=TestCaseInOut(
                config_vars=self.__config.variables,
                export_vars=self.get_export_variables(),
            ),
            log=self.__log_path,
            step_datas=self.__step_datas,
        )

    #主入口，由pytest执行
    def test_start(self, param: Dict = None) -> "HttpRunner":
        """main entrance, discovered by pytest"""
        self.__init_tests__()
        # 获取项目元
        self.__project_meta = self.__project_meta or load_project_meta(
            self.__config.path
        )
        # 获取用例id
        self.__case_id = self.__case_id or str(uuid.uuid4())
        # 获取日志路径
        self.__log_path = self.__log_path or os.path.join(
            self.__project_meta.RootDir, "logs", f"{self.__case_id}.run.log"
        )
        log_handler = logger.add(self.__log_path, level="DEBUG")

        # parse config name
        # 获取测试用例的变量
        config_variables = self.__config.variables
        if param:
            # param的变量更新到config变量中
            config_variables.update(param)
        # session的变量更新到config变量中
        config_variables.update(self.__session_variables)
        # 使用求值变量映射解析原始数据。解析配置名称
        self.__config.name = parse_data(
            self.__config.name, config_variables, self.__project_meta.functions
        )

        if USE_ALLURE:
            # update allure report meta
            # 更新allure报告元数据
            allure.dynamic.title(self.__config.name)
            allure.dynamic.description(f"TestCase ID: {self.__case_id}")

        logger.info(
            f"Start to run testcase: {self.__config.name}, TestCase ID: {self.__case_id}"
        )

        try:
            # 返回运行测试用例
            return self.run_testcase(
                TestCase(config=self.__config, teststeps=self.__teststeps)
            )
        finally:
            # 生成测试用例日志
            logger.remove(log_handler)
            logger.info(f"generate testcase log: {self.__log_path}")
