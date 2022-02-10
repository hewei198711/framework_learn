from email import contentmanager
import importlib
from httprunner.loader.buildup_test import load_test_file
from pprint import pprint
from httprunner import builtin


path = r"httprunner2.5.7\\调试集合.yml"


loaded_content = load_test_file(path)
