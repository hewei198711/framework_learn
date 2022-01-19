class LocustError(Exception):
    pass


class ResponseError(Exception):
    pass


class CatchResponseError(Exception):
    pass


class MissingWaitTimeError(LocustError):
    pass


class InterruptTaskSet(Exception):
    """
    Exception that will interrupt a User when thrown inside a task
    在task中抛出时中断User
    """

    def __init__(self, reschedule=True):
        """
        If *reschedule* is True and the InterruptTaskSet is raised inside a nested TaskSet,
        the parent TaskSet would immediately reschedule another task.
        如果* resschedule *为真，并且interrupttasset在嵌套的TaskSet中被抛出，
        父TaskSet将立即重新调度另一个任务。
        """
        self.reschedule = reschedule


class StopUser(Exception):
    pass


class RescheduleTask(Exception):
    """
    When raised in a task it's equivalent of a return statement.
    当在任务中被抛出时，它相当于一个return语句。

    Also used internally by TaskSet. When raised within the task control flow of a TaskSet,
    but not inside a task, the execution should be handed over to the parent TaskSet.
    也被TaskSet内部使用。当在TaskSet的task控制流中引发时，但不是在task内部，执行应该被移交给父TaskSet。
    """


class RescheduleTaskImmediately(Exception):
    """
    When raised in a User task, another User task will be rescheduled immediately (without calling wait_time first)
    当在一个User task中引发时，另一个User task将立即被重新调度(无需首先调用wait_time)
    """


class RPCError(Exception):
    """
    Exception that shows bad or broken network.显示坏的或损坏的网络的例外

    When raised from zmqrpc, RPC should be reestablished.
    当从zmqrpc启动时，RPC应该重新建立。
    """


class AuthCredentialsError(ValueError):
    """
    Exception when the auth credentials provided
    are not in the correct format
    当提供的认证凭据格式不正确时，会出现异常
    """

    pass


class RunnerAlreadyExistsError(Exception):
    pass
