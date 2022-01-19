"""
Built-in validate comparators.
"""

import re

from httprunner.compat import basestring, builtin_str, integer_types


def equals(check_value, expect_value):
    assert check_value == expect_value


def less_than(check_value, expect_value):
    assert check_value < expect_value


def less_than_or_equals(check_value, expect_value):
    assert check_value <= expect_value


def greater_than(check_value, expect_value):
    assert check_value > expect_value


def greater_than_or_equals(check_value, expect_value):
    assert check_value >= expect_value


def not_equals(check_value, expect_value):
    assert check_value != expect_value


def string_equals(check_value, expect_value):
    assert builtin_str(check_value) == builtin_str(expect_value)


def length_equals(check_value, expect_value):
    assert isinstance(expect_value, integer_types)
    expect_len = _cast_to_int(expect_value)
    assert len(check_value) == expect_len


def length_greater_than(check_value, expect_value):
    assert isinstance(expect_value, integer_types)
    expect_len = _cast_to_int(expect_value)
    assert len(check_value) > expect_len


def length_greater_than_or_equals(check_value, expect_value):
    assert isinstance(expect_value, integer_types)
    expect_len = _cast_to_int(expect_value)
    assert len(check_value) >= expect_len


def length_less_than(check_value, expect_value):
    assert isinstance(expect_value, integer_types)
    expect_len = _cast_to_int(expect_value)
    assert len(check_value) < expect_len


def length_less_than_or_equals(check_value, expect_value):
    assert isinstance(expect_value, integer_types)
    expect_len = _cast_to_int(expect_value)
    assert len(check_value) <= expect_len


def listdict_equals(check_value, expect_value):
    """
    自己定义的函数
    解析搜索返回的数据，看是否和预期一致
    check_value:搜索返回的内容，list嵌套dict格式
    expect_value:断言预期值{key: value},key为查询的键,value为预期值
    """
    if isinstance(check_value, list) and check_value:
        for dictitem in check_value:
            assert dictitem[expect_value[0]] == expect_value[1]
    else:
        assert check_value == []


def contains(check_value, expect_value):
    assert isinstance(check_value, (list, tuple, dict, basestring))
    assert expect_value in check_value


def contained_by(check_value, expect_value):
    assert isinstance(expect_value, (list, tuple, dict, basestring))
    assert check_value in expect_value


def type_match(check_value, expect_value):
    def get_type(name):
        if isinstance(name, type):
            return name
        elif isinstance(name, basestring):
            try:
                return __builtins__[name]
            except KeyError:
                raise ValueError(name)
        else:
            raise ValueError(name)

    assert isinstance(check_value, get_type(expect_value))


def regex_match(check_value, expect_value):
    assert isinstance(expect_value, basestring)
    assert isinstance(check_value, basestring)
    assert re.match(expect_value, check_value)


def startswith(check_value, expect_value):
    assert builtin_str(check_value).startswith(builtin_str(expect_value))


def endswith(check_value, expect_value):
    assert builtin_str(check_value).endswith(builtin_str(expect_value))


def _cast_to_int(expect_value):
    try:
        return int(expect_value)
    except Exception:
        raise AssertionError("%r can't cast to int" % str(expect_value))