# -*- coding: utf-8 -*-

from httprunner.api import HttpRunner, report
from httprunner.loader.locate import project_working_directory


"""
loaded
    project_mapping
        env
        PWD
        functions
        test_path
    testcases
        config
        teststeps
            name***
            testcase
            !testcase_def
                config
                teststeps
                    name***
                    api
                    !api_def
                        name
                        request
                        variables
                        validate
            name***
            api
            !api_def
                name
                request
                ***
"""

runner = HttpRunner(
    failfast=True,
    save_tests=True,
    log_level="DEBUG",
    log_file=r"httprunner2.5.7/logs/test.log"
)
  

summary = runner.run("httprunner2.5.7\调试集合.yml")

report.gen_html_report(
    summary,
    report_dir="httprunner2.5.7/reports"
)