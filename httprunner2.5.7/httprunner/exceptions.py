# encoding: utf-8

from httprunner.compat import JSONDecodeError, FileNotFoundError

""" failure type exceptions失败类型异常
    these exceptions will mark test as failure
    这些异常将把test标记为失败
"""


class MyBaseFailure(Exception):
    pass


class ParseTestsFailure(MyBaseFailure):
    pass


class ValidationFailure(MyBaseFailure):
    pass


class ExtractFailure(MyBaseFailure):
    pass


class SetupHooksFailure(MyBaseFailure):
    pass


class TeardownHooksFailure(MyBaseFailure):
    pass


""" error type exceptions错误类型的异常
    these exceptions will mark test as error
    这些异常将把test标记为错误
"""


class MyBaseError(Exception):
    pass


class FileFormatError(MyBaseError):
    pass


class ParamsError(MyBaseError):
    pass


class NotFoundError(MyBaseError):
    pass


class FileNotFound(FileNotFoundError, NotFoundError):
    pass


class FunctionNotFound(NotFoundError):
    pass


class VariableNotFound(NotFoundError):
    pass


class EnvNotFound(NotFoundError):
    pass


class CSVNotFound(NotFoundError):
    pass


class ApiNotFound(NotFoundError):
    pass


class TestcaseNotFound(NotFoundError):
    pass


class SummaryEmpty(MyBaseError):
    """ test result summary data is empty
    """
