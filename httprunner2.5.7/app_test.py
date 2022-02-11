from email import contentmanager
import importlib
from httprunner.runner import Runner, HookTypeEnum
from pprint import pprint as print
from httprunner import builtin


config = {
    'name': '调试用例', 
    'verify': False, 
    'setup_hooks': ['${hw_setup("test setup")}'], 
    'teardown_hooks': ['${hw_teardown("test teardown")}'], 
    'base_url': None, 
    'variables': {
        'pageNum': 1, 
        'pageSize': 10,
        'storeCode': '920111', 
        'maxMonth': '202108', 
        'minMonth': '202108'
    }
}

runner = Runner(config)


actions = ['${hw_setup("test setup")}']
hook_type = HookTypeEnum.SETUP

runner.do_hook_actions(actions, hook_type)