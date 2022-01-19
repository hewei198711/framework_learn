import logging
import logging.config
import socket

HOSTNAME = socket.gethostname()  # 获取本地主机名

# Global flag that we set to True if any unhandled exception occurs in a greenlet
# 全局标志，如果在greenlet中发生任何未处理的异常，我们将其设置为True
# Used by main.py to set the process return code to non-zero
# 由main.py用于将进程返回码设置为非零
unhandled_greenlet_exception = False  # 未处理的一种绿色小鸟例外


def setup_logging(loglevel, logfile=None):
    loglevel = loglevel.upper()

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,  # 禁用现有伐木工
        "formatters": {  # 格式器
            "default": {  # 默认的
                "format": "[%(asctime)s] {0}/%(levelname)s/%(name)s: %(message)s".format(HOSTNAME),
            },
            "plain": {  # 平原
                "format": "%(message)s",
            },
        },
        "handlers": {  # 处理程序
            "console": {  # 控制台
                "class": "logging.StreamHandler",  # 流处理程序
                "formatter": "default",
            },
            "console_plain": {  # 控制台平原
                "class": "logging.StreamHandler",
                "formatter": "plain",
            },
        },
        "loggers": {
            "locust": {
                "handlers": ["console"],
                "level": loglevel,
                "propagate": False,  # 传播
            },
            "locust.stats_logger": {
                "handlers": ["console_plain"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": loglevel,
        },
    }
    if logfile:
        # if a file has been specified add a file logging handler and set
        # 如果已指定文件，则添加文件日志处理程序并进行设置
        # the locust and root loggers to use it
        # 蝗虫和根日志记录器使用它
        LOGGING_CONFIG["handlers"]["file"] = {
            "class": "logging.FileHandler",
            "filename": logfile,
            "formatter": "default",
        }
        LOGGING_CONFIG["loggers"]["locust"]["handlers"] = ["file"]
        LOGGING_CONFIG["root"]["handlers"] = ["file"]

    logging.config.dictConfig(LOGGING_CONFIG)


def greenlet_exception_logger(logger, level=logging.CRITICAL):
    """
    Return a function that can be used as argument to Greenlet.link_exception() that will log the
    unhandled exception to the given logger.
    返回一个函数，该函数可作为Greenlet.link_exception()的参数，它将记录对给定记录器的未处理异常。
    """

    def exception_handler(greenlet):
        logger.log(level, "Unhandled exception in greenlet: %s", greenlet, exc_info=greenlet.exc_info)
        global unhandled_greenlet_exception
        unhandled_greenlet_exception = True

    return exception_handler
