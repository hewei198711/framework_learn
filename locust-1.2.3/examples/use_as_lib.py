import gevent
from locust import HttpUser, task, between
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging

setup_logging("INFO", None)


class User(HttpUser):
    wait_time = between(1, 3)
    host = "https://docs.locust.io"

    @task
    def my_task(self):
        self.client.get("/")

    @task
    def task_404(self):
        self.client.get("/non-existing-path")


# setup Environment and Runner 设置环境和运行程序
env = Environment(user_classes=[User])
env.create_local_runner()

# start a WebUI instance 启动web实例
env.create_web_ui("127.0.0.1", 8089)

# start a greenlet that periodically outputs the current stats 启动一个定期输出当前统计信息的greenlet
gevent.spawn(stats_printer(env.stats))

# start a greenlet that save current stats to history 启动一个保存当前统计数据到历史的绿色窗口
gevent.spawn(stats_history, env.runner)

# start the test
env.runner.start(1, spawn_rate=10)

# in 60 seconds stop the runner 在60秒内让跑者停下来
gevent.spawn_later(60, lambda: env.runner.quit())

# wait for the greenlets 等待着绿芽
env.runner.greenlet.join()

# stop the web server for good measures 停止web服务器的良好措施
env.web_ui.stop()
