from email import contentmanager
from httprunner.loader.load_test import load_dot_env_file
from pprint import pprint as print


path = r"D:\github\framework_learn\httprunner2.5.7\.env"
content = load_dot_env_file(path)

print(content, indent=4)