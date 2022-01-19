"""
Built-in functions used in YAML/JSON testcases.
内置在YAML/JSON测试用例中使用的函数。
"""

import datetime
import random
import string
import time

from httprunner.compat import builtin_str, integer_types
from httprunner.exceptions import ParamsError


def gen_random_string(str_len):
    """ generate random string with specified length
    """
    return ''.join(
        random.choice(string.ascii_letters + string.digits) for _ in range(str_len))


def get_timestamp(str_len=13):
    """ get timestamp string, length can only between 0 and 16
        获取时间戳字符串，长度只能在0到16之间
    """
    if isinstance(str_len, integer_types) and 0 < str_len < 17:
        return builtin_str(time.time()).replace(".", "")[:str_len]

    raise ParamsError("timestamp length can only between 0 and 16.")


def get_current_date(fmt="%Y-%m-%d"):
    """ get current date, default format is %Y-%m-%d
        获取当前日期，默认格式为%Y-%m-%d
    """
    return datetime.datetime.now().strftime(fmt)


def sleep(n_secs):
    """ sleep n seconds睡眠n秒
    """
    time.sleep(n_secs)

