"""
内置再测试用例中使用的函数
"""

import datetime
import random
import string
import time

from prettyprinter import pprint

from httprunner.compat import builtin_str, integer_types
from httprunner.exceptions import ParamsError


def gen_random_string(str_len):
    """
    生成指定长度的随机字符串
    :param str_len:10
    :return:'Y96ZBTzFyb'
    """
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(str_len)
    )


def get_timestamp(str_len=13):
    """
    获取时间戳字符串，长度只能在0到16之间
    :param str_len:
    :return:
    """
    if isinstance(str_len, integer_types) and 0 < str_len < 17:
        return builtin_str(time.time()).replace(".", "")[:str_len]

    raise ParamsError("时间戳长度只能在0到16之间.")


def get_current_date(fmt="%Y-%m-%d"):
    """
    获取当前日期，默认格式为%Y-%m-%d
    :param fmt:
    :return:'2020-07-04'
    """
    return datetime.datetime.now().strftime(fmt)


def sleep(n_secs):
    """
    睡眠n秒
    :param n_secs:
    :return:
    """
    time.sleep(n_secs)










