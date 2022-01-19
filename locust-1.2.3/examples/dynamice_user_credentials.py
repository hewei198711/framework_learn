# locustfile.py

from locust import HttpUser, TaskSet, task, between

USER_CREDENTIALS = [
    ("user1", "password"),
    ("user2", "password"),
    ("user3", "password"),
]


class UserBehaviour(TaskSet):
    def on_start(self):
        if len(USER_CREDENTIALS) > 0:
            user, passw = USER_CREDENTIALS.pop()
            self.client.post("/login", {"username": user, "password": passw})

    @task
    def some_task(self):
        # user should be logged in here (unless the USER_CREDENTIALS ran out)
        # 用户应该在这里登录(除非USER_CREDENTIALS用完)
        self.client.get("/protected/resource")


class User(HttpUser):
    tasks = [UserBehaviour]
    wait_time = between(5, 60)
