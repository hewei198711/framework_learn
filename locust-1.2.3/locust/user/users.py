from gevent import GreenletExit, greenlet
from gevent.pool import Group
from locust.clients import HttpSession
from locust.exception import LocustError, StopUser
from locust.util import deprecation
from .task import (
    DefaultTaskSet,
    get_tasks_from_base_classes,
    LOCUST_STATE_RUNNING,
    LOCUST_STATE_WAITING,
    LOCUST_STATE_STOPPING,
)


class NoClientWarningRaiser(object):
    """
    The purpose of this class is to emit a sensible error message for old test scripts that
    inherit from User, and expects there to be an HTTP client under the client attribute.
    这个类的目的是为旧的测试脚本发出一个合理的错误消息继承自User，并期望在client属性下有一个HTTP客户机。
    """

    def __getattr__(self, _):
        raise LocustError("No client instantiated. Did you intend to inherit from HttpUser?")


class UserMeta(type):
    """
    Meta class for the main User class. It's used to allow User classes to specify task execution
    ratio using an {task:int} dict, or a [(task0,int), ..., (taskN,int)] list.
    主User类的元类。它用于允许User类指定任务执行使用
    {task:int} dict，或[(task0,int)，…(taskN int)列表。
    """

    def __new__(mcs, classname, bases, class_dict):
        # gather any tasks that is declared on the class (or it's bases)
        # 收集在类(或它的基类)上声明的任何任务
        tasks = get_tasks_from_base_classes(bases, class_dict)
        class_dict["tasks"] = tasks

        if not class_dict.get("abstract"):
            # Not a base class
            class_dict["abstract"] = False

        deprecation.check_for_deprecated_task_set_attribute(class_dict)

        return type.__new__(mcs, classname, bases, class_dict)


