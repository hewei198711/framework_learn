import math
from locust import LoadTestShape

class DoubleWave(LoadTestShape):
    """
    A shape to immitate some specific user behaviour. In this example, midday
    and evening meal times.模仿某些特定用户行为的形状。在这个例子中，是午餐和晚餐时间。

    Settings:
        min_users -- minimum users 最小的用户数
        peak_one_users -- users in first peak 第一个高峰用户数
        peak_two_users -- users in second peak 第二次高峰用户数
        time_limit -- total length of test 试验总长度
    """

    min_users = 5
    peak_one_users = 20
    peak_two_users = 10
    time_limit = 60

    def tick(self):
        run_time = round(self.get_run_time())

        if run_time < self.time_limit:
            user_count = (
                (self.peak_one_users - self.min_users)
                * math.e ** -(((run_time / (self.time_limit / 10 * 2 / 3)) - 5) ** 2)
                + (self.peak_two_users - self.min_users)
                * math.e ** -(((run_time / (self.time_limit / 10 * 2 / 3)) - 10) ** 2)
                + self.min_users
            )
            return (round(user_count), round(user_count))
        else:
            return None


min_users = 5
peak_one_users = 20
peak_two_users = 10
time_limit = 60
run_time = 60

a = (peak_one_users - min_users) * math.e ** 3
b = time_limit / 10 * 2 / 3
c = run_time / (time_limit / 10 * 2 / 3)
d = -(((run_time / (time_limit / 10 * 2 / 3)) - 5) ** 2)
user_count = (
                (peak_one_users - min_users)
                * math.e ** -(((run_time / (time_limit / 10 * 2 / 3)) - 5) ** 2)
                + (peak_two_users - min_users)
                * math.e ** -(((run_time / (time_limit / 10 * 2 / 3)) - 10) ** 2)
                + min_users
            )
print(a)
print(math.e)
print(b)
print(c)
print(d)
print(round(user_count))