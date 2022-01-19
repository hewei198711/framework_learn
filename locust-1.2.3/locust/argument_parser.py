import argparse
import os
import sys
import textwrap

import configargparse

import locust

version = locust.__version__

# 默认配置文件
DEFAULT_CONFIG_FILES = ["~/.locust.conf", "locust.conf"]


def _is_package(path):
    """
    Is the given path a Python package?
    给定的路径是Python包吗?
    path:locustfiles(只是文件夹，不是文件名)
    """
    return os.path.isdir(path) and os.path.exists(os.path.join(path, "__init__.py"))


def find_locustfile(locustfile):
    """
    Attempt to locate a locustfile, either explicitly or by searching parent dirs.
    尝试明确地或通过搜索父目录来定位locustfile。
    locustfile是否是.py文件
        不是则加上.py
    locustfile是否包含路径
        是，把路径中的"~"和"~user"转换成用户目录
        路径是否存在
            是，locustfile是否是.py文件，或者一个包
                返回locustfile的绝对路径
    locustfile不包含路径
        当前目录绝对路径，拼接当前目录+locustfile
            拼接后路径是否存在
                是，locustfile是否是.py文件，或者一个包
                    返回拼接后路径的绝对路径

    """
    # Obtain env value
    # 获得env值
    names = [locustfile]
    # Create .py version if necessary
    # 如果需要，创建.py版本，endswith() 方法用于判断字符串是否以指定后缀结尾，如果以指定后缀结尾返回True，否则返回False
    if not names[0].endswith(".py"):
        names.append(names[0] + ".py")
    # Does the name contain path elements?
    # 名称是否包含路径元素?(os.path.dirname(path)	返回文件路径部分)
    if os.path.dirname(names[0]):
        # If so, expand home-directory markers and test for existence
        # 如果是，展开主目录标记并测试是否存在
        for name in names:
            # os.path.expanduser(name)把name中包含的"~"和"~user"转换成用户目录
            expanded = os.path.expanduser(name)
            # os.path.exists(expanded)	如果路径 expanded 存在，返回 True；如果路径 path 不存在，返回 False。
            if os.path.exists(expanded):
                if name.endswith(".py") or _is_package(expanded):
                    # os.path.abspath(path)	返回绝对路径
                    return os.path.abspath(expanded)
    else:
        # Otherwise, start in cwd and work downwards towards filesystem root
        # 否则，在cwd中启动并向下工作到文件系统根(返回当前目录的绝对路径)
        path = os.path.abspath(".")
        while True:
            for name in names:
                # 拼接path
                joined = os.path.join(path, name)
                if os.path.exists(joined):
                    if name.endswith(".py") or _is_package(joined):
                        return os.path.abspath(joined)
            parent_path = os.path.dirname(path)
            if parent_path == path:
                # we've reached the root path which has been checked this iteration
                # 我们已经到达了经过这次迭代检查的根路径
                break
            path = parent_path
    # Implicit 'return None' if nothing was found
    # 如果没有找到任何东西，则隐式“返回None”


def get_empty_argument_parser(add_help=True, default_config_files=DEFAULT_CONFIG_FILES):
    parser = configargparse.ArgumentParser(
        default_config_files=default_config_files,
        add_env_var_help=False,
        add_config_file_help=False,
        add_help=add_help,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=argparse.SUPPRESS,
        description=textwrap.dedent(
            """
            Usage: locust [OPTIONS] [UserClass ...]

        """
        ),
        # epilog="",
    )
    parser.add_argument(
        "-f",
        "--locustfile",
        default="locustfile",
        help="Python module file to import, e.g. '../other.py'. Default: locustfile",
        env_var="LOCUST_LOCUSTFILE",
    )
    parser.add_argument("--config", is_config_file_arg=True, help="Config file path")

    return parser


