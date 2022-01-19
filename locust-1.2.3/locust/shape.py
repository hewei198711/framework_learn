import time


class LoadTestShape(object):
    """
    A simple load test shape class used to control the shape of load generated
    during a load test.
    一个简单的负载测试形状类，用于控制生成的负载形状在负载测试期间。
    """

    start_time = time.monotonic()

    def reset_time(self):
        """
        Resets start time back to 0
        将起始时间设置为0
        """
        self.start_time = time.monotonic()

    def get_run_time(self):
        """
        Calculates run time in seconds of the load test
        以负载测试的秒数计算运行时间
        """
        return time.monotonic() - self.start_time

    def tick(self):
        """
        Returns a tuple with 2 elements to control the running load test:
        返回一个包含2个元素的元组来控制运行的负载测试:

            user_count -- Total user count 用户总数
            spawn_rate -- Number of users to start/stop per second when changing number of users 改变用户数量时每秒要启动/停止的用户数量

        If `None` is returned then the running load test will be stopped.
        如果返回' None '，则正在运行的负载测试将停止。

        """

        return None
