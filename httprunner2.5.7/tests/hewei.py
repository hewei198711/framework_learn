import os
import time
import unittest

from prettyprinter import pprint

from httprunner import exceptions, loader, parser
from httprunner.loader import load
from debugtalk import gen_random_string, sum_two

variables_mapping = {
            "var_1": "abc",
            "var_2": "def",
            "var_3": 123,
            "var_4": {"a": 1},
            "var_5": True,
            "var_6": None
        }
check_variables_set = variables_mapping.keys()
functions_mapping = {
    "func1": lambda x,y: str(x) + str(y)
}

var = parser.LazyString("${func1($var_1, $var_3)}", functions_mapping, check_variables_set)

print(var._args[0])
