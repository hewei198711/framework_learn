import logging
import random
import sys
import traceback
from time import time

import gevent
from gevent import GreenletExit

from locust.exception import InterruptTaskSet, RescheduleTask, RescheduleTaskImmediately, StopUser, MissingWaitTimeError


logger = logging.getLogger(__name__)

LOCUST_STATE_RUNNING, LOCUST_STATE_WAITING, LOCUST_STATE_STOPPING = ["running", "waiting", "stopping"]


def task(weight=1):
    """
    Used as a convenience decorator to be able to declare tasks for a User or a TaskSet
    inline in the class. Example::用作方便的装饰器，以便能够在类中内联地为用户或TaskSet声明任务

        class ForumPage(TaskSet):
            @task(100)
            def read_thread(self):
                pass

            @task(7)
            def create_thread(self):
                pass
    """

    def decorator_func(func):
        if func.__name__ in ["on_stop", "on_start"]:
            logging.warning(
                "You have tagged your on_stop/start function with @task. "
                "This will make the method get called both as a task AND on stop/start."
            )  # this is usually not what the user intended 这通常不是用户想要的
        func.locust_task_weight = weight
        return func

    """
    Check if task was used without parentheses (not called), like this::检查task是否在使用时没有使用括号(未调用)，如下所示

        @task
        def my_task()
            pass
    """
    if callable(weight):
        func = weight
        weight = 1
        return decorator_func(func)
    else:
        return decorator_func


def tag(*tags):
    """
    Decorator for tagging tasks and TaskSets with the given tag name. You can then limit the test
    to only execute tasks that are tagged with any of the tags provided by the --tags command-line
    argument. Example::

        class ForumPage(TaskSet):
            @tag('thread')
            @task(100)
            def read_thread(self):
                pass

            @tag('thread')
            @tag('post')
            @task(7)
            def create_thread(self):
                pass

            @tag('post')
            @task(11)
            def comment(self):
                pass
    """

    def decorator_func(decorated):
        if hasattr(decorated, "tasks"):
            decorated.tasks = list(map(tag(*tags), decorated.tasks))
        else:
            if "locust_tag_set" not in decorated.__dict__:
                decorated.locust_tag_set = set()
            decorated.locust_tag_set |= set(tags)
        return decorated

    if len(tags) == 0 or callable(tags[0]):
        raise ValueError("No tag name was supplied")

    return decorator_func


def get_tasks_from_base_classes(bases, class_dict):
    """
    Function used by both TaskSetMeta and UserMeta for collecting all declared tasks
    on the TaskSet/User class and all its base classes
    TaskSetMeta和UserMeta使用的函数，用于收集TaskSet/User类及其所有基类上声明的所有任务
    """
    new_tasks = []
    for base in bases:
        if hasattr(base, "tasks") and base.tasks:
            new_tasks += base.tasks

    if "tasks" in class_dict and class_dict["tasks"] is not None:
        tasks = class_dict["tasks"]
        if isinstance(tasks, dict):
            tasks = tasks.items()

        for task in tasks:
            if isinstance(task, tuple):
                task, count = task
                for i in range(count):
                    new_tasks.append(task)
            else:
                new_tasks.append(task)

    for item in class_dict.values():
        if "locust_task_weight" in dir(item):
            for i in range(0, item.locust_task_weight):
                new_tasks.append(item)

    return new_tasks


def filter_tasks_by_tags(task_holder, tags=None, exclude_tags=None, checked=None):
    """
    Function used by Environment to recursively remove any tasks/TaskSets from a TaskSet/User that
    shouldn't be executed according to the tag options
    按标签筛选任务:环境使用的函数，用于递归地从任务集/用户中删除根据标记选项不应该执行的任务/任务集
    """

    new_tasks = []
    if checked is None:
        checked = {}
    for task in task_holder.tasks:
        if task in checked:
            if checked[task]:
                new_tasks.append(task)
            continue

        passing = True
        if hasattr(task, "tasks"):
            filter_tasks_by_tags(task, tags, exclude_tags, checked)
            passing = len(task.tasks) > 0
        else:
            if tags is not None:
                passing &= "locust_tag_set" in dir(task) and len(task.locust_tag_set & tags) > 0
            if exclude_tags is not None:
                passing &= "locust_tag_set" not in dir(task) or len(task.locust_tag_set & exclude_tags) == 0

        if passing:
            new_tasks.append(task)
        checked[task] = passing

    task_holder.tasks = new_tasks


class TaskSetMeta(type):
    """
    Meta class for the main User class. It's used to allow User classes to specify task execution
    ratio using an {task:int} dict, or a [(task0,int), ..., (taskN,int)] list.
    主User类的元类。它用于允许User类指定任务执行使用{task:int} dict，或[(task0,int)，…(taskN int)列表。
    """

    def __new__(mcs, classname, bases, class_dict):
        class_dict["tasks"] = get_tasks_from_base_classes(bases, class_dict)
        return type.__new__(mcs, classname, bases, class_dict)


