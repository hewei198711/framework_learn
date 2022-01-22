# -*- coding: utf-8 -*-

from httprunner.api import HttpRunner, report


runner = HttpRunner(
    failfast=True,
    save_tests=True,
    log_level="DEBUG",
    log_file=r"logs/test.log"
)
  

summary = runner.run("httprunner2.5.7\调试.yml")
report.gen_html_report(
    summary,
    report_dir="httprunner2.5.7/reports"
)