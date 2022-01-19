import logging
import os
import sys

from colorama import Fore, init
from colorlog import ColoredFormatter

init(autoreset=True)

LOG_LEVEL = "INFO"
LOG_FILE_PATH = ""

log_colors_config = {
    'DEBUG':    'cyan',
    'INFO':     'green',
    'WARNING':  'yellow',
    'ERROR':    'red',
    'CRITICAL': 'red',
}
loggers = {}


def setup_logger(log_level, log_file=None):
    global LOG_LEVEL
    LOG_LEVEL = log_level

    if log_file:
        global LOG_FILE_PATH
        LOG_FILE_PATH = log_file


def get_logger(name=None):
    """setup logger with ColoredFormatter."""
    name = name or "httprunner"
    logger_key = "".join([name, LOG_LEVEL, LOG_FILE_PATH])
    if logger_key in loggers:
        return loggers[logger_key]

    _logger = logging.getLogger(name)

    log_level = LOG_LEVEL
    # getattr(object, name[, default])返回一个对象属性值
    level = getattr(logging, log_level.upper(), None)
    if not level:
        color_print("Invalid log level: %s" % log_level, "RED")
        sys.exit(1)

    # hide traceback when log level is INFO/WARNING/ERROR/CRITICAL
    # 当level is INFO/WARNING/ERROR/CRITICAL，不打印回溯信息
    if level >= logging.INFO:
        # sys.tracebacklimit 当该变量值设置为整数，在发生未处理的异常时，它将决定打印的回溯信息的最大层级数;
        # 默认为 1000。当将其设置为 0 或小于 0，将关闭所有回溯信息，并且只打印异常类型和异常值
        sys.tracebacklimit = 0

    _logger.setLevel(level)
    if LOG_FILE_PATH:
        # os.path.dirname 返回文件路径（不含文件名）
        log_dir = os.path.dirname(LOG_FILE_PATH)
        if not os.path.isdir(log_dir):
            os.makedirs(log_dir)
        # logging.FileHandler(filename, mode='a', encoding=None, delay=False, errors=None) 将日志写入到文件。 
        # 如果未指定 mode，则会使用 'a'。 
        # 如果 encoding 不为 None，则会将其用作打开文件的编码格式。 
        # 如果 delay 为真值，则文件打开会被推迟至第一次调用 emit() 时。 默认情况下，文件会无限增长。 
        # 如果指定了 errors，它会被用于确定编码格式错误的处理方式
        handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
    else:
        # class logging.StreamHandler(stream=None)
        # 如果指定了 stream，则实例将用它作为日志记录输出；在其他情况下将使用 sys.stderr。
        handler = logging.StreamHandler(sys.stdout)
    # ColoredFormatter(logging.Formatter)
    # - fmt (str): The format string to use
    # - datefmt (str): A format string for the date
    # - log_colors (dict): A mapping of log level names to color names
    # - reset (bool): Implicitly append a color reset to all records unless False
    formatter = ColoredFormatter(
        u"%(log_color)s%(bg_white)s%(levelname)-8s%(reset)s %(message)s",
        datefmt=None,
        reset=True,
        log_colors=log_colors_config
    )
    handler.setFormatter(formatter)
    _logger.addHandler(handler)

    loggers[logger_key] = _logger
    return _logger


def coloring(text, color="WHITE"):
    fore_color = getattr(Fore, color.upper())
    return fore_color + text


def color_print(msg, color="WHITE"):
    fore_color = getattr(Fore, color.upper())
    print(fore_color + msg)


def log_with_color(level):
    """ log with color by different level
    """
    def wrapper(text):
        color = log_colors_config[level.upper()]
        _logger = get_logger()
        # level(msg, *args, **kwargs) 在此记录器上记录 INFO 级别的消息
        getattr(_logger, level.lower())(coloring(text, color))

    return wrapper

# level(msg)
log_debug = log_with_color("debug")
log_info = log_with_color("info")
log_warning = log_with_color("warning")
log_error = log_with_color("error")
log_critical = log_with_color("critical")
