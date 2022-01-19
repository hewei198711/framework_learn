from locust import HttpUser, TaskSet, task, between
from locust.contrib.fasthttp import FastHttpUser


class WebsiteUser(FastHttpUser):
    """
    User class that does requests to the locust web server running on localhost,
    using the fast HTTP client
    向运行在localhost上的locust web服务器执行请求的用户类，使用快速HTTP客户端
    """

    host = "http://127.0.0.1:8089"
    wait_time = between(2, 5)
    # some things you can configure on FastHttpUser 你可以在fastthttpuser上配置一些东西
    # connection_timeout = 60.0  连接超时
    # insecure = True  不安全的
    # max_redirects = 5  最大重定向次数
    # max_retries = 1  最大重试次数
    # network_timeout = 60.0  网络超时

    @task
    def index(self):
        self.client.get("/")

    @task
    def stats(self):
        self.client.get("/stats/requests")
