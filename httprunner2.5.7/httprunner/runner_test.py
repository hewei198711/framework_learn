# encoding:utf-8

from enum import Enum
from unittest.case import SkipTest

from httprunner import exceptions, logger, response, utils
from httprunner.client import HttpSession
from httprunner.context import SessionContext
from httprunner.validator import Validator


class HookTypeEnum(Enum):
    SETUP = 1
    TEARDOWN = 2
    

class Runner:
    def __init__(self, config, http_client_session=None):
        self.verify = config.get("verify", True)
        self.export = config.get("export") or config.get("output", [])
        config_variables = config.get("variables", {})

        testcase_setup_hooks = config.get("setup_hooks", [])
        self.testcase_teardown_hooks = config.get("teardown_hooks", [])

        self.http_client_session = http_client_session or HttpSession()
        self.session_context = SessionContext(config_variables)

        if testcase_setup_hooks:
            self.do_hook_actions(testcase_setup_hooks, HookTypeEnum.SETUP)
    
    def __del__(self):
        if self.testcase_teardown_hooks:
            self.do_hook_actions(self.testcase_teardown_hooks, HookTypeEnum.TEARDOWN)
    
    def do_hook_actions(self, actions, hook_type):
        logger.log_debug(f"call {hook_type.name} hook actions")
        for action in actions:
            if isinstance(action, dict) and len(action) == 1:
                var_name, hook_content = list(action.items()[0])
                hook_content_eval = self.session_context.eval_content(hook_content)
                logger.log_debug(f"assignment with hook: {var_name} = {hook_content} => {hook_content_eval}")
                self.session_context.update_test_variables(var_name, hook_content_eval)
            else:
                logger.log_debug(f"call hook function: {action}")
                self.session_context.eval_content(action)

    def __clear_test_data(self):
        if not isinstance(self.http_client_session, HttpSession):
            return
        self.http_client_session.init_meta_data()
    
    def _handle_skip_feature(self, test_dict):
        skip_reason = None
        
        if "skip" in test_dict:
            skip_reason = test_dict["skip"]
        elif "skipIf" in test_dict:
            skip_if_condition = test_dict["skipIf"]
            if self.session_context.eval_content(skip_if_condition):
                skip_reason = f"{skip_if_condition} evaluate to True"
        elif "skipUnless" in test_dict:
            skip_unless_condition = test_dict["skipUnless"]
            if not self.session_context.eval_content(skip_unless_condition):
                skip_reason = "{skip_unless_condition} evaluate to False"
        
        if skip_reason:
            raise SkipTest(skip_reason)
    
    
 
 
 
 
 
        