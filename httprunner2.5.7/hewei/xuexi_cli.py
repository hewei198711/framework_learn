import argparse
import os
import sys

import sentry_sdk

from httprunner import __description__, __version__, exceptions
from httprunner.api import HttpRunner
from httprunner.compat import is_py2
from httprunner.loader import load_cases
from httprunner.logger import color_print, log_error
from httprunner.report import gen_html_report
from httprunner.utils import (create_scaffold, get_python2_retire_msg,
                              prettify_json_file, init_sentry_sdk)


# parser = argparse.ArgumentParser(description=__description__)
# parser.add_argument("-V", "--version", dest="version", action="store_true",
#                     help="show version")


parser = argparse.ArgumentParser(description="我是何伟的命令行参数")
parser.add_argument(
    "hewei_path", nargs="*",
    help="我是何伟的位置参数")
parser.add_argument(
    "-v", "--version", dest="version", action="store_true",
    help="hewei de version"
)
args = parser.parse_args()
print(args)
print(args.hewei_path)
print(args.version)
