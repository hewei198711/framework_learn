from email import contentmanager
import importlib
from httprunner.loader.buildup_test import load_project_data
from pprint import pprint
from httprunner import builtin


test_path = r"httprunner2.5.7\\调试集合.yml"


project_mapping = load_project_data(test_path, dot_env_path=None)
