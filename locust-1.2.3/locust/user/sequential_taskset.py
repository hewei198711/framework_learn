from locust.exception import LocustError
from .task import TaskSet, TaskSetMeta


class SequentialTaskSetMeta(TaskSetMeta):
    """
    Meta class for SequentialTaskSet. It's used to allow SequentialTaskSet classes to specify
    task execution in both a list as the tasks attribute or using the @task decorator
    序列任务集的元类。它被用来允许指定SequentialTaskSet类在列表中作为tasks属性或使用@task装饰器执行任务

    We use the fact that class_dict order is the order of declaration in Python 3.6
    (See https://www.python.org/dev/peps/pep-0520/)
    """

    def __new__(mcs, classname, bases, class_dict):
        new_tasks = []
        for base in bases:
            # first get tasks from base classes首先从基类中获取任务
            if hasattr(base, "tasks") and base.tasks:
                new_tasks += base.tasks
        for key, value in class_dict.items():
            if key == "tasks":
                # we want to insert tasks from the tasks attribute at the point of it's declaration
                # compared to methods declared with @task
                # 与使用@task声明的方法相比，我们希望在tasks属性的声明处插入任务任务
                if isinstance(value, list):
                    new_tasks.extend(value)
                else:
                    raise ValueError("On SequentialTaskSet the task attribute can only be set to a list")

            if "locust_task_weight" in dir(value):
                # method decorated with @task方法用@task装饰
                new_tasks.append(value)

        class_dict["tasks"] = new_tasks
        return type.__new__(mcs, classname, bases, class_dict)


class SequentialTaskSet(TaskSet, metaclass=SequentialTaskSetMeta):
    """
    Class defining a sequence of tasks that a User will execute.
    定义用户将执行的任务序列的类。

    Works like TaskSet, but task weight is ignored, and all tasks are executed in order. Tasks can
    either be specified by setting the *tasks* attribute to a list of tasks, or by declaring tasks
    as methods using the @task decorator. The order of declaration decides the order of execution.
    工作方式类似于TaskSet，但任务权重被忽略，所有任务按顺序执行,声明的顺序决定了执行的顺序。任务可以要么通过将*tasks*属性设置,or使用@task装饰器的方法。

    It's possible to combine a task list in the *tasks* attribute, with some tasks declared using
    the @task decorator. The order of declaration is respected also in that case.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._task_index = 0

    def get_next_task(self):
        if not self.tasks:
            raise LocustError(
                "No tasks defined. use the @task decorator or set the tasks property of the SequentialTaskSet"
            )
        task = self.tasks[self._task_index % len(self.tasks)]
        self._task_index += 1
        return task
