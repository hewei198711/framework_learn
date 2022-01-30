# -*- coding:utf-8 -*-

from colorama import init, Fore


init(autoreset=True) # 自动恢复默认颜色


print(Fore.RED + "some red text")
print("automatically back to default color again")