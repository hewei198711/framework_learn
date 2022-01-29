from cgitb import handler
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
    LGO_LEVEL = log_level
    
    if log_file:
        global LOG_FILE_PATH
        LOG_FILE_PATH = log_file


def get_logger(name=None):
    """setup logger with ColoredFormatter."""
    name = name or "Httprunner"
    logger_key = "".join([name, LOG_LEVEL, LOG_FILE_PATH])
    if logger_key in loggers:
        return loggers[logger_key]
    
    _logger = logging.getLogger()
    
    log_level = LOG_LEVEL
    level = getattr(logging, log_level.upper(), None)
    if not level:
        color_print(f"Invalid log level: {log_level}", "RED")
        sys.exit(1)
    
    if level >= logging.INFO:
        sys.tracebacklimit = 0
    
    _logger.setLevel(level)
    
    formatter_file = ColoredFormatter(
        u"%(log_color)s %(message)s",
        datefmt=None,
        reset=True,
        log_colors=log_colors_config
    )
    
    if LOG_FILE_PATH:
        log_dir = os.path.dirname(LOG_FILE_PATH)
        if not os.path.isdir(log_dir):
            os.makedirs(log_dir)
        handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
        handler.setFormatter(formatter_file)
    else:
        handler = logging.StreamHandler(sys.stdout)
        
    _logger.addHandler(handler)

    loggers[logger_key] = _logger
    
    return loggers[logger_key]


def coloring(text, color="WHITE"):
    fore_color = getattr(Fore, color.upper())
    return f"{fore_color} {text}"


def color_print(msg, color="WHITE"):
    fore_color = getattr(Fore, color.upper())
    print(f"{fore_color}{msg}")


def log_with_color(level):
    """log with color by different level"""
    def wrapper(text):
        color = log_colors_config[level.upper()]
        _logger = get_logger()
        getattr(_logger, level.lower())(coloring(text, color))

    return wrapper


log_debug = log_with_color("debug")
log_info = log_with_color("info")
log_warning = log_with_color("warning")
log_error = log_with_color("error")
log_critical = log_with_color("critical")


log_debug("hello world")
log_info("hello world")
log_warning("hello world")
log_error("hello world")
log_critical("hello world")