def parse_locustfile_option(args=None):
    """
    Construct a command line parser that is only used to parse the -f argument so that we can
    import the test scripts in case any of them adds additional command line arguments to the
    parser
    构造一个仅用于解析-f参数的命令行解析器，以便我们可以导入测试脚本，以防它们中的任何一个添加额外的命令行参数到解析器
    """
    parser = get_empty_argument_parser(add_help=False)
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--version",
        "-V",
        action="store_true",
        default=False,
    )

    options, _ = parser.parse_known_args(args=args)

    locustfile = find_locustfile(options.locustfile)

    if not locustfile:
        if options.help or options.version:
            # if --help or --version is specified we'll call parse_options which will print the help/version message
            # 如果指定了--help or --version，我们将调用parse_options，它将打印帮助/版本信息
            parse_options(args=args)
        sys.stderr.write(
            "Could not find any locustfile! Ensure file ends in '.py' and see --help for available options.\n"
        )
        sys.exit(1)

    if locustfile == "locust.py":
        # 不能将locustfile命名为' locust.py '。请重命名文件，然后重试。
        sys.stderr.write("The locustfile must not be named `locust.py`. Please rename the file and try again.\n")
        sys.exit(1)

    return locustfile


def setup_parser_arguments(parser):
    """
    Setup command-line options
    设置命令行选项
    Takes a configargparse.ArgumentParser as argument and calls it's add_argument
    for each of the supported arguments
    configargparse.ArgumentParser作为参数并调用它的add_argument对每个被支持的论点
    """
    # 常见的选项
    parser._optionals.title = "Common options"
    parser.add_argument(
        "-H",
        "--host",
        help="Host to load test in the following format: http://10.21.32.33",
        env_var="LOCUST_HOST",
    )
    parser.add_argument(
        "-u",
        "--users",
        type=int,
        dest="num_users",
        # Locust用户并发数。主要与--headless连用
        help="Number of concurrent Locust users. Primarily used together with --headless",
        env_var="LOCUST_USERS",
    )
    parser.add_argument(
        "-r",
        "--spawn-rate",
        type=float,
        # 每秒产生用户的速率。主要与--headless连用
        help="The rate per second in which users are spawned. Primarily used together with --headless",
        env_var="LOCUST_SPAWN_RATE",
    )
    parser.add_argument(
        # 孵化率
        "--hatch-rate",
        env_var="LOCUST_HATCH_RATE",
        type=float,
        default=0,
        help=configargparse.SUPPRESS,
    )
    parser.add_argument(
        "-t",
        "--run-time",
        # 在规定的时间后停止，例如(300秒、20米、3小时、1小时30米等)。只与--headless连用
        help="Stop after the specified amount of time, e.g. (300s, 20m, 3h, 1h30m, etc.). "
             "Only used together with --headless",
        env_var="LOCUST_RUN_TIME",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        dest="list_commands",
        # 显示可能的用户类列表并退出
        help="Show list of possible User classes and exit",
    )
    # Web UI选项
    web_ui_group = parser.add_argument_group("Web UI options")
    web_ui_group.add_argument(
        "--web-host",
        default="",
        # 绑定web界面的主机。默认为'*'(所有接口)
        help="Host to bind the web interface to. Defaults to '*' (all interfaces)",
        env_var="LOCUST_WEB_HOST",
    )
    web_ui_group.add_argument(
        "--web-port",
        "-P",
        type=int,
        default=8089,
        # 运行web主机的端口
        help="Port on which to run web host",
        env_var="LOCUST_WEB_PORT",
    )
    web_ui_group.add_argument(
        "--headless",
        action="store_true",
        # 禁用web界面，并立即启动负载测试。要求指定-u和-t。
        help="Disable the web interface, and instead start the load test immediately. "
             "Requires -u and -t to be specified.",
        env_var="LOCUST_HEADLESS",
    )
    web_ui_group.add_argument(
        "--web-auth",
        type=str,
        dest="web_auth",
        default=None,
        # 打开web界面的Basic Auth。应该以以下格式提供:用户名:密码
        help="Turn on Basic Auth for the web interface. Should be supplied in the following format: username:password",
        env_var="LOCUST_WEB_AUTH",
    )
    web_ui_group.add_argument(
        "--tls-cert",
        default="",
        # 可选的TLS证书路径，用于通过HTTPS提供服务
        help="Optional path to TLS certificate to use to serve over HTTPS",
        env_var="LOCUST_TLS_CERT",
    )
    web_ui_group.add_argument(
        "--tls-key",
        default="",
        # 可选的TLS私钥路径，用于通过HTTPS提供服务
        help="Optional path to TLS private key to use to serve over HTTPS",
        env_var="LOCUST_TLS_KEY",
    )
    # 在运行分布式Locust时运行Locust Master节点的选项。主节点在运行负载测试之前需要连接到它的Worker节点。
    master_group = parser.add_argument_group(
        "Master options",
        "Options for running a Locust Master node when running Locust distributed. "
        "A Master node need Worker nodes that connect to it before it can run load tests.",
    )
    # if locust should be run in distributed mode as master
    # 如果蝗虫以分布式模式作为master运行
    master_group.add_argument(
        "--master",
        action="store_true",
        # 将locust设置为以分布式模式运行，并将此进程设置为master
        help="Set locust to run in distributed mode with this process as master",
        env_var="LOCUST_MODE_MASTER",
    )
    master_group.add_argument(
        "--master-bind-host",
        default="*",
        # locust master应该绑定的接口(主机名，ip)。只在使用——master时使用。默认为*(所有可用接口)。
        help="Interfaces (hostname, ip) that locust master should bind to. Only used when running with --master. "
             "Defaults to * (all available interfaces).",
        env_var="LOCUST_MASTER_BIND_HOST",
    )
    master_group.add_argument(
        "--master-bind-port",
        type=int,
        default=5557,
        # locust master应该绑定的端口。只在使用——master时使用。默认为5557。
        help="Port that locust master should bind to. Only used when running with --master. Defaults to 5557.",
        env_var="LOCUST_MASTER_BIND_PORT",
    )
    master_group.add_argument(
        "--expect-workers",
        type=int,
        default=1,
        # 在开始测试之前，master应该连接多少工人(仅当-headless使用时)
        help="How many workers master should expect to connect before starting the test (only when --headless used).",
        env_var="LOCUST_EXPECT_WORKERS",
    )
    master_group.add_argument(
        "--expect-slaves",
        action="store_true",
        help=configargparse.SUPPRESS,
    )
    # 运行Locust分布式时运行Locust Worker节点的选项.
    # 在启动Worker时，只需要指定LOCUSTFILE (-f选项)，因为其他选项如-u、-r、-t在Master节点上被指定。
    worker_group = parser.add_argument_group(
        "Worker options",
        textwrap.dedent(
            """
            Options for running a Locust Worker node when running Locust distributed.
            Only the LOCUSTFILE (-f option) need to be specified when starting a Worker, since other options such as -u,
             -r, -t are specified on the Master node.
        """
        ),
    )
    # if locust should be run in distributed mode as worker
    # 如果蝗虫以分布式模式作为工作者运行
    worker_group.add_argument(
        "--worker",
        action="store_true",
        # 将locust设置为以该进程作为worker的分布式模式运行
        help="Set locust to run in distributed mode with this process as worker",
        env_var="LOCUST_MODE_WORKER",
    )
    worker_group.add_argument(
        "--slave",
        action="store_true",
        help=configargparse.SUPPRESS,
    )
    # master host options
    # 主服务器选项
    worker_group.add_argument(
        "--master-host",
        default="127.0.0.1",
        # 用于分布式负载测试的蝗虫主机或IP地址。仅在与--worker运行时使用。默认为127.0.0.1。
        help="Host or IP address of locust master for distributed load testing. Only used when running with --worker. "
             "Defaults to 127.0.0.1.",
        env_var="LOCUST_MASTER_NODE_HOST",
        metavar="MASTER_NODE_HOST",
    )
    worker_group.add_argument(
        "--master-port",
        type=int,
        default=5557,
        # 要连接到它的端口由蝗虫主机用于分布式负载测试。仅在与--worker运行时使用。默认为5557。
        help="The port to connect to that is used by the locust master for distributed load testing. "
             "Only used when running with --worker. Defaults to 5557.",
        env_var="LOCUST_MASTER_NODE_PORT",
        metavar="MASTER_NODE_PORT",
    )
    # 标签选项,可以使用@tag装饰器对Locust任务进行标记。这些选项允许指定在测试期间包含或排除哪些任务。
    tag_group = parser.add_argument_group(
        "Tag options",
        "Locust tasks can be tagged using the @tag decorator. "
        "These options let specify which tasks to include or exclude during a test.",
    )
    tag_group.add_argument(
        "-T",
        "--tags",
        nargs="*",
        metavar="TAG",
        env_var="LOCUST_TAGS",
        # 要包含在测试中的标记列表，因此只有具有任何匹配标记的任务将被执行
        help="List of tags to include in the test, so only tasks with any matching tags will be executed",
    )
    tag_group.add_argument(
        "-E",
        "--exclude-tags",
        nargs="*",
        metavar="TAG",
        env_var="LOCUST_EXCLUDE_TAGS",
        # 要从测试中排除的标记列表，因此只有没有匹配标记的任务将被执行
        help="List of tags to exclude from the test, so only tasks with no matching tags will be executed",
    )
    # 请求数据选项
    stats_group = parser.add_argument_group("Request statistics options")
    stats_group.add_argument(
        "--csv",  # Name repeated in 'parse_options'名称重复在'parse options'中
        dest="csv_prefix",
        # 存储当前请求统计数据到CSV格式的文件。设置此选项将生成三个文件:
        # [CSV_PREFIX]_stats.csv， [CSV_PREFIX]_stats_history.csv和[CSV_PREFIX]_failures.csv"
        help="Store current request stats to files in CSV format. "
             "Setting this option will generate three files: [CSV_PREFIX]_stats.csv, "
             "[CSV_PREFIX]_stats_history.csv and [CSV_PREFIX]_failures.csv",
        env_var="LOCUST_CSV",
    )
    stats_group.add_argument(
        "--csv-full-history",  # Name repeated in 'parse_options'名称重复在'parse_options'中
        action="store_true",
        default=False,
        dest="stats_history_enabled",
        # 将每个统计条目以CSV格式存储到_stats_history.csv文件中。你也必须指定'--csv'参数来启用它。
        help="Store each stats entry in CSV format to _stats_history.csv file. "
             "You must also specify the '--csv' argument to enable this.",
        env_var="LOCUST_CSV_FULL_HISTORY",
    )
    stats_group.add_argument(
        "--print-stats",
        action="store_true",
        # 在控制台中打印统计数据
        help="Print stats in the console",
        env_var="LOCUST_PRINT_STATS",
    )
    stats_group.add_argument(
        "--only-summary",
        action="store_true",
        # Only print the summary stats
        help="Only print the summary stats",
        env_var="LOCUST_ONLY_SUMMARY",
    )
    stats_group.add_argument(
        "--reset-stats",
        action="store_true",
        # 一旦刷出完成重置统计数据。在分布式模式下运行时，应该在master和worker上都设置
        help="Reset statistics once spawning has been completed. "
             "Should be set on both master and workers when running in distributed mode",
        env_var="LOCUST_RESET_STATS",
    )
    # 日志记录选项
    log_group = parser.add_argument_group("Logging options")
    log_group.add_argument(
        "--skip-log-setup",
        action="store_true",
        dest="skip_log_setup",
        default=False,
        # 禁用Locust的日志设置。相反，配置是由Locust测试或Python默认值提供的。
        help="Disable Locust's logging setup. Instead, "
             "the configuration is provided by the Locust test or Python defaults.",
        env_var="LOCUST_SKIP_LOG_SETUP",
    )
    log_group.add_argument(
        "--loglevel",
        "-L",
        default="INFO",
        # 选择DEBUG/INFO/WARNING/ERROR/CRITICAL。默认是INFO。
        help="Choose between DEBUG/INFO/WARNING/ERROR/CRITICAL. Default is INFO.",
        env_var="LOCUST_LOGLEVEL",
    )
    log_group.add_argument(
        "--logfile",
        # 日志文件路径。如果没有设置，日志将转到stdout/stderr
        help="Path to log file. If not set, log will go to stdout/stderr",
        env_var="LOCUST_LOGFILE",
    )
    # 逐步加载选项
    step_load_group = parser.add_argument_group("Step load options")
    step_load_group.add_argument(
        "--step-load",
        action="store_true",
        # 启用Step Load模式以监视用户负载增加时性能指标的变化情况。要求指定--step-users和--step-time。
        help="Enable Step Load mode to monitor how performance metrics varies when user load increases. "
             "Requires --step-users and --step-time to be specified.",
        env_var="LOCUST_STEP_LOAD",
    )
    step_load_group.add_argument(
        "--step-users",
        type=int,
        # 在逐步加载模式中，用户数量将逐步增加。仅与--step-load配合使用
        help="User count to increase by step in Step Load mode. Only used together with --step-load",
        env_var="LOCUST_STEP_USERS",
    )
    step_load_group.add_argument("--step-clients", action="store_true", help=configargparse.SUPPRESS)
    step_load_group.add_argument(
        "--step-time",
        # Step Load模式的步长，例如(300s, 20m, 3h, 1h30m等)。仅与--step-load配合使用
        help="Step duration in Step Load mode, e.g. (300s, 20m, 3h, 1h30m, etc.). Only used together with --step-load",
        env_var="LOCUST_STEP_TIME",
    )
    # 其他选项
    other_group = parser.add_argument_group("Other options")
    # 打印User类的任务执行比率表
    other_group.add_argument(
        "--show-task-ratio", action="store_true", help="Print table of the User classes' task execution ratio"
    )
    # 按json数据格式打印User类的任务执行比率
    other_group.add_argument(
        "--show-task-ratio-json", action="store_true", help="Print json data of the User classes' task execution ratio"
    )
    # optparse gives you --version but we have to do it ourselves to get -V too
    other_group.add_argument(
        "--version",
        "-V",
        action="version",
        # 显示程序的版本号并退出
        help="Show program's version number and exit",
        version="%(prog)s {}".format(version),
    )
    other_group.add_argument(
        "--exit-code-on-error",
        type=int,
        default=1,
        # 设置当测试结果包含任何失败或错误时使用的进程退出代码
        help="Sets the process exit code to use when a test result contain any failure or error",
        env_var="LOCUST_EXIT_CODE_ON_ERROR",
    )
    other_group.add_argument(
        "-s",
        "--stop-timeout",
        action="store",
        type=int,
        dest="stop_timeout",
        default=None,
        # 在退出之前等待模拟用户完成任何正在执行的任务的秒数。违约将立即终止。仅当运行Locust分布式时，需要为主进程指定此参数
        help="Number of seconds to wait for a simulated user to complete any executing task before exiting. "
             "Default is to terminate immediately. "
             "This parameter only needs to be specified for the master process when running Locust distributed.",
        env_var="LOCUST_STOP_TIMEOUT",
    )

    user_classes_group = parser.add_argument_group("User classes")
    user_classes_group.add_argument(
        "user_classes",
        nargs="*",
        metavar="UserClass",
        # 可选地指定应该使用哪些User类(可用的User类可以用-l或——list列出)
        help="Optionally specify which User classes that should be used "
             "(available User classes can be listed with -l or --list)",
    )


def get_parser(default_config_files=DEFAULT_CONFIG_FILES):
    # get a parser that is only able to parse the -f argument
    # 获取一个只能解析-f参数的解析器
    parser = get_empty_argument_parser(add_help=True, default_config_files=default_config_files)
    # add all the other supported arguments
    # 添加所有其他支持的参数
    setup_parser_arguments(parser)
    # fire event to provide a hook for locustscripts and plugins to add command line arguments
    # 触发事件，为locustscripts和插件提供一个钩子，以添加命令行参数
    locust.events.init_command_line_parser.fire(parser=parser)
    return parser


def parse_options(args=None):
    parser = get_parser()
    parsed_opts = parser.parse_args(args=args)
    if parsed_opts.stats_history_enabled and (parsed_opts.csv_prefix is None):
        parser.error("'--csv-full-history' requires '--csv'.")
    return parsed_opts
