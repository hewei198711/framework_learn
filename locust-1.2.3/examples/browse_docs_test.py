# This locust test script example will simulate a user
# browsing the Locust documentation on https://docs.locust.io/

import random
from locust import HttpUser, TaskSet, task, between
from pyquery import PyQuery


class BrowseDocumentation(TaskSet):
    def on_start(self):
        # assume all users arrive at the index page假设所有用户都到达了索引页
        self.index_page()
        self.urls_on_current_page = self.toc_urls

    @task(10)
    def index_page(self):
        r = self.client.get("/")
        pq = PyQuery(r.content)
        link_elements = pq(".toctree-wrapper a.internal")
        self.toc_urls = [l.attrib["href"] for l in link_elements]

    @task(50)
    def load_page(self, url=None):
        url = random.choice(self.toc_urls)
        r = self.client.get(url)
        pq = PyQuery(r.content)
        link_elements = pq("a.internal")
        self.urls_on_current_page = [l.attrib["href"] for l in link_elements]

    @task(30)
    def load_sub_page(self):
        url = random.choice(self.urls_on_current_page)
        r = self.client.get(url)


class AwesomeUser(HttpUser):
    tasks = [BrowseDocumentation]
    host = "https://docs.locust.io/en/latest/"

    # we assume someone who is browsing the Locust docs,
    # generally has a quite long waiting time (between 
    # 20 and 600 seconds), since there's a bunch of text
    # on each page
    # 我们假设某人正在浏览Locust文档,通常需要很长的等待时间(在20到600秒之间)，因为每一页上都有很多文本
    wait_time = between(20, 600)
