"""
HttpRunner report

- summarize: aggregate test stat data to summary汇总:将测试数据汇总为汇总
- stringify: stringify summary, in order to dump json file and generate html report.摘要，以便转储json文件和生成html报告。
- html: render html report渲染html报告
"""

from httprunner.report.summarize import get_platform, aggregate_stat, get_summary
from httprunner.report.stringify import stringify_summary
from httprunner.report.html import HtmlTestResult, gen_html_report

__all__ = [
    "get_platform",
    "aggregate_stat",
    "get_summary",
    "stringify_summary",
    "HtmlTestResult",
    "gen_html_report"
]
