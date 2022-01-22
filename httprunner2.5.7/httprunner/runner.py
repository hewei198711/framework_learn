# encoding: utf-8

from enum import Enum
from unittest.case import SkipTest

from httprunner import exceptions, logger, response, utils
from httprunner.client import HttpSession
from httprunner.context import SessionContext
from httprunner.validator import Validator


class HookTypeEnum(Enum):
    SETUP = 1
    TEARDOWN = 2


class Runner(object):
    """ Running testcases.

    Examples:
        >>> tests_mapping = {
                "project_mapping": {
                    "functions": {}
                },
                "testcases": [
                    {
                        "config": {
                            "name": "XXXX",
                            "base_url": "http://127.0.0.1",
                            "verify": False
                        },
                        "teststeps": [
                            {
                                "name": "test description",
                                "variables": [],        # optional
                                "request": {
                                    "url": "http://127.0.0.1:5000/api/users/1000",
                                    "method": "GET"
                                }
                            }
                        ]
                    }
                ]
            }

        >>> testcases = parser.parse_tests(tests_mapping)
        >>> parsed_testcase = testcases[0]

        >>> test_runner = runner.Runner(parsed_testcase["config"])
        >>> test_runner.run_test(parsed_testcase["teststeps"][0])

    """

    def __init__(self, config, http_client_session=None):
        """ run testcase or testsuite.

        Args:
            config (dict): testcase/testsuite config dict

                {
                    "name": "ABC",
                    "variables": {},
                    "setup_hooks", [],
                    "teardown_hooks", []
                }

            http_client_session (instance): requests.Session(), or locust.client.Session() instance.

        """
        self.verify = config.get("verify", True)
        self.export = config.get("export") or config.get("output", [])
        config_variables = config.get("variables", {})

        # testcase setup hooks
        testcase_setup_hooks = config.get("setup_hooks", [])
        # testcase teardown hooks
        self.testcase_teardown_hooks = config.get("teardown_hooks", [])

        self.http_client_session = http_client_session or HttpSession()
        self.session_context = SessionContext(config_variables)

        if testcase_setup_hooks:
            self.do_hook_actions(testcase_setup_hooks, HookTypeEnum.SETUP)

    def __del__(self): # 对象消失或再无引用时自动调用__del__
        if self.testcase_teardown_hooks:
            self.do_hook_actions(self.testcase_teardown_hooks, HookTypeEnum.TEARDOWN)

    def __clear_test_data(self):
        """ clear request and response data
        """
        if not isinstance(self.http_client_session, HttpSession):
            return

        self.http_client_session.init_meta_data()

    def _handle_skip_feature(self, test_dict):
        """ handle skip feature for test
            - skip: skip current test unconditionally 跳过:无条件测试步骤
            - skipIf: skip current test if condition is true 条件为真时跳过
            - skipUnless: skip current test unless condition is true 条件为假时跳过

        Args:
            test_dict (dict): test info

        Raises:
            SkipTest: skip test

        """
        # TODO: move skip to initialize 移动跳转到初始化
        skip_reason = None

        if "skip" in test_dict:
            skip_reason = test_dict["skip"]

        elif "skipIf" in test_dict:
            skip_if_condition = test_dict["skipIf"]
            if self.session_context.eval_content(skip_if_condition):
                skip_reason = "{} evaluate to True".format(skip_if_condition)

        elif "skipUnless" in test_dict:
            skip_unless_condition = test_dict["skipUnless"]
            if not self.session_context.eval_content(skip_unless_condition):
                skip_reason = "{} evaluate to False".format(skip_unless_condition)

        if skip_reason:
            raise SkipTest(skip_reason)

    def do_hook_actions(self, actions, hook_type):
        """ call hook actions.

        Args:
            actions (list): each action in actions list maybe in two format.动作列表中的每个动作可能有两种格式

                format1 (dict): assignment, the value returned by hook function will be assigned to variable.
                                赋值，钩子函数返回的值将被赋给变量
                    {"var": "${func()}"}
                format2 (str): only call hook functions.只调用钩子函数
                    ${func()}

            hook_type (HookTypeEnum): setup/teardown

        """
        logger.log_debug("call {} hook actions.".format(hook_type.name))
        for action in actions:

            if isinstance(action, dict) and len(action) == 1:
                # format 1
                # {"var": "${func()}"}
                var_name, hook_content = list(action.items())[0]
                hook_content_eval = self.session_context.eval_content(hook_content)
                logger.log_debug(
                    "assignment with hook: {} = {} => {}".format(
                        var_name, hook_content, hook_content_eval
                    )
                )
                self.session_context.update_test_variables(
                    var_name, hook_content_eval
                )
            else:
                # format 2
                logger.log_debug("call hook function: {}".format(action))
                # TODO: check hook function if valid 检查钩函数是否有效
                self.session_context.eval_content(action)

    def _run_test(self, test_dict):
        """ run single teststep. 

        Args:
            test_dict (dict): teststep info
                {
                    "name": "teststep description",
                    "skip": "skip this test unconditionally",
                    "times": 3,
                    "variables": [],            # optional, override 可选的,覆盖
                    "request": {
                        "url": "http://127.0.0.1:5000/api/users/1000",
                        "method": "POST",
                        "headers": {
                            "Content-Type": "application/json",
                            "authorization": "$authorization",
                            "random": "$random"
                        },
                        "json": {"name": "user", "password": "123456"}
                    },
                    "extract": {},              # optional可选的
                    "validate": [],             # optional可选的
                    "setup_hooks": [],          # optional可选的
                    "teardown_hooks": []        # optional可选的
                }

        Raises:
            exceptions.ParamsError 参数错误
            exceptions.ValidationFailure 验证失败
            exceptions.ExtractFailure 提取失败
        
        {
            'api': 'api/架构基础服务/完美运营后台登陆.yml',
            'extract': {'access_token': 'content.data.access_token',
            'token_type': 'content.data.token_type'},
            'name': '前提条件：登录完美运营后台',
            'request': {
                'data': {'data': LazyString(${data}), 'key': LazyString(${key})},
                'headers': {'Authorization': LazyString(Basic ${ENV(Authorization)})},
                'method': 'POST',
                'url': LazyString(${base_url}/login),
                'verify': False
            },
            'validate': [LazyFunction(equals(status_code, 200)),LazyFunction(equals(content.code, 200))],
            'variables': {
                'base_url': LazyString(${ENV(base_url)}),
                'channel': 'op',
                'data': LazyString(${hw_login_rsakey($username, $password, 0, $channel)}),
                'key': LazyString(${hw_login_rsakey($username, $password, 1, $channel)}),
                'maxMonth': '202108',
                'minMonth': '202108',
                'pageNum': 1,
                'pageSize': 10,
                'password': LazyString(${ENV(password)}),
                'storeCode': '920111',
                'username': LazyString(${ENV(username)})
            }
        }
        
        {
            'api': 'api\\mgmt\\服务中心电子合同\\查询已月结服务中心.yml',
            'extract': {},
            'name': LazyString(查询已月结服务中心：成功路径-搜索服务中心编号${storeCode},月份${minMonth}检查),
            'request': {
                'headers': {'Authorization': LazyString(${token_type} ${access_token})},
                'method': 'GET',
                'params': {
                    'companyCode': LazyString(${companyCode}),
                    'maxMonth': LazyString(${maxMonth}),
                    'minMonth': LazyString(${minMonth}),
                    'pageNum': LazyString(${pageNum}),
                    'pageSize': LazyString(${pageSize}),
                    'storeCode': LazyString(${storeCode})
                },
                'url': LazyString(${base_url}/mgmt/inventory/bill/settled-store),
                'verify': False
            },
            'validate': [
                LazyFunction(equals(status_code, 200)),
                LazyFunction(equals(content.data.list.0.storeCode, LazyString(${storeCode}))),
                LazyFunction(equals(content.data.total, 1)),
                LazyFunction(equals(content.data.totalPage, 1))
            ],
            'variables': {
                'access_token': LazyString(${ENV(access_token)}),
                'base_url': LazyString(${ENV(base_url)}),
                'companyCode': '',
                'maxMonth': '202108',
                'minMonth': '202108',
                'pageNum': 1,
                'pageSize': 10,
                'storeCode': '920111',
                'token_type': LazyString(${ENV(token_type)})
            }
        }
        
        {
            'api': 'api\\mgmt\\服务中心电子合同\\查询已月结服务中心.yml',
            'extract': {},
            'name': LazyString(查询已月结服务中心：成功路径-搜索服务中心编号${storeCode},月份${minMonth}检查),
            'request': {
                'headers': {'Authorization': LazyString(${token_type} ${access_token})},
                'method': 'GET',
                'params': {
                    'companyCode': LazyString(${companyCode}),
                    'maxMonth': LazyString(${maxMonth}),
                    'minMonth': LazyString(${minMonth}),
                    'pageNum': LazyString(${pageNum}),
                    'pageSize': LazyString(${pageSize}),
                    'storeCode': LazyString(${storeCode})
                },
                'url': LazyString(${base_url}/mgmt/inventory/bill/settled-store),
                'verify': False
            },
            'validate': [
                LazyFunction(equals(status_code, 200)),
                LazyFunction(equals(content.data.list.0.storeCode, LazyString(${storeCode}))),
                LazyFunction(equals(content.data.total, 1)),
                LazyFunction(equals(content.data.totalPage, 1))
            ],
            'variables': {
                'access_token': LazyString(${ENV(access_token)}),
                'base_url': LazyString(${ENV(base_url)}),
                'companyCode': '',
                'maxMonth': '202108',
                'minMonth': '202108',
                'pageNum': 1,
                'pageSize': 10,
                'storeCode': '920111',
                'token_type': LazyString(${ENV(token_type)})
            }
        }

        """
        # clear meta data first to ensure independence for each test 首先清除元数据，确保每个测试的独立性
        self.__clear_test_data()

        # check skip 检查跳过
        self._handle_skip_feature(test_dict)

        # prepare 准备参数
        test_dict = utils.lower_test_dict_keys(test_dict)
        test_variables = test_dict.get("variables", {})
        self.session_context.init_test_variables(test_variables)

        # teststep name
        test_name = self.session_context.eval_content(test_dict.get("name", ""))

        # parse test request
        raw_request = test_dict.get('request', {})
        parsed_test_request = self.session_context.eval_content(raw_request)
        self.session_context.update_test_variables("request", parsed_test_request)

        # setup hooks
        setup_hooks = test_dict.get("setup_hooks", [])
        if setup_hooks:
            self.do_hook_actions(setup_hooks, HookTypeEnum.SETUP)

        # prepend url with base_url unless it's already an absolute URL 在url前面加上base_url，除非它已经是一个绝对url
        url = parsed_test_request.pop('url')
        base_url = self.session_context.eval_content(test_dict.get("base_url", ""))
        parsed_url = utils.build_url(base_url, url)

        try:
            method = parsed_test_request.pop('method')
            parsed_test_request.setdefault("verify", self.verify)
            group_name = parsed_test_request.pop("group", None)
        except KeyError:
            raise exceptions.ParamsError("URL or METHOD missed!")

        logger.log_info("{method} {url}".format(method=method, url=parsed_url))
        logger.log_debug(
            "request kwargs(raw): {kwargs}".format(kwargs=parsed_test_request))

        # request
        resp = self.http_client_session.request(
            method,
            parsed_url,
            name=(group_name or test_name),
            **parsed_test_request
        )
        resp_obj = response.ResponseObject(resp)

        def log_req_resp_details():
            err_msg = "{} DETAILED REQUEST & RESPONSE {}\n".format("*" * 32, "*" * 32)

            # log request
            err_msg += "====== request details ======\n"
            err_msg += "url: {}\n".format(parsed_url)
            err_msg += "method: {}\n".format(method)
            err_msg += "headers: {}\n".format(parsed_test_request.pop("headers", {}))
            for k, v in parsed_test_request.items():
                v = utils.omit_long_data(v)
                err_msg += "{}: {}\n".format(k, repr(v))

            err_msg += "\n"

            # log response
            err_msg += "====== response details ======\n"
            err_msg += "status_code: {}\n".format(resp_obj.status_code)
            err_msg += "headers: {}\n".format(resp_obj.headers)
            err_msg += "body: {}\n".format(repr(resp_obj.text))
            logger.log_error(err_msg)

        # teardown hooks
        teardown_hooks = test_dict.get("teardown_hooks", [])
        if teardown_hooks:
            self.session_context.update_test_variables("response", resp_obj)
            self.do_hook_actions(teardown_hooks, HookTypeEnum.TEARDOWN)
            self.http_client_session.update_last_req_resp_record(resp_obj)

        # extract
        extractors = test_dict.get("extract", {})
        try:
            extracted_variables_mapping = resp_obj.extract_response(extractors)
            self.session_context.update_session_variables(extracted_variables_mapping)
        except (exceptions.ParamsError, exceptions.ExtractFailure): #Extract Failure提取失败
            log_req_resp_details()
            raise

        # validate
        validators = test_dict.get("validate") or test_dict.get("validators") or []
        validate_script = test_dict.get("validate_script", [])
        if validate_script:
            validators.append({
                "type": "python_script",
                "script": validate_script
            })

        validator = Validator(self.session_context, resp_obj)
        try:
            validator.validate(validators)
        except exceptions.ValidationFailure:
            log_req_resp_details()
            raise
        finally:
            self.validation_results = validator.validation_results

    def _run_testcase(self, testcase_dict):
        """ 
        run single testcase.
        testcases\服务中心管理\对账单管理\调试.yml
        {
            'config': {
                'base_url': '',
                'name': '前提条件：登录完美运营后台',
                'output': ['access_token', 'token_type'],
                'testcase': 'testcases\\服务中心管理\\对账单管理\\查询已月结服务中心：服务中心编号搜索功能检查.yml',
                'variables': {
                    'maxMonth': '202108',
                    'minMonth': '202108',
                    'pageNum': 1,
                    'pageSize': 10,
                    'storeCode': '920111'
                    },
                'verify': False
            },
            'teststeps': [
                {
                    'api': 'api/架构基础服务/完美运营后台登陆.yml',
                    'extract': {
                        'access_token': 'content.data.access_token',
                        'token_type': 'content.data.token_type'
                    },
                    'name': '前提条件：登录完美运营后台',
                    'request': {
                        'data': {'data': LazyString(${data}),'key': LazyString(${key})},
                        'headers': {'Authorization': LazyString(Basic ${ENV(Authorization)})},
                        'method': 'POST',
                        'url': LazyString(${base_url}/login),
                        'verify': False
                    },
                    'validate': [LazyFunction(equals(status_code, 200)),LazyFunction(equals(content.code, 200))],
                    'variables': {
                        'base_url': LazyString(${ENV(base_url)}),
                        'channel': 'op',
                        'data': LazyString(${hw_login_rsakey($username, $password, 0, $channel)}),
                        'key': LazyString(${hw_login_rsakey($username, $password, 1, $channel)}),
                        'maxMonth': '202108',
                        'minMonth': '202108',
                        'pageNum': 1,
                        'pageSize': 10,
                        'password': LazyString(${ENV(password)}),
                        'storeCode': '920111',
                        'username': LazyString(${ENV(username)})
                    }
                },
               {
                    'api': 'api\\mgmt\\服务中心电子合同\\查询已月结服务中心.yml',
                    'extract': {},
                    'name': LazyString(查询已月结服务中心：成功路径-搜索服务中心编号${storeCode},月份${minMonth}检查),
                    'request': {
                        'headers': {'Authorization': LazyString(${token_type} ${access_token})},
                        'method': 'GET',
                        'params': {
                            'companyCode': LazyString(${companyCode}),
                            'maxMonth': LazyString(${maxMonth}),
                            'minMonth': LazyString(${minMonth}),
                            'pageNum': LazyString(${pageNum}),
                            'pageSize': LazyString(${pageSize}),
                            'storeCode': LazyString(${storeCode})
                        },
                        'url': LazyString(${base_url}/mgmt/inventory/bill/settled-store),
                        'verify': False
                    },
                    'validate': [LazyFunction(equals(status_code, 200)),
                                LazyFunction(equals(content.data.list.0.storeCode, LazyString(${storeCode}))),
                                LazyFunction(equals(content.data.total, 1)),
                                LazyFunction(equals(content.data.totalPage, 1))],
                    'variables': {
                        'access_token': LazyString(${ENV(access_token)}),
                        'base_url': LazyString(${ENV(base_url)}),
                        'companyCode': '',
                        'maxMonth': '202108',
                        'minMonth': '202108',
                        'pageNum': 1,
                        'pageSize': 10,
                        'storeCode': '920111',
                        'token_type': LazyString(${ENV(token_type)})
                    }
                }
            ],
            'validate': []
        }
        """
        self.meta_datas = []
        config = testcase_dict.get("config", {})

        # each teststeps in one testcase (YAML/JSON) share the same session.一个testcase (YAML/JSON)中的每个测试步骤共享相同的会话。
        test_runner = Runner(config, self.http_client_session)

        tests = testcase_dict.get("teststeps", [])

        for index, test_dict in enumerate(tests):

            # override current teststep variables with former testcase output variables 用以前的testcase输出变量重写当前的teststep变量
            former_output_variables = self.session_context.test_variables_mapping
            if former_output_variables:
                test_dict.setdefault("variables", {})
                test_dict["variables"].update(former_output_variables)

            try:
                test_runner.run_test(test_dict)
            except Exception:
                # log exception request_type and name for locust stat 日志异常request_type和locust stat的名称
                self.exception_request_type = test_runner.exception_request_type
                self.exception_name = test_runner.exception_name
                raise
            finally:
                _meta_datas = test_runner.meta_datas
                self.meta_datas.append(_meta_datas)

        self.session_context.update_session_variables(
            test_runner.export_variables(test_runner.export)
        )

    def run_test(self, test_dict):
        """ run single teststep of testcase.
            test_dict may be in 3 types.可分为三种类型

        Args:
            test_dict (dict):

                # teststep
                {
                    "name": "teststep description",
                    "variables": [],        # optional
                    "request": {
                        "url": "http://127.0.0.1:5000/api/users/1000",
                        "method": "GET"
                    }
                }

                # nested testcase 嵌套测试用例
                {
                    "config": {...},
                    "teststeps": [
                        {...},
                        {...}
                    ]
                }

                # TODO: function
                {
                    "name": "exec function",
                    "function": "${func()}"
                }
        """

        """
         teststep: 第一       
        {
            'config': {
                'base_url': '',
                'name': '前提条件：登录完美运营后台',
                'output': ['access_token', 'token_type'],
                'testcase': 'testcases\\服务中心管理\\对账单管理\\查询已月结服务中心：服务中心编号搜索功能检查.yml',
                'variables': {
                    'maxMonth': '202108',
                    'minMonth': '202108',
                    'pageNum': 1,
                    'pageSize': 10,
                    'storeCode': '920111'
                },
                'verify': False
            },
            'teststeps': [
                {
                    'api': 'api/架构基础服务/完美运营后台登陆.yml',
                    'extract': {'access_token': 'content.data.access_token','token_type': 'content.data.token_type'},
                    'name': '前提条件：登录完美运营后台',
                    'request': {
                        'data': {'data': LazyString(${data}),'key': LazyString(${key})},
                        'headers': {'Authorization': LazyString(Basic ${ENV(Authorization)})},
                        'method': 'POST',
                        'url': LazyString(${base_url}/login),
                        'verify': False
                    },
                    'validate': [LazyFunction(equals(status_code, 200)),LazyFunction(equals(content.code, 200))],
                    'variables': {
                        'base_url': LazyString(${ENV(base_url)}),
                        'channel': 'op',
                        'data': LazyString(${hw_login_rsakey($username, $password, 0, $channel)}),
                        'key': LazyString(${hw_login_rsakey($username, $password, 1, $channel)}),
                        'maxMonth': '202108',
                        'minMonth': '202108',
                        'pageNum': 1,
                        'pageSize': 10,
                        'password': LazyString(${ENV(password)}),
                        'storeCode': '920111',
                        'username': LazyString(${ENV(username)})
                    }
                },
                {
                    'api': 'api\\mgmt\\服务中心电子合同\\查询已月结服务中心.yml',
                    'extract': {},
                    'name': LazyString(查询已月结服务中心：成功路径-搜索服务中心编号${storeCode},月份${minMonth}检查),
                    'request': {
                        'headers': {'Authorization': LazyString(${token_type} ${access_token})},
                        'method': 'GET',
                        'params': {
                            'companyCode': LazyString(${companyCode}),
                            'maxMonth': LazyString(${maxMonth}),
                            'minMonth': LazyString(${minMonth}),
                            'pageNum': LazyString(${pageNum}),
                            'pageSize': LazyString(${pageSize}),
                            'storeCode': LazyString(${storeCode})
                        },
                        'url': LazyString(${base_url}/mgmt/inventory/bill/settled-store),
                        'verify': False
                    },
                    'validate': [
                        LazyFunction(equals(status_code, 200)),
                        LazyFunction(equals(content.data.list.0.storeCode, LazyString(${storeCode}))),
                        LazyFunction(equals(content.data.total, 1)),
                        LazyFunction(equals(content.data.totalPage, 1))
                    ],
                    'variables': {
                        'access_token': LazyString(${ENV(access_token)}),
                        'base_url': LazyString(${ENV(base_url)}),
                        'companyCode': '',
                        'maxMonth': '202108',
                        'minMonth': '202108',
                        'pageNum': 1,
                        'pageSize': 10,
                        'storeCode': '920111',
                        'token_type': LazyString(${ENV(token_type)})
                    }
                }
            ],
            'validate': []
        }
        """
        
        """
        teststep: 第一的第一步
        {
            'api': 'api/架构基础服务/完美运营后台登陆.yml',
            'extract': {'access_token': 'content.data.access_token','token_type': 'content.data.token_type'},
            'name': '前提条件：登录完美运营后台',
            'request': {
                'data': {'data': LazyString(${data}), 'key': LazyString(${key})},
                'headers': {'Authorization': LazyString(Basic ${ENV(Authorization)})},
                'method': 'POST',
                'url': LazyString(${base_url}/login),
                'verify': False
            },
            'validate': [LazyFunction(equals(status_code, 200)),LazyFunction(equals(content.code, 200))],
            'variables': {
                'base_url': LazyString(${ENV(base_url)}),
                'channel': 'op',
                'data': LazyString(${hw_login_rsakey($username, $password, 0, $channel)}),
                'key': LazyString(${hw_login_rsakey($username, $password, 1, $channel)}),
                'maxMonth': '202108',
                'minMonth': '202108',
                'pageNum': 1,
                'pageSize': 10,
                'password': LazyString(${ENV(password)}),
                'storeCode': '920111',
                'username': LazyString(${ENV(username)})
            }
        }
        """
        
        """
        teststep: 第一的第二步
        {
            'api': 'api\\mgmt\\服务中心电子合同\\查询已月结服务中心.yml',
            'extract': {},
            'name': LazyString(查询已月结服务中心：成功路径-搜索服务中心编号${storeCode},月份${minMonth}检查),
            'request': {
                'headers': {'Authorization': LazyString(${token_type} ${access_token})},
                'method': 'GET',
                'params': {
                    'companyCode': LazyString(${companyCode}),
                    'maxMonth': LazyString(${maxMonth}),
                    'minMonth': LazyString(${minMonth}),
                    'pageNum': LazyString(${pageNum}),
                    'pageSize': LazyString(${pageSize}),
                    'storeCode': LazyString(${storeCode})
                },
                'url': LazyString(${base_url}/mgmt/inventory/bill/settled-store),
                'verify': False
            },
            'validate': [
                LazyFunction(equals(status_code, 200)),
                LazyFunction(equals(content.data.list.0.storeCode, LazyString(${storeCode}))),
                LazyFunction(equals(content.data.total, 1)),
                LazyFunction(equals(content.data.totalPage, 1))
            ],
            'variables': {
                'access_token': LazyString(${ENV(access_token)}),
                'base_url': LazyString(${ENV(base_url)}),
                'companyCode': '',
                'maxMonth': '202108',
                'minMonth': '202108',
                'pageNum': 1,
                'pageSize': 10,
                'storeCode': '920111',
                'token_type': LazyString(${ENV(token_type)})
            }
        }
        """
        
        """
        teststep: 第二
        {
            'api': 'api\\mgmt\\服务中心电子合同\\查询已月结服务中心.yml',
            'extract': {},
            'name': LazyString(查询已月结服务中心：成功路径-搜索服务中心编号${storeCode},月份${minMonth}检查),
            'request': {
                'headers': {'Authorization': LazyString(${token_type} ${access_token})},
                'method': 'GET',
                'params': {
                    'companyCode': LazyString(${companyCode}),
                    'maxMonth': LazyString(${maxMonth}),
                    'minMonth': LazyString(${minMonth}),
                    'pageNum': LazyString(${pageNum}),
                    'pageSize': LazyString(${pageSize}),
                    'storeCode': LazyString(${storeCode})
                },
                'url': LazyString(${base_url}/mgmt/inventory/bill/settled-store),
                'verify': False
            },
            'validate': [
                LazyFunction(equals(status_code, 200)),
                LazyFunction(equals(content.data.list.0.storeCode, LazyString(${storeCode}))),
                LazyFunction(equals(content.data.total, 1)),
                LazyFunction(equals(content.data.totalPage, 1))
            ],
            'variables': {
                'access_token': LazyString(${ENV(access_token)}),
                'base_url': LazyString(${ENV(base_url)}),
                'companyCode': '',
                'maxMonth': '202108',
                'minMonth': '202108',
                'pageNum': 1,
                'pageSize': 10,
                'storeCode': '920111',
                'token_type': LazyString(${ENV(token_type)})
            }
        }
        """
        self.meta_datas = None
        if "teststeps" in test_dict:
            # nested testcase 嵌套的testcase
            test_dict.setdefault("config", {}).setdefault("variables", {})
            test_dict["config"]["variables"].update(
                self.session_context.session_variables_mapping)
            self._run_testcase(test_dict)
        else:
            # api
            self.validation_results = {}
            try:
                self._run_test(test_dict)
            except Exception:
                # log exception request_type and name for locust stat 日志异常request_type和locust stat的名称
                self.exception_request_type = test_dict["request"]["method"]
                self.exception_name = test_dict.get("name")
                raise
            finally:
                # get request/response data and validate results 获取请求/响应数据并验证结果
                self.meta_datas = getattr(self.http_client_session, "meta_data", {})
                self.meta_datas["validators"] = self.validation_results

    def export_variables(self, output_variables_list):
        """ export current testcase variables 导出当前的testcase变量
        """
        variables_mapping = self.session_context.session_variables_mapping

        output = {}
        for variable in output_variables_list:
            if variable not in variables_mapping:
                logger.log_warning(
                    "variable '{}' can not be found in variables mapping, "
                    "failed to export!".format(variable)
                )
                continue

            output[variable] = variables_mapping[variable]

        utils.print_info(output)
        return output
