# -*- coding:utf-8 -*-

import re
from colorlog import ColoredFormatter


formatter = ColoredFormatter(
    "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
    datefmt=None,
    reset=True,
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white"
    },
    secondary_log_colors={},
    style="%"
)