class User(object, metaclass=UserMeta):
    """
    Represents a "user" which is to be spawned and attack the system that is to be load tested.
    表示一个将要产生的“用户”，并攻击将要进行负载测试的系统。

    The behaviour of this user is defined by its tasks. Tasks can be declared either directly on the
    class by using the :py:func:`@task decorator <locust.task>` on methods, or by setting
    the :py:attr:`tasks attribute <locust.User.tasks>`.
    该用户的行为由其任务定义。使用@task装饰器，或者属性tasks来设置

    This class should usually be subclassed by a class that defines some kind of client. For
    example when load testing an HTTP system, you probably want to use the
    :py:class:`HttpUser <locust.HttpUser>` class.
    这个类通常应该由定义某种客户端的类继承。当加载测试HTTP系统时，您可能使用HttpUser
    """

    host = None
    """Base hostname to swarm. i.e: http://127.0.0.1:1234"""

    min_wait = None
    """Deprecated: Use wait_time instead. Minimum waiting time between the execution of locust tasks"""

    max_wait = None
    """Deprecated: Use wait_time instead. Maximum waiting time between the execution of locust tasks"""

    wait_time = None
    """
    Method that returns the time (in seconds) between the execution of locust tasks.
    Can be overridden for individual TaskSets.
    返回执行locust任务之间的时间(以秒为单位)。可以为单独的任务集重写。

    Example::

        from locust import User, between
        class MyUser(User):
            wait_time = between(3, 25)
    """

    wait_function = None
    """
    .. warning::

        DEPRECATED: Use wait_time instead. Note that the new wait_time method should return seconds and not milliseconds.
        已弃用:使用wait_time代替。请注意，新的wait_time方法应该返回秒而不是毫秒。

    Method that returns the time between the execution of locust tasks in milliseconds
    """

    tasks = []
    """
    Collection of python callables and/or TaskSet classes that the Locust user(s) will run.
    Locust用户将运行的python可调用对象或TaskSet类的集合

    If tasks is a list, the task to be performed will be picked randomly.
    如果任务是一个列表，将随机选择要执行的任务

    If tasks is a *(callable,int)* list of two-tuples, or a {callable:int} dict,
    the task to be performed will be picked randomly, but each task will be weighted
    according to its corresponding int value. So in the following case, *ThreadPage* will
    be fifteen times more likely to be picked than *write_post*::
    如果task是一个[(callable,int),(callable,int)]二元组列表，或者是一个{callable:int} dict，
    要执行的任务将随机抽取,但每项任务都要根据其对应的int值加权.
    

        class ForumPage(TaskSet):
            tasks = {ThreadPage:15, write_post:1}
    """

    weight = 10
    """
    Probability of user class being chosen. The higher the weight, the greater the chance of it being chosen.
    用户类被选择的概率。权重越高，被选中的机会就越大
    """

    abstract = True
    """
    If abstract is True, the class is meant to be subclassed, 
    and locust will not spawn users of this class during a test.
    如果abstract为True，则该类将被子类化，蝗虫不会在测试期间产生这个类的用户。
    """

    environment = None
    """
    A reference to the :py:attr:`environment <locust.Environment>` in which this locust is running
    对:py:attr:`environment <locust.Environment>`的引用，该蝗虫正在其中运行
    """

    client = NoClientWarningRaiser()
    _state = None
    _greenlet: greenlet.Greenlet = None
    _group: Group
    _taskset_instance = None

    def __init__(self, environment):
        super().__init__()
        self.environment = environment

    def on_start(self):
        """
        Called when a User starts running.
        当用户开始运行时调用。
        """
        pass

    def on_stop(self):
        """
        Called when a User stops running (is killed)
        当用户停止运行(被杀死)时调用
        """
        pass

    def run(self):
        self._state = LOCUST_STATE_RUNNING
        self._taskset_instance = DefaultTaskSet(self)
        try:
            # run the TaskSet on_start method, if it has one
            # 运行TaskSet on_start方法(如果有的话)
            self.on_start()

            self._taskset_instance.run()
        except (GreenletExit, StopUser):
            # run the on_stop method, if it has one
            # 运行on_stop方法，如果它有的话
            self.on_stop()

    def wait(self):
        """
        Make the running user sleep for a duration defined by the User.wait_time
        function.
        让正在运行的用户休眠一段由user .wait_time定义的时间函数。

        The user can also be killed gracefully while it's sleeping, so calling this
        method within a task makes it possible for a user to be killed mid-task even if you've
        set a stop_timeout. If this behaviour is not desired, you should make the user wait using
        gevent.sleep() instead.
        用户也可以在休眠时被优雅地杀死，所以调用这个方法使用户有可能在任务中被杀死，
        即使您已经设置一个stop_timeout。如果不希望这种行为，您应该让用户等待使用gevent.sleep()。
        """
        self._taskset_instance.wait()

    def start(self, group: Group):
        """
        Start a greenlet that runs this User instance.
        启动运行此User实例的greenlet。

        :param group: Group instance where the greenlet will be spawned.将生成greenlet的组实例。
        :type gevent_group: gevent.pool.Group
        :returns: The spawned greenlet.催生了一种绿色小鸟。
        """

        def run_user(user):
            """
            Main function for User greenlet. It's important that this function takes the user
            instance as an argument, since we use greenlet_instance.args[0] to retrieve a reference to the
            User instance.
            用户greenlet的主要功能。重要的是，这个函数将用户实例作为参数，
            因为我们使用了greenlet_instance。args[0]来检索对User实例的引用。
            """
            user.run()

        self._greenlet = group.spawn(run_user, self)
        self._group = group
        return self._greenlet

    def stop(self, force=False):
        """
        Stop the user greenlet.停止用户greenlet。

        :param force: If False (the default) the stopping is done gracefully by setting the state to LOCUST_STATE_STOPPING
                      which will make the User instance stop once any currently running task is complete and on_stop
                      methods are called. If force is True the greenlet will be killed immediately.
        :returns: True if the greenlet was killed immediately, otherwise False
        """
        if force or self._state == LOCUST_STATE_WAITING:
            self._group.killone(self._greenlet)
            return True
        elif self._state == LOCUST_STATE_RUNNING:
            self._state = LOCUST_STATE_STOPPING
            return False


class HttpUser(User):
    """
    Represents an HTTP "user" which is to be spawned and attack the system that is to be load tested.
    表示要生成的HTTP“用户”，并攻击要进行负载测试的系统。

    The behaviour of this user is defined by its tasks. Tasks can be declared either directly on the
    class by using the :py:func:`@task decorator <locust.task>` on methods, or by setting
    the :py:attr:`tasks attribute <locust.User.tasks>`.
    该用户的行为由其任务定义。

    This class creates a *client* attribute on instantiation which is an HTTP client with support
    for keeping a user session between requests.
    这个类在实例化时创建一个*client*属性，它是一个支持HTTP的客户端,用于在请求之间保持用户会话。
    """

    abstract = True
    """
    If abstract is True, the class is meant to be subclassed, and users will not choose this locust during a test
    如果abstract为True，则该类将被子类化，用户将不会在测试期间选择这个“蝗虫”
    """

    client = None
    """
    Instance of HttpSession that is created upon instantiation of Locust.
    The client supports cookies, and therefore keeps the session between HTTP requests.
    在Locust实例化时创建的HttpSession实例。客户端支持cookie，因此在HTTP请求之间保持会话。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.host is None:
            # 必须指定基本主机。要么在User类的host属性中，要么在命令行中使用——host选项。
            raise LocustError(
                "You must specify the base host. "
                "Either in the host attribute in the User class, or on the command line using the --host option."
            )

        session = HttpSession(
            base_url=self.host,
            request_success=self.environment.events.request_success,
            request_failure=self.environment.events.request_failure,
        )
        session.trust_env = False
        self.client = session
