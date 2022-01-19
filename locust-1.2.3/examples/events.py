# -*- coding: utf-8 -*-

"""
This is an example of a locustfile that uses Locust's built in event hooks to
track the sum of the content-length header in all successful HTTP responses
这是一个locustfile示例，它使用Locust内置的事件钩子来跟踪所有成功HTTP响应中的内容长度头的总和
"""

from locust import HttpUser, TaskSet, task, web, between
from locust import events


class MyTaskSet(TaskSet):
    @task(2)
    def index(l):
        l.client.get("/")

    @task(1)
    def stats(l):
        l.client.get("/stats/requests")


class WebsiteUser(HttpUser):
    host = "http://127.0.0.1:8089"
    wait_time = between(2, 5)
    tasks = [MyTaskSet]


stats = {"content-length": 0}


@events.init.add_listener
def locust_init(environment, **kwargs):
    """
    We need somewhere to store the stats.
    我们需要一个地方来存储数据
    On the master node stats will contain the aggregated sum of all content-lengths,
    while on the worker nodes this will be the sum of the content-lengths since the
    last stats report was sent to the master
    在主节点上，统计数据将包含所有内容长度的总和，而在工作节点上，这将是自上次统计报告发送到主节点以来的内容长度之和
    """
    if environment.web_ui:
        # this code is only run on the master node (the web_ui instance doesn't exist on workers)
        # 这段代码只在主节点上运行(web_ui实例在工作者上不存在)
        @environment.web_ui.app.route("/content-length")
        def total_content_length():
            """
            Add a route to the Locust web app, where we can see the total content-length
            添加一个到Locust web应用程序的路由，在那里我们可以看到总内容长度
            """
            return "Total content-length received: %i" % stats["content-length"]


@events.request_success.add_listener
def on_request_success(request_type, name, response_time, response_length):
    """
    Event handler that get triggered on every successful request
    事件处理程序，在每个成功请求时触发
    """
    stats["content-length"] += response_length


@events.report_to_master.add_listener
def on_report_to_master(client_id, data):
    """
    This event is triggered on the worker instances every time a stats report is
    to be sent to the locust master. It will allow us to add our extra content-length
    data to the dict that is being sent, and then we clear the local stats in the worker.
    每次向locust主机发送统计报告时，都会在工作实例上触发此事件。
    它将允许我们将额外的内容长度数据添加到正在发送的字典中，然后清除worker中的本地统计数据。
    """
    data["content-length"] = stats["content-length"]
    stats["content-length"] = 0


@events.worker_report.add_listener
def on_worker_report(client_id, data):
    """
    This event is triggered on the master instance when a new stats report arrives
    from a worker. Here we just add the content-length to the master's aggregated
    stats dict.
    当一个新的统计报告从一个worker到达时，这个事件会在主实例上触发。在这里，我们只是将内容长度添加到主节点的聚合统计字典。
    """
    stats["content-length"] += data["content-length"]
