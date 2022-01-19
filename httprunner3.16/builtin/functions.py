"""
Built-in functions used in YAML/JSON testcases.YAML/JSON测试用例中使用的内置函数。
"""

import datetime
import random
import string
import time

from httprunner.exceptions import ParamsError

# 随机返回str_len 长度的字母与数字的组合
def gen_random_string(str_len):
    """ generate random string with specified length
    """
    return "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(str_len)
    )

# 返回str位的时间戳，长度大于0小于等于16位
def get_timestamp(str_len=13):
    """ get timestamp string, length can only between 0 and 16
    """
    if isinstance(str_len, int) and 0 < str_len < 17:
        return str(time.time()).replace(".", "")[:str_len]

    raise ParamsError("timestamp length can only between 0 and 16.")

# 返回规定格式的当前时间，默认格式为"%Y-%m-%d"
def get_current_date(fmt="%Y-%m-%d"):
    """ get current date, default format is %Y-%m-%d
    """
    return datetime.datetime.now().strftime(fmt)

# 睡眠n_secs
def sleep(n_secs):
    """ sleep n seconds
    """
    time.sleep(n_secs)
