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


runner = HttpRunner(failfast=args.failfast)