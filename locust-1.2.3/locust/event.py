import logging
from . import log
import traceback
from .exception import StopUser, RescheduleTask, RescheduleTaskImmediately, InterruptTaskSet


class EventHook:
    """
    Simple event class used to provide hooks for different types of events in Locust.
    一个简单的事件类，用于在蝗虫中为不同类型的事件提供钩子。

    Here's how to use the EventHook class::
    下面是如何使用EventHook类:

        my_event = EventHook()
        def on_my_event(a, b, **kw):
            print("Event was fired with arguments: %s, %s" % (a, b))
        my_event.add_listener(on_my_event)
        my_event.fire(a="foo", b="bar")

    If reverse is True, then the handlers will run in the reverse order
    that they were inserted
    如果reverse为真，则处理程序将以插入时的相反顺序运行
    """

    def __init__(self):
        self._handlers = []

    def add_listener(self, handler):
        self._handlers.append(handler)
        return handler

    def remove_listener(self, handler):
        self._handlers.remove(handler)

    def fire(self, *, reverse=False, **kwargs):
        if reverse:
            handlers = reversed(self._handlers)  # 反转列表的顺序
        else:
            handlers = self._handlers
        for handler in handlers:
            try:
                handler(**kwargs)
            except (StopUser, RescheduleTask, RescheduleTaskImmediately, InterruptTaskSet):
                # These exceptions could be thrown by, for example, a request_failure handler,
                # in which case they are entirely appropriate and should not be caught
                # 可以抛出这些异常,例如，request_failure handler在这种情况下，它们是完全合适的，不应该被抓住
                raise
            except Exception:
                # 事件处理程序中的未捕获异常:traceback.format_exc()提取，格式化和打印关于Python堆栈跟踪的信息
                logging.error("Uncaught exception in event handler: \n%s", traceback.format_exc())
                log.unhandled_greenlet_exception = True


class Events:
    request_success = EventHook
    """
    Fired when a request is completed successfully. This event is typically used to report requests
    when writing custom clients for locust.
    请求成功完成时触发。此事件通常用于在为蝗虫编写自定义客户端时报告请求。

    Event arguments:事件参数

    :param request_type: Request type method used
    :param name: Path to the URL that was called (or override name if it was used in the call to the client)
    :param response_time: Response time in milliseconds
    :param response_length: Content-length of the response
    """

    request_failure = EventHook
    """
    Fired when a request fails. This event is typically used to report failed requests when writing
    custom clients for locust.
    请求失败时触发。此事件通常用于在为蝗虫编写自定义客户端时报告失败的请求

    Event arguments:

    :param request_type: Request type method used
    :param name: Path to the URL that was called (or override name if it was used in the call to the client)
    :param response_time: Time in milliseconds until exception was thrown
    :param response_length: Content-length of the response
    :param exception: Exception instance that was thrown被抛出的异常实例
    """

    user_error = EventHook
    """
    Fired when an exception occurs inside the execution of a User class.
    在用户类的执行过程中发生异常时触发

    Event arguments:

    :param user_instance: User class instance where the exception occurred发生异常的用户类实例
    :param exception: Exception that was thrown抛出的异常
    :param tb: Traceback object (from e.__traceback__)回溯对象
    """

    report_to_master = EventHook
    """
    Used when Locust is running in --worker mode. It can be used to attach
    data to the dicts that are regularly sent to the master. It's fired regularly when a report
    is to be sent to the master server.
    当蝗虫在——worker模式下运行时使用。它可以用来将数据附加到定期发送给主服务器的字典上。当报告要发送到主服务器时，它会定期触发

    Note that the keys "stats" and "errors" are used by Locust and shouldn't be overridden.
    注意键“stats”和“errors”是由蝗虫使用的，不应该被覆盖。

    Event arguments:

    :param client_id: The client id of the running locust process.正在运行的locust进程的客户端id
    :param data: Data dict that can be modified in order to attach data that should be sent to the master.
    可以修改的数据字典，以附加应该发送给主服务器的数据
    """

    worker_report = EventHook
    """
    Used when Locust is running in --master mode and is fired when the master
    server receives a report from a Locust worker server.
    当蝗虫在——主模式下运行时使用，当主服务器接收到来自蝗虫工作者服务器的报告时触发。

    This event can be used to aggregate data from the locust worker servers.
    此事件可用于聚合来自locust worker服务器的数据。

    Event arguments:

    :param client_id: Client id of the reporting worker报表工作者的客户端id
    :param data: Data dict with the data from the worker node数据字典与来自工作节点的数据
    """

    spawning_complete = EventHook
    """
    Fired when all simulated users has been spawned.
    当所有模拟用户都已生成时触发。

    Event arguments:

    :param user_count: Number of users that were spawned产生的用户数量
    """

    quitting = EventHook
    """
    Fired when the locust process is exiting当蝗虫进程退出时触发

    Event arguments:

    :param environment: Environment instance环境实例
    """

    init = EventHook
    """
    Fired when Locust is started, once the Environment instance and locust runner instance
    have been created. This hook can be used by end-users' code to run code that requires access to
    the Environment. For example to register listeners to request_success, request_failure
    or other events.
    一旦创建了环境实例和蝗虫运行器实例，在启动蝗虫时触发。这个钩子可以被最终用户的代码用来运行需要访问环境的代码。
    例如将监听器注册到request_success、request_failure或其他事件。

    Event arguments:

    :param environment: Environment instance环境实例
    """

    init_command_line_parser = EventHook
    """
    Event that can be used to add command line options to Locust
    事件，可用于向蝗虫添加命令行选项

    Event arguments:

    :param parser: ArgumentParser instance参数Parser实例
    """

    test_start = EventHook
    """
    Fired when a new load test is started. It's not fired again if the number of
    users change during a test. When running locust distributed the event is only fired
    on the master node and not on each worker node.
    在启动新的负载测试时触发。如果在测试期间用户数量发生变化，则不会再次触发它。
    当运行locust distributed时，事件只在主节点上触发，而不是在每个工作节点上触发。
    """

    test_stop = EventHook
    """
    Fired when a load test is stopped. When running locust distributed the event
    is only fired on the master node and not on each worker node.
    当负载测试停止时触发。当运行locust distributed时，事件只在主节点上触发，而不是在每个工作节点上。
    """

    reset_stats = EventHook
    """
    Fired when the Reset Stats button is clicked in the web UI.
    当在web UI中单击Reset Stats按钮时触发
    """
    # vars() 函数返回对象object的属性和属性值的字典对象
    # type() 函数如果你只有第一个参数则返回对象的类型
    # 字典(Dictionary) items() 函数以列表返回可遍历的(键, 值) 元组数组。
    # setattr() 函数对应函数 getattr()，用于设置属性值，该属性不一定是存在的
    def __init__(self):
        for name, value in vars(type(self)).items():
            if value == EventHook:
                setattr(self, name, value())
