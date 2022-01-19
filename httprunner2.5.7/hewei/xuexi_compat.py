# encoding: utf-8

"""
httprunner.compat

这个模块处理Python 2和Python 3之间的导入兼容性问题。
"""

try:
    import simplejson as json
except ImportError:
    import json

import sys

_ver = sys.version_info


is_py2 = (_ver[0] == 2)

is_py3 = (_ver[0] == 3)

try:
    JSONDecodeError = json.JSONDecodeError
except AttributeError:
    JSONDecodeError = ValueError

if is_py2:
    builtin_str = str
    bytes = str
    str = unicode
    basestring
