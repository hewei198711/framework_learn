# -*- coding:utf-8 -*-

import colorlog


handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s%(levelname)s:%(name)s:%(message)s"
))

logger = colorlog.getLogger("example")
logger.addHandler(handler)