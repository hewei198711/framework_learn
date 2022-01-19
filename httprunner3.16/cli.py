import argparse
import enum
import os
import sys

import pytest
from loguru import logger
from sentry_sdk import capture_message

from httprunner import __description__, __version__
from httprunner.compat import ensure_cli_args
from httprunner.ext.har2case import init_har2case_parser, main_har2case
from httprunner.make import init_make_parser, main_make
from httprunner.scaffold import init_parser_scaffold, main_scaffold
from httprunner.utils import init_sentry_sdk

init_sentry_sdk()

# 制作HttpRunner测试用例并使用pytest运行。
def init_parser_run(subparsers):
    # 添加run运行的帮助
    sub_parser_run = subparsers.add_parser(
        "run", help="Make HttpRunner testcases and run with pytest."
    )
    return sub_parser_run

# 运行开始
def main_run(extra_args) -> enum.IntEnum:
    capture_message("start to run")
    # keep compatibility with v2 保持与v2的兼容性
    # 确保与v2中不推荐使用的cli参数兼容，返回v3的命令
    extra_args = ensure_cli_args(extra_args)

    tests_path_list = [] # 测试路径列表
    extra_args_new = [] # 新的命令参数列表
    for item in extra_args:
        # 判断路径是否存在
        if not os.path.exists(item):
            # item is not file/folder path
            extra_args_new.append(item)
        else:
            # item is file/folder path
            # 添加到路径列表
            tests_path_list.append(item)
    # 如果路径长度为0
    if len(tests_path_list) == 0:
        # has not specified any testcase path
        # 未指定任何测试用例路径
        logger.error(f"No valid testcase path in cli arguments: {extra_args}")
        sys.exit(1)
    # 制作测试用例的py文件
    testcase_path_list = main_make(tests_path_list)
    if not testcase_path_list:
        # 未找到有效的测试用例
        logger.error("No valid testcases found, exit 1.")
        sys.exit(1)

    if "--tb=short" not in extra_args_new:
        extra_args_new.append("--tb=short")

    # 把文件列表加到新命令列表中
    extra_args_new.extend(testcase_path_list)
    # 开始使用pytest运行测试。
    logger.info(f"start to run tests with pytest. HttpRunner version: {__version__}")
    # 使用pytest运行测试。
    return pytest.main(extra_args_new)

# API测试：解析命令行选项并运行命令。
def main():
    """ API test: parse command line options and run commands.
    """
    # 命令行参数解析器
    parser = argparse.ArgumentParser(description=__description__)
    # 添加参数操作
    parser.add_argument(
        "-V", "--version", dest="version", action="store_true", help="show version"
    )

    subparsers = parser.add_subparsers(help="sub-command help")
    # 添加 制作HttpRunner测试用例并使用pytest运行的子命令
    sub_parser_run = init_parser_run(subparsers)
    # 添加 创建具有模板结构的新项目的子命令
    sub_parser_scaffold = init_parser_scaffold(subparsers)
    # 添加 将HAR（HTTP存档）转换为HttpRunner的YAML/JSON测试用例 子命令
    sub_parser_har2case = init_har2case_parser(subparsers)
    # 添加 生成测试用例：解析命令行选项并运行命令。
    sub_parser_make = init_make_parser(subparsers)

    if len(sys.argv) == 1:
        # httprunner 输出help
        parser.print_help()
        sys.exit(0)
    elif len(sys.argv) == 2:
        # print help for sub-commands 打印子命令的帮助
        if sys.argv[1] in ["-V", "--version"]:
            # httprunner -V
            print(f"{__version__}")
        elif sys.argv[1] in ["-h", "--help"]:
            # httprunner -h
            parser.print_help()
        elif sys.argv[1] == "startproject":
            # httprunner startproject
            sub_parser_scaffold.print_help()
        elif sys.argv[1] == "har2case":
            # httprunner har2case
            sub_parser_har2case.print_help()
        elif sys.argv[1] == "run":
            # httprunner run
            pytest.main(["-h"])
        elif sys.argv[1] == "make":
            # httprunner make
            sub_parser_make.print_help()
        sys.exit(0)
    elif (
        len(sys.argv) == 3 and sys.argv[1] == "run" and sys.argv[2] in ["-h", "--help"]
    ):
        # httprunner run -h
        pytest.main(["-h"])
        sys.exit(0)

    extra_args = []
    # 运行性能测试
    if len(sys.argv) >= 2 and sys.argv[1] in ["run", "locusts"]:
        # 解析已知参数
        args, extra_args = parser.parse_known_args()
    else:
        # 命令行参数解析方法
        args = parser.parse_args()

    if args.version:
        print(f"{__version__}")
        sys.exit(0)
    # 运行开始
    if sys.argv[1] == "run":
        sys.exit(main_run(extra_args))
    # 创建httprunner脚手架
    elif sys.argv[1] == "startproject":
        main_scaffold(args)
    # 生成测试用例yaml/json
    elif sys.argv[1] == "har2case":
        main_har2case(args)
    # 制作pytest的py文件
    elif sys.argv[1] == "make":
        main_make(args.testcase_path)

# 命令别名，hrun = httprunner run
def main_hrun_alias():
    """ command alias
        hrun = httprunner run
    """
    # 如果命令列表长度为2
    if len(sys.argv) == 2:
        # 第二位为"-V"或 "--version"
        if sys.argv[1] in ["-V", "--version"]:
            # hrun -V
            # 命令转为httprunner -V
            sys.argv = ["httprunner", "-V"]
        elif sys.argv[1] in ["-h", "--help"]:
            # 命令转为httprunner -h
            pytest.main(["-h"])
            sys.exit(0)
        else:
            # hrun /path/to/testcase
            # 命令插入“run” ，例如为 hrun run /path/to/testcase
            sys.argv.insert(1, "run")
    else:
        # 命令第二位插入run，变成hrun run ...
        sys.argv.insert(1, "run")

    main()

# 命令别名 hmake=httprunner make
def main_make_alias():
    """ command alias
        hmake = httprunner make
    """
    # 命令第二位插入 make
    sys.argv.insert(1, "make")
    main()

# 命令别名,har2case = httprunner har2case
def main_har2case_alias():
    """ command alias
        har2case = httprunner har2case
    """
    # 命令第二位插入 har2case
    sys.argv.insert(1, "har2case")
    main()


if __name__ == "__main__":
    main()