class TaskSet(object, metaclass=TaskSetMeta):
    """
    Class defining a set of tasks that a User will execute.类定义用户将执行的一组任务

    When a TaskSet starts running, it will pick a task from the *tasks* attribute,
    execute it, and then sleep for the number of seconds returned by its *wait_time*
    function. If no wait_time method has been declared on the TaskSet, it'll call the
    wait_time function on the User by default. It will then schedule another task
    for execution and so on.
    当TaskSet开始运行时，它将从*tasks*属性中选择一个任务，执行它，然后休眠它的*wait_time*返回的秒数函数。
    如果TaskSet上没有声明wait_time方法，则调用默认情况下，
    wait_time函数对用户起作用。然后它将调度另一个任务执行死刑等等。

    TaskSets can be nested, which means that a TaskSet's *tasks* attribute can contain
    another TaskSet. If the nested TaskSet is scheduled to be executed, it will be
    instantiated and called from the currently executing TaskSet. Execution in the
    currently running TaskSet will then be handed over to the nested TaskSet which will
    continue to run until it throws an InterruptTaskSet exception, which is done when
    :py:meth:`TaskSet.interrupt() <locust.TaskSet.interrupt>` is called. (execution
    will then continue in the first TaskSet).
    任务集可以嵌套，这意味着任务集的*tasks*属性可以包含另一个TaskSet。
    如果嵌套的任务集被调度执行，它就会被调度执行从当前执行的任务集实例化并调用。
    执行的当前运行的任务集将被传递给嵌套的任务集继续运行，
    直到它抛出一个InterruptTaskSet异常，该异常在调用:
    py:meth: ' TaskSet.interrupt() &lt;(执行然后在第一个任务集中继续)。
    """

    tasks = []
    """
    Collection of python callables and/or TaskSet classes that the User(s) will run.

    If tasks is a list, the task to be performed will be picked randomly.

    If tasks is a *(callable,int)* list of two-tuples, or a {callable:int} dict,
    the task to be performed will be picked randomly, but each task will be weighted
    according to its corresponding int value. So in the following case, *ThreadPage* will
    be fifteen times more likely to be picked than *write_post*::

        class ForumPage(TaskSet):
            tasks = {ThreadPage:15, write_post:1}
    """

    min_wait = None
    """
    Deprecated: Use wait_time instead.
    Minimum waiting time between the execution of user tasks. Can be used to override
    the min_wait defined in the root User class, which will be used if not set on the
    TaskSet.
    """

    max_wait = None
    """
    Deprecated: Use wait_time instead.
    Maximum waiting time between the execution of user tasks. Can be used to override
    the max_wait defined in the root User class, which will be used if not set on the
    TaskSet.
    """

    wait_function = None
    """
    Deprecated: Use wait_time instead.
    Function used to calculate waiting time between the execution of user tasks in milliseconds.
    Can be used to override the wait_function defined in the root User class, which will be used
    if not set on the TaskSet.
    已弃用:使用wait_time代替。
    """

    _user = None
    _parent = None

    def __init__(self, parent):
        self._task_queue = []
        self._time_start = time()

        if isinstance(parent, TaskSet):
            self._user = parent.user
        else:
            self._user = parent

        self._parent = parent

        # if this class doesn't have a min_wait, max_wait or wait_function defined, copy it from Locust
        # 如果这个类没有定义min_wait, max_wait或wait_function，从Locust复制它
        if not self.min_wait:
            self.min_wait = self.user.min_wait
        if not self.max_wait:
            self.max_wait = self.user.max_wait
        if not self.wait_function:
            self.wait_function = self.user.wait_function

    @property
    def user(self):
        """:py:class:`User <locust.User>` instance that this TaskSet was created by"""
        return self._user

    @property
    def parent(self):
        """Parent TaskSet instance of this TaskSet
        (or :py:class:`User <locust.User>` if this is not a nested TaskSet)"""
        return self._parent

    def on_start(self):
        """
        Called when a User starts executing this TaskSet
        """
        pass

    def on_stop(self):
        """
        Called when a User stops executing this TaskSet. E.g. when TaskSet.interrupt() is called
        or when the User is killed
        """
        pass

    def run(self):
        try:
            self.on_start()
        except InterruptTaskSet as e:
            if e.reschedule:
                raise RescheduleTaskImmediately(e.reschedule).with_traceback(e.__traceback__)
            else:
                raise RescheduleTask(e.reschedule).with_traceback(e.__traceback__)

        while True:
            try:
                if not self._task_queue:
                    self.schedule_task(self.get_next_task())

                try:
                    if self.user._state == LOCUST_STATE_STOPPING:
                        raise StopUser()
                    self.execute_next_task()
                except RescheduleTaskImmediately:
                    pass
                except RescheduleTask:
                    self.wait()
                else:
                    self.wait()
            except InterruptTaskSet as e:
                self.on_stop()
                if e.reschedule:
                    raise RescheduleTaskImmediately(e.reschedule) from e
                else:
                    raise RescheduleTask(e.reschedule) from e
            except (StopUser, GreenletExit):
                self.on_stop()
                raise
            except Exception as e:
                self.user.environment.events.user_error.fire(user_instance=self, exception=e, tb=e.__traceback__)
                if self.user.environment.catch_exceptions:
                    logger.error("%s\n%s", e, traceback.format_exc())
                    self.wait()
                else:
                    raise

    def execute_next_task(self):
        self.execute_task(self._task_queue.pop(0))

    def execute_task(self, task):
        # check if the function is a method bound to the current locust, and if so, don't pass self as first argument
        # 检查该函数是否是绑定到当前locust的方法，如果是，不要将self作为第一个参数传递
        if hasattr(task, "__self__") and task.__self__ == self:
            # task is a bound method on self
            # 任务是自我约束的方法
            task()
        elif hasattr(task, "tasks") and issubclass(task, TaskSet):
            # task is another (nested) TaskSet class
            # task是另一个(嵌套的)TaskSet类
            task(self).run()
        else:
            # task is a function
            task(self)

    def schedule_task(self, task_callable, first=False):
        """
        Add a task to the User's task execution queue.
        向User的任务执行队列中添加任务。

        :param task_callable: User task to schedule.要调度的用户任务。
        :param first: Optional keyword argument. If True, the task will be put first in the queue.
        ptional关键字参数。如果为True，任务将被放在队列的第一个位置。
        """
        if first:
            self._task_queue.insert(0, task_callable)
        else:
            self._task_queue.append(task_callable)

    def get_next_task(self):
        if not self.tasks:
            raise Exception("No tasks defined. use the @task decorator or set the tasks property of the TaskSet")
        return random.choice(self.tasks)

    def wait_time(self):
        """
        Method that returns the time (in seconds) between the execution of tasks.

        Example::

            from locust import TaskSet, between
            class Tasks(TaskSet):
                wait_time = between(3, 25)
        """
        if self.user.wait_time:
            return self.user.wait_time()
        elif self.min_wait is not None and self.max_wait is not None:
            return random.randint(self.min_wait, self.max_wait) / 1000.0
        else:
            raise MissingWaitTimeError(
                "You must define a wait_time method on either the %s or %s class"
                % (
                    type(self.user).__name__,
                    type(self).__name__,
                )
            )

    def wait(self):
        """
        Make the running user sleep for a duration defined by the Locust.wait_time
        function (or TaskSet.wait_time function if it's been defined).

        The user can also be killed gracefully while it's sleeping, so calling this
        method within a task makes it possible for a user to be killed mid-task, even if you've
        set a stop_timeout. If this behaviour is not desired you should make the user wait using
        gevent.sleep() instead.
        """
        if self.user._state == LOCUST_STATE_STOPPING:
            raise StopUser()
        self.user._state = LOCUST_STATE_WAITING
        self._sleep(self.wait_time())
        if self.user._state == LOCUST_STATE_STOPPING:
            raise StopUser()
        self.user._state = LOCUST_STATE_RUNNING

    def _sleep(self, seconds):
        gevent.sleep(seconds)

    def interrupt(self, reschedule=True):
        """
        Interrupt the TaskSet and hand over execution control back to the parent TaskSet.
        中断TaskSet并将执行控制权交还给父TaskSet。

        If *reschedule* is True (default), the parent User will immediately re-schedule,
        and execute, a new task.
        """
        raise InterruptTaskSet(reschedule)

    @property
    def client(self):
        """
        Shortcut to the client :py:attr:`client <locust.User.client>` attribute of this TaskSet's :py:class:`User <locust.User>`
        """
        return self.user.client


class DefaultTaskSet(TaskSet):
    """
    Default root TaskSet that executes tasks in User.tasks.
    It executes tasks declared directly on the Locust with the user instance as the task argument.
    默认根任务集，执行User.tasks中的任务。
    它使用用户实例作为任务参数，执行在Locust上直接声明的任务。
    """

    def get_next_task(self):
        if not self.user.tasks:
            raise Exception("No tasks defined. use the @task decorator or set the tasks property of the User")
        return random.choice(self.user.tasks)

    def execute_task(self, task):
        if hasattr(task, "tasks") and issubclass(task, TaskSet):
            # task is  (nested) TaskSet class
            # task是(嵌套的)TaskSet类
            task(self.user).run()
        else:
            # task is a function
            # Task是一个函数
            task(self.user)
