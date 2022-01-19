from keyword import kwlist

from prettyprinter import pprint
from httprunner.builtin.comparators import *
from httprunner.builtin.functions import *
import sys

# Syntax sugar.
_ver = sys.version_info

#: Python 2.x?
is_py2 = (_ver[0] == 2)

#: Python 3.x?
is_py3 = (_ver[0] == 3)

print(is_py2)
print(is_py3)

a = 5
b = 7
c = (a > b)
print(c)
