import os
import unittest

from sentry_sdk import capture_message

from httprunner import (__version__, exceptions, loader, logger, parser,
                        report, runner, utils)


class HttpRunner(object):
    """ Developer Interface: Main Interface 开发者界面:主界面
        Usage:

            from httprunner.api import HttpRunner
            runner = HttpRunner(
                failfast=True, 
                save_tests=True, 
                log_level="INFO",
                log_file="test.log"
            )
            summary = runner.run(path_or_tests) 

    """

    def __init__(self, failfast=False, save_tests=False, log_level="WARNING", log_file=None):
        """ initialize HttpRunner.

        Args:
            failfast (bool): stop the test run on the first error or failure. 
            save_tests (bool): save loaded/parsed tests to JSON file. 
            log_level (str): logging level. 
            log_file (str): log file path. 

        """
        logger.setup_logger(log_level, log_file)

        self.exception_stage = "initialize HttpRunner()"  #异常阶段
        kwargs = {
            "failfast": failfast,
            "resultclass": report.HtmlTestResult  #结果类
        }
        self.unittest_runner = unittest.TextTestRunner(**kwargs)
        self.test_loader = unittest.TestLoader()
        self.save_tests = save_tests
        self._summary = None
        self.project_working_directory = None #目录

    def _add_tests(self, testcases):
        """ initialize testcase with Runner() and add to test suite.

        Args:
            testcases (list): testcases list.

        Returns:
            unittest.TestSuite()
        """

        def _add_test(test_runner, test_dict):
            """ 
            add test to testcase. 
            """

            def test(self):
                try:
                    test_runner.run_test(test_dict)
                except exceptions.MyBaseFailure as ex:
                    self.fail(str(ex))
                finally:
                    self.meta_datas = test_runner.meta_datas

            if "config" in test_dict:
                # run nested testcase 
                test.__doc__ = test_dict["config"].get("name")
                variables = test_dict["config"].get("variables", {})
            else:
                # run api test
                test.__doc__ = test_dict.get("name")
                variables = test_dict.get("variables", {})

            if isinstance(test.__doc__, parser.LazyString):

                try:
                    parsed_variables = parser.parse_variables_mapping(variables)  # 所有的变量字典
                    test.__doc__ = parser.parse_lazy_data(  # 找到引用变量对应的值
                        test.__doc__, parsed_variables
                    )
                except exceptions.VariableNotFound:
                    test.__doc__ = str(test.__doc__)
            return test

        test_suite = unittest.TestSuite()
        for testcase in testcases:
            config = testcase.get("config", {})
            test_runner = runner.Runner(config)
            TestSequense = type('TestSequense', (unittest.TestCase,), {}) 
            tests = testcase.get("teststeps", [])

            for index, test_dict in enumerate(tests):  # 遍历测试步骤
                times = test_dict.get("times", 1)

                try:
                    times = int(times)
                except ValueError:
                    raise exceptions.ParamsError(
                        "times should be digit, given: {}".format(times))

                for times_index in range(times):
                    # suppose one testcase should not have more than 9999 steps,
                    # and one step should not run more than 999 times.
                    test_method_name = 'test_{:04}_{:03}'.format(index, times_index)
                    test_method = _add_test(test_runner, test_dict)
                    setattr(TestSequense, test_method_name, test_method)

            loaded_testcase = self.test_loader.loadTestsFromTestCase(TestSequense)  # 加载测试用例到用例集（小集：测试用例）

            setattr(loaded_testcase, "config", config)  # 加载属性到用例集（小集：测试用例）

            setattr(loaded_testcase, "teststeps", tests)  # 加载属性到用例集（小集：测试用例）

            setattr(loaded_testcase, "runner", test_runner)  # 加载运行方法到用例集（小集：测试用例）

            test_suite.addTest(loaded_testcase)  # 加载用例集（小集：测试用例）到大用例集

        return test_suite

    def _run_suite(self, test_suite):
        """ 运行测试套件

        Args:
            test_suite: unittest.TestSuite()

        Returns:
            list: tests_results测试结果

        """
        tests_results = []

        for testcase in test_suite:  # 遍历用例集中的每一个用例
            testcase_name = testcase.config.get("name")
            logger.log_info("Start to run testcase: {}".format(testcase_name))

            result = self.unittest_runner.run(testcase)
            if result.wasSuccessful():
                tests_results.append((testcase, result))
            else:
                tests_results.insert(0, (testcase, result))

        return tests_results

    def _aggregate(self, tests_results):
        """ 测试结果总数据

        Args:
            tests_results (list): list of (testcase, result)

        """
        summary = {
            "success": True,
            "stat": {  #合计
                "testcases": {
                    "total": len(tests_results),
                    "success": 0,
                    "fail": 0
                },
                "teststeps": {}
            },
            "time": {},
            "platform": report.get_platform(),
            "details": []  #详情
        }

        for tests_result in tests_results:
            testcase, result = tests_result
            testcase_summary = report.get_summary(result)

            if testcase_summary["success"]:
                summary["stat"]["testcases"]["success"] += 1
            else:
                summary["stat"]["testcases"]["fail"] += 1

            summary["success"] &= testcase_summary["success"]
            testcase_summary["name"] = testcase.config.get("name")
            testcase_summary["in_out"] = utils.get_testcase_io(testcase)

            report.aggregate_stat(summary["stat"]["teststeps"], testcase_summary["stat"])
            report.aggregate_stat(summary["time"], testcase_summary["time"])

            summary["details"].append(testcase_summary)

        return summary

    def run_tests(self, tests_mapping):
        """
        run testcase/testsuite data
        project_mapping = {
            "env": {"username": "hewei1987","password": "888888"},
            "PWD": "D:\\git_ligeit\\test_ucong",
            "functions": {},
            "test_path": "D:\\git_ligeit\\test_ucong\\api\\财务管理\\服务中心银行流水\\汇款.yml"
            }
        parsed_testcases = [
            {
                "config":{
                    "name":"/mgmt/store/checkBusinessAddressIsExist"
                },
                "teststeps":[
                    {
                        "name":"/mgmt/store/checkBusinessAddressIsExist",
                        "request":{
                            "headers":{
                                "Authorization":"LazyString(${token_type} ${access_token})"
                            },
                            "method":"GET",
                            "params":{
                                "provinceName":"LazyString(${provinceName})",
                                "cityName":"LazyString(${cityName})",
                                "areaName":"LazyString(${areaName})",
                                "streetName":"LazyString(${streetName})",
                                "detailAddress":"LazyString(${detailAddress})"
                            },
                            "url":"LazyString(${base_url}/mgmt/store/checkBusinessAddressIsExist)",
                            "verify":true
                        },
                        "variables":{
                            "provinceName":"广东省",
                            "cityName":"广州市",
                            "areaName":"海珠区",
                            "streetName":"南州街道",
                            "detailAddress":"广州市海珠区南洲街道新滘中路88号唯品同创汇6区东三街17号自编23号",
                            "access_token":"LazyString(${ENV(access_token)})",
                            "token_type":"LazyString(${ENV(token_type)})",
                            "base_url":"LazyString(${ENV(base_url)})"
                        },
                        "validate":[
                            "LazyFunction(equals(status_code, 200))"
                        ]
                    }
                ]
            }
        ]
        """
        capture_message("start to run tests")
        project_mapping = tests_mapping.get("project_mapping", {})
        self.project_working_directory = project_mapping.get("PWD", os.getcwd())  #项目工作目录

        if self.save_tests:
            utils.dump_logs(tests_mapping, project_mapping, "loaded")  #转储日志

        # parse tests
        self.exception_stage = "parse tests"
        # 用测试用例抽出来（变量已经按优先级处理正确），剩下LazyString(${token_type} ${access_token})未解析
        parsed_testcases = parser.parse_tests(tests_mapping)
        parse_failed_testfiles = parser.get_parse_failed_testfiles()
        if parse_failed_testfiles:
            logger.log_warning("parse failures occurred ...")
            utils.dump_logs(parse_failed_testfiles, project_mapping, "parse_failed")

        if len(parsed_testcases) == 0:
            logger.log_error("failed to parse all cases, abort.")
            raise exceptions.ParseTestsFailure

        if self.save_tests:
            utils.dump_logs(parsed_testcases, project_mapping, "parsed")

        # add tests to test suite
        self.exception_stage = "add tests to test suite"
        # <unittest.suite.TestSuite tests=
        # [<unittest.suite.TestSuite tests=[<httprunner.api.TestSequense testMethod=test_0000_000>]>]>
        test_suite = self._add_tests(parsed_testcases)

        # run test suite
        self.exception_stage = "run test suite"
        results = self._run_suite(test_suite)

        # aggregate results总结果
        self.exception_stage = "aggregate results"
        self._summary = self._aggregate(results)

        # generate html report
        self.exception_stage = "generate html report"
        report.stringify_summary(self._summary)

        if self.save_tests:
            utils.dump_logs(self._summary, project_mapping, "summary")
            # save variables and export data保存变量和导出数据
            vars_out = self.get_vars_out()
            utils.dump_logs(vars_out, project_mapping, "io")

        return self._summary

    def get_vars_out(self):
        """ get variables and output
        Returns:
            list: list of variables and output.
                if tests are parameterized, list items are corresponded to parameters.
                如果测试被参数化，则列表项对应于参数。

                [
                    {
                        "in": {
                            "user1": "leo"
                        },
                        "out": {
                            "out1": "out_value_1"
                        }
                    },
                    {...}
                ]

            None: returns None if tests not started or finished or corrupted.
            如果测试未启动、未完成或损坏，则返回None。

        """
        if not self._summary:
            return None

        return [
            summary["in_out"]
            for summary in self._summary["details"]
        ]

    def run_path(self, path, dot_env_path=None, mapping=None):
        """ run testcase/testsuite file or folder.

        Args:
            path (str): testcase/testsuite file/foler path.
            dot_env_path (str): specified .env file path.
            mapping (dict): if mapping is specified, it will override variables in config block.

        Returns:
            dict: result summary

        """
        # load tests
        self.exception_stage = "load tests"
        tests_mapping = loader.load_cases(path, dot_env_path)

        if mapping:
            tests_mapping["project_mapping"]["variables"] = mapping

        return self.run_tests(tests_mapping)

    def run(self, path_or_tests, dot_env_path=None, mapping=None):
        """ main interface. 主界面

        Args:
            path_or_tests:
                str: testcase/testsuite file/foler path
                dict: valid testcase/testsuite data
            dot_env_path (str): specified .env file path.
            mapping (dict): if mapping is specified, it will override variables in config block.
             如果指定了映射，它将覆盖配置块中的变量。

        Returns:
            dict: result summary

        """
        logger.log_info("HttpRunner version: {}".format(__version__))
        if loader.is_test_path(path_or_tests):
            return self.run_path(path_or_tests, dot_env_path, mapping)
        elif loader.is_test_content(path_or_tests):
            project_working_directory = path_or_tests.get("project_mapping", {}).get("PWD", os.getcwd())
            loader.init_pwd(project_working_directory)
            return self.run_tests(path_or_tests)
        else:
            raise exceptions.ParamsError("Invalid testcase path or testcases: {}".format(path_or_tests)) 