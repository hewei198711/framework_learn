# -*- coding:utf-8 -*-

from colorama import init
from termcolor import colored


# 使用Colorama让Termcolor也能在Windows上工作
init()

# 然后对所有彩色文本输出使用Termcolor
print(colored("Hello, World!", "green", "on_red"))
