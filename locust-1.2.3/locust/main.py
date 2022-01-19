import inspect
import logging
import os
import importlib
import signal
import socket
import sys
import time

import gevent

import locust

from . import log
from .argument_parser import parse_locustfile_option, parse_options
from .env import Environment
from .log import setup_logging, greenlet_exception_logger
from . import stats
from .stats import print_error_report, print_percentile_stats, print_stats, stats_printer, stats_history
from .stats import StatsCSV, StatsCSVFileWriter
from .user import User
from .user.inspectuser import get_task_ratio_dict, print_task_ratio
from .util.timespan import parse_timespan
from .exception import AuthCredentialsError
from .shape import LoadTestShape


version = locust.__version__


def is_user_class(item):
    """
    Check if a variable is a runnable (non-abstract) User class
    检查变量是否为可运行(非抽象)的User类
    bool() 函数用于将给定参数转换为布尔类型，如果没有参数，返回 False。
    inspect.isclass(item):是否为类
    issubclass(item, User)：item是否为User的子类，返回 True，否则返回 False。
    item.abstract:如果abstract为真，则该类将被子类化，并且locust将不会在测试期间生成该类的用户(Users.py文件114行)
    """
    return bool(inspect.isclass(item) and issubclass(item, User) and item.abstract is False)


def is_shape_class(item):
    """
    Check if a class is a LoadTestShape
    检查类是否为LoadTestShape
    inspect.isclass(item):是否为类
    issubclass(item, User)：item是否为LoadTestShape的子类，返回 True，否则返回 False。

    """
    return bool(
        inspect.isclass(item) and issubclass(item, LoadTestShape) and item.__dict__["__module__"] != "locust.shape"
    )


def load_locustfile(path):
    """
    Import given locustfile path and return (docstring, callables).
    导入给定的loccustfile路径并返回(docstring, callables)。

    Specifically, the locustfile's ``__doc__`` attribute (a string) and a
    dictionary of ``{'name': callable}`` containing all callables which pass
    the "is a Locust" test.
    path:locustfiles/locust_search_pay_simple.py
    imported.__doc__:模块中的说明
    user_classes：{'WebsiteUser': <class 'locust_search_pay_simple.WebsiteUser'>}
    shape_class：
    """

    # Start with making sure the current working dir is in the sys.path
    # 把当前工作目录放到sys.path中的最前面（os.getcwd() 方法用于返回当前工作目录），这样新添加的目录会优先于其他目录被import检查
    sys.path.insert(0, os.getcwd())
    # Get directory and locustfile name
    # 获取目录和locustfile名称(把目录和文件名分离)
    directory, locustfile = os.path.split(path)
    # If the directory isn't in the PYTHONPATH, add it so our import will work
    # 如果目录不在PYTHONPATH中，请添加它，以便我们的导入工作
    added_to_path = False
    index = None
    if directory not in sys.path:
        sys.path.insert(0, directory)
        added_to_path = True
    # If the directory IS in the PYTHONPATH, move it to the front temporarily,
    # 如果目录在PYTHONPATH中，将其暂时移到前面（性能更好）
    # otherwise other locustfiles -- like Locusts's own -- may scoop the intended one.
    # 否则，其他的loccustfiles——像蝗虫自己的——可能会抢了预期的第一个。
    else:
        # 目录在sys.path中排第几名
        i = sys.path.index(directory)
        if i != 0:
            # Store index for later restoration
            # 存储索引，以便以后恢复
            index = i
            # Add to front, then remove from original position
            # 添加到前面，然后从原来的位置移除
            sys.path.insert(0, directory)
            del sys.path[i + 1]
    # Perform the import
    # 执行导入(os.path.splitext(locustfile)把文件和文件名后缀分离'main', '.py')
    # source = <_frozen_importlib_external.SourceFileLoader object at 0x000001EF109DFFD0>
    # imported = <module 'locust_search_pay_simple' from 'locustfiles/locust_search_pay_simple.py'>
    source = importlib.machinery.SourceFileLoader(os.path.splitext(locustfile)[0], path)
    imported = source.load_module()
    # Remove directory from path if we added it ourselves (just to be neat)
    # 如果是我们自己添加的，就从path中删除directory(为了整洁)，68行的逆操作
    if added_to_path:
        del sys.path[0]
    # Put back in original index if we moved it
    # 如果我们移动它，就把它放回原来的索引，85行的逆操作
    if index is not None:
        sys.path.insert(index + 1, directory)
        del sys.path[0]
    # Return our two-tuple
    # 返回我们的二元组
    # vars() 函数返回对象object的属性和属性值的字典对象。
    # user_classes = {'WebsiteUser': <class 'locust_search_pay_simple.WebsiteUser'>}
    user_classes = {name: value for name, value in vars(imported).items() if is_user_class(value)}

    # Find shape class, if any, return it
    # 找到shape类，如果有，返回它
    shape_classes = [value for name, value in vars(imported).items() if is_shape_class(value)]
    if shape_classes:
        shape_class = shape_classes[0]()
    else:
        shape_class = None

    return imported.__doc__, user_classes, shape_class
    #  imported.__doc__ = """云商搜索商品，直接购买，自购，提交订单，钱包支付全流程场景\n……"""


