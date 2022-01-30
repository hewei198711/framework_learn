# -*- coding:utf-8 -*-


from os import sep


msg = "hello world!"
print(f"表达:{msg:>20}:结束了", f"表达:{msg:<20}:结束了", f"表达:{msg:20}:结束了",sep="\n")


d = 10000
msg = "hello world"
print(f"{msg!s}")
print(f"{msg!r}")
print(f"{msg!a}")

print(f"{d:.2f}")
print(f"{d:%}")
print(f"{d:.2%}")
print(f"{d:,}")
print(f"{d:.2e}")

import datetime


now = datetime.datetime.now()
ten_days_ago = now - datetime.timedelta(days=10)
print(f"{ten_days_ago:%Y-%m-%d %H:%M:%S}")
print(f"{now:%Y-%m-%d %H:%M:%S}")