def create_environment(user_classes, options, events=None, shape_class=None):
    """
    Create an Environment instance from options
    从选项创建一个Environment实例
    """
    return Environment(
        user_classes=user_classes,
        shape_class=shape_class,
        tags=options.tags,
        exclude_tags=options.exclude_tags,
        events=events,
        host=options.host,
        reset_stats=options.reset_stats,
        step_load=options.step_load,
        stop_timeout=options.stop_timeout,
        parsed_options=options,
    )


def main():
    # find specified locustfile and make sure it exists, using a very simplified
    # command line parser that is only used to parse the -f option
    # 找到指定的locustfile并确保它存在，使用一个非常简化的命令行解析器，该解析器只用于解析-f选项
    locustfile = parse_locustfile_option()

    # import the locustfile
    docstring, user_classes, shape_class = load_locustfile(locustfile)

    # parse all command line options
    # 解析所有命令行选项
    options = parse_options()

    # 检查丢弃的命令--slave/--expect-slaves是否存在，并提示已更名为--worker/--expect-workers
    if options.slave or options.expect_slaves:
        sys.stderr.write("The --slave/--expect-slaves parameters have been renamed --worker/--expect-workers\n")
        sys.exit(1)
    # 检查丢弃的命令-hatch-rate是否存在，并提示已更名为--spawn-rate
    if options.hatch_rate:
        sys.stderr.write("[DEPRECATED] The --hatch-rate parameter has been renamed --spawn-rate\n")
        options.spawn_rate = options.hatch_rate

    # setup logging 设置日志记录
    if not options.skip_log_setup:
        if options.loglevel.upper() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            setup_logging(options.loglevel, options.logfile)
        else:
            sys.stderr.write("Invalid --loglevel. Valid values are: DEBUG/INFO/WARNING/ERROR/CRITICAL\n")
            sys.exit(1)

    logger = logging.getLogger(__name__)
    greenlet_exception_handler = greenlet_exception_logger(logger)

    if options.list_commands:
        print("Available Users:")
        for name in user_classes:
            print("    " + name)
        sys.exit(0)

    if not user_classes:
        logger.error("No User class found!")
        sys.exit(1)

    # make sure specified User exists
    # 确保指定的用户类存在，并只运行这些用户类203行
    if options.user_classes:
        # 差集运算,确保要运行的user_classes是确实存在的
        missing = set(options.user_classes) - set(user_classes.keys())
        if missing:
            logger.error("Unknown User(s): %s\n" % (", ".join(missing)))
            sys.exit(1)
        else:
            # 交集运算
            names = set(options.user_classes) & set(user_classes.keys())
            user_classes = [user_classes[n] for n in names]
    else:
        # list() call is needed to consume the dict_view object in Python 3
        # 在Python 3中，使用dict_view对象需要list()调用，调用这些用户类
        user_classes = list(user_classes.values())

    # os.name该变量返回当前操作系统的类型，当前只注册了3个值：分别是posix , nt , java， 对应linux/windows/java虚拟机
    if os.name != "nt":
        try:
            # (只用于 Unix , 可选) resource 模块用于查询或修改当前系统资源限制设置
            import resource

            # 能打开的最大文件数
            if resource.getrlimit(resource.RLIMIT_NOFILE)[0] < 10000:
                # Increasing the limit to 10000 within a running process should work on at least MacOS.
                # 在一个正在运行的进程中，将限制增加到10000应该至少在MacOS上有效
                # It does not work on all OS:es, but we should be no worse off for trying.
                # 它不能在所有的操作系统上工作，但我们应该不会因为尝试而变得更糟。
                resource.setrlimit(resource.RLIMIT_NOFILE, [10000, resource.RLIM_INFINITY])
        except BaseException:
            logger.warning(
                "System open file limit setting is not high enough for load testing, "
                "and the OS didn't allow locust to increase it by itself. "
                "See https://github.com/locustio/locust/wiki/Installation#increasing-maximum-number-of-open-files-limit for more info."
            )
            # 系统打开文件限制设置不够高，无法进行负载测试，并且操作系统不允许locust自己增加它

    # create locust Environment
    # 创造蝗虫的环境
    environment = create_environment(user_classes, options, events=locust.events, shape_class=shape_class)

    if shape_class and (options.num_users or options.spawn_rate or options.step_load):
        logger.error(
            "The specified locustfile contains a shape class but a conflicting argument was specified: users, spawn-rate or step-load"
        )
        # 指定的locustfile包含一个shape类，但指定了一个冲突的参数:users、产卵率或步长加载
        sys.exit(1)

    if options.show_task_ratio:
        # 每个用户类的任务比率
        print("\n Task ratio per User class")
        print("-" * 80)
        print_task_ratio(user_classes)
        # 任务总比
        print("\n Total task ratio")
        print("-" * 80)
        print_task_ratio(user_classes, total=True)
        sys.exit(0)
    if options.show_task_ratio_json:
        from json import dumps

        task_data = {
            "per_class": get_task_ratio_dict(user_classes),
            "total": get_task_ratio_dict(user_classes, total=True),
        }
        print(dumps(task_data))
        sys.exit(0)

    if options.step_time:
        if not options.step_load:
            # --step-time参数只能与--step-load一起使用
            logger.error("The --step-time argument can only be used together with --step-load")
            sys.exit(1)
        if options.worker:
            # --step-time应该在主节点上指定，而不是在工作节点上
            logger.error("--step-time should be specified on the master node, and not on worker nodes")
            sys.exit(1)
        try:
            options.step_time = parse_timespan(options.step_time)
        except ValueError:
            # 有效的步长时间格式为:20,20s, 3m, 2h, 1h20m, 3h30m10s等
            logger.error("Valid --step-time formats are: 20, 20s, 3m, 2h, 1h20m, 3h30m10s, etc.")
            sys.exit(1)
    # 创建master,worker或者local进程
    if options.master:
        runner = environment.create_master_runner(
            master_bind_host=options.master_bind_host,
            master_bind_port=options.master_bind_port,
        )
    elif options.worker:
        try:
            runner = environment.create_worker_runner(options.master_host, options.master_port)
        except socket.error as e:
            # 无法连接到Locust主机
            logger.error("Failed to connect to the Locust master: %s", e)
            sys.exit(-1)
    else:
        runner = environment.create_local_runner()

    # main_greenlet is pointing to runners.greenlet by default, it will point the web greenlet later if in web mode
    # 主main_greenlet指向runners.greenlet。默认情况下，如果在web模式下，它将指向web Greenlet
    main_greenlet = runner.greenlet

    if options.run_time:
        if not options.headless:
            # --run-time参数只能与--headless一起使用
            logger.error("The --run-time argument can only be used together with --headless")
            sys.exit(1)
        if options.worker:
            # --run-time应该在主节点上指定，而不是在工作节点上
            logger.error("--run-time should be specified on the master node, and not on worker nodes")
            sys.exit(1)
        try:
            options.run_time = parse_timespan(options.run_time)
        except ValueError:
            # 有效的运行时间格式是:20,20s, 3m, 2h, 1h20m, 3h30m10s等。
            logger.error("Valid --run-time formats are: 20, 20s, 3m, 2h, 1h20m, 3h30m10s, etc.")
            sys.exit(1)

        def spawn_run_time_limit_greenlet():
            # 运行时间限制设置为%s秒
            logger.info("Run time limit set to %s seconds" % options.run_time)

            def timelimit_stop():
                # 时间限制。停止蝗虫
                logger.info("Time limit reached. Stopping Locust.")
                runner.quit()

            gevent.spawn_later(options.run_time, timelimit_stop).link_exception(greenlet_exception_handler)

    if options.csv_prefix:
        stats_csv_writer = StatsCSVFileWriter(
            environment, stats.PERCENTILES_TO_REPORT, options.csv_prefix, options.stats_history_enabled
        )
    else:
        stats_csv_writer = StatsCSV(environment, stats.PERCENTILES_TO_REPORT)

    # start Web UI
    # 启动Web UI
    if not options.headless and not options.worker:
        # spawn web greenlet
        # 产生网络一种绿色小鸟
        protocol = "https" if options.tls_cert and options.tls_key else "http"
        try:
            if options.web_host == "*":
                # special check for "*" so that we're consistent with --master-bind-host
                # 对“*”进行特殊检查，以便与--master-bind-host一致
                web_host = ""
            else:
                web_host = options.web_host
            if web_host:
                # 在以下网址启动web界面
                logger.info("Starting web interface at %s://%s:%s" % (protocol, web_host, options.web_port))
            else:
                # 在以下网址启动web界面，接受来自所有网络接口的连接
                logger.info(
                    "Starting web interface at %s://0.0.0.0:%s (accepting connections from all network interfaces)"
                    % (protocol, options.web_port)
                )
            web_ui = environment.create_web_ui(
                host=web_host,
                port=options.web_port,
                auth_credentials=options.web_auth,
                tls_cert=options.tls_cert,
                tls_key=options.tls_key,
                stats_csv_writer=stats_csv_writer,
            )
        except AuthCredentialsError:
            # --web-auth提供的凭据应该有格式:用户名:密码
            logger.error("Credentials supplied with --web-auth should have the format: username:password")
            sys.exit(1)
        else:
            main_greenlet = web_ui.greenlet
    else:
        web_ui = None

    # Fire locust init event which can be used by end-users' code to run setup code that
    # need access to the Environment, Runner or WebUI
    # Fire locust init事件，最终用户的代码可以使用它来运行需要访问环境、运行程序或web的设置代码
    environment.events.init.fire(environment=environment, runner=runner, web_ui=web_ui)

    if options.headless:
        # headless mode
        # 无头模式
        if options.master:
            # wait for worker nodes to connect
            # 等待工作节点连接
            while len(runner.clients.ready) < options.expect_workers:
                # 等待工人准备好，%s中的%s已连接
                logging.info(
                    "Waiting for workers to be ready, %s of %s connected",
                    len(runner.clients.ready),
                    options.expect_workers,
                )
                time.sleep(1)
        if not options.worker:
            # apply headless mode defaults
            # 应用无头模式默认值
            if options.num_users is None:
                options.num_users = 1
            if options.spawn_rate is None:
                options.spawn_rate = 1
            if options.step_users is None:
                options.step_users = 1

            # start the test
            # 启动测试
            if options.step_time:
                runner.start_stepload(options.num_users, options.spawn_rate, options.step_users, options.step_time)
            if environment.shape_class:
                environment.runner.start_shape()
            else:
                runner.start(options.num_users, options.spawn_rate)

    if options.run_time:
        spawn_run_time_limit_greenlet()

    stats_printer_greenlet = None
    if not options.only_summary and (options.print_stats or (options.headless and not options.worker)):
        # spawn stats printing greenlet
        # 刷出统计打印绿色
        stats_printer_greenlet = gevent.spawn(stats_printer(runner.stats))
        stats_printer_greenlet.link_exception(greenlet_exception_handler)

    if options.csv_prefix:
        gevent.spawn(stats_csv_writer.stats_writer).link_exception(greenlet_exception_handler)

    gevent.spawn(stats_history, runner)

    def shutdown():
        """
        Shut down locust by firing quitting event, printing/writing stats and exiting
        通过触发退出事件，打印/写入数据和退出来关闭蝗虫
        """
        logger.info("Running teardowns...")
        environment.events.quitting.fire(environment=environment, reverse=True)

        # determine the process exit code
        # 确定进程退出代码
        if log.unhandled_greenlet_exception:
            code = 2
        elif environment.process_exit_code is not None:
            code = environment.process_exit_code
        elif len(runner.errors) or len(runner.exceptions):
            code = options.exit_code_on_error
        else:
            code = 0
        # 关闭(退出码%s)，再见
        logger.info("Shutting down (exit code %s), bye." % code)
        if stats_printer_greenlet is not None:
            stats_printer_greenlet.kill(block=False)
        # 清理runner……
        logger.info("Cleaning up runner...")
        if runner is not None:
            runner.quit()

        print_stats(runner.stats, current=False)
        print_percentile_stats(runner.stats)

        print_error_report(runner.stats)

        sys.exit(code)

    # install SIGTERM handler
    # 获得SIGTERM信号
    def sig_term_handler():
        logger.info("Got SIGTERM signal")
        shutdown()

    gevent.signal_handler(signal.SIGTERM, sig_term_handler)

    try:
        # 从蝗虫某版本
        logger.info("Starting Locust %s" % version)
        main_greenlet.join()
        shutdown()
    except KeyboardInterrupt:
        shutdown()

