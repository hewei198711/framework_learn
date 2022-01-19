# -*- coding: utf-8 -*-
import logging
import random
import socket
import sys
import traceback
import warnings
from uuid import uuid4
from time import time

import gevent
import greenlet
import psutil
from gevent.pool import Group

from . import User
from .log import greenlet_exception_logger
from .rpc import Message, rpc
from .stats import RequestStats, setup_distributed_stats_event_listeners

from .exception import RPCError
from .user.task import LOCUST_STATE_STOPPING


logger = logging.getLogger(__name__)


STATE_INIT, STATE_SPAWNING, STATE_RUNNING, STATE_CLEANUP, STATE_STOPPING, STATE_STOPPED, STATE_MISSING = [
    "ready",  # 准备好了
    "spawning",  # 孵化中
    "running",  # 运行中
    "cleanup",  # 清理
    "stopping",  # 停止中
    "stopped",  # 停止
    "missing",  # 失踪
]
WORKER_REPORT_INTERVAL = 3.0  # 工人报告时间间隔
CPU_MONITOR_INTERVAL = 5.0  # CPU监视时间间隔
HEARTBEAT_INTERVAL = 1  # 心跳间隔
HEARTBEAT_LIVENESS = 3  # 心跳活性
FALLBACK_INTERVAL = 5  # 回退时间间隔


# 一种绿色小鸟异常处理程序
greenlet_exception_handler = greenlet_exception_logger(logger)


class Runner(object):
    """
    Orchestrates the load test by starting and stopping the users.
    通过启动和停止用户来编排负载测试。

    Use one of the :meth:`create_local_runner <locust.env.Environment.create_local_runner>`,
    :meth:`create_master_runner <locust.env.Environment.create_master_runner>` or
    :meth:`create_worker_runner <locust.env.Environment.create_worker_runner>` methods on
    the :class:`Environment <locust.env.Environment>` instance to create a runner of the
    desired type.

    使用其中一个:meth:`create_local_runner <locust.env.Environment.create_local_runner>`,
    :meth:`create_master_runner <locust.env.Environment.create_master_runner>` or
    :meth:`create_worker_runner <locust.env.Environment.create_worker_runner>` methods on
    the :class:`Environment <locust.env.Environment>`实例创建所需类型的运行程序。
    """

    def __init__(self, environment):
        self.environment = environment
        self.user_greenlets = Group()
        self.greenlet = Group()
        self.state = STATE_INIT  # 准备好了
        self.spawning_greenlet = None  # 产生一种绿色小鸟
        self.stepload_greenlet = None  # 步进加载一种绿色小鸟
        self.shape_greenlet = None  # 形成一种绿色小鸟
        self.shape_last_state = None  # 准备好后的形状
        self.current_cpu_usage = 0  # 当前的cpu使用率
        self.cpu_warning_emitted = False  # cpu发出警告
        self.greenlet.spawn(self.monitor_cpu).link_exception(greenlet_exception_handler)
        self.exceptions = {}
        self.target_user_count = None  # 目标用户数量

        # set up event listeners for recording requests
        # 设置记录请求的事件监听器
        def on_request_success(request_type, name, response_time, response_length, **kwargs):
            self.stats.log_request(request_type, name, response_time, response_length)

        def on_request_failure(request_type, name, response_time, response_length, exception, **kwargs):
            self.stats.log_request(request_type, name, response_time, response_length)
            self.stats.log_error(request_type, name, exception)

        self.environment.events.request_success.add_listener(on_request_success)
        self.environment.events.request_failure.add_listener(on_request_failure)
        self.connection_broken = False  # 连接断了

        # register listener that resets stats when spawning is complete
        # 产卵完成后注册侦听器重置统计
        def on_spawning_complete(user_count):
            self.state = STATE_RUNNING
            if environment.reset_stats:
                logger.info("Resetting stats\n")
                self.stats.reset_all()

        self.environment.events.spawning_complete.add_listener(on_spawning_complete)

    def __del__(self):
        # don't leave any stray greenlets if runner is removed
        # 如果被移除，不要留下任何迷路的绿草
        if self.greenlet and len(self.greenlet) > 0:
            self.greenlet.kill(block=False)

    @property
    def user_classes(self):
        return self.environment.user_classes

    @property
    def stats(self) -> RequestStats:
        return self.environment.stats

    @property
    def errors(self):
        return self.stats.errors

    @property
    def user_count(self):
        """
        :returns: Number of currently running users
        当前运行用户数
        """
        return len(self.user_greenlets)

    def cpu_log_warning(self):
        """
        Called at the end of the test to repeat the warning & return the status
        在测试结束时调用，以重复警告并返回状态（提醒应该考虑分布式压测了）
        """
        if self.cpu_warning_emitted:
            # 在测试期间的某个时刻，CPU使用率过高，如何在多个CPU内核或机器上分配负载
            logger.warning(
                "CPU usage was too high at some point during the test! "
                "See https://docs.locust.io/en/stable/running-locust-distributed.html "
                "for how to distribute the load over multiple CPU cores or machines"
            )
            return True
        return False

    def weight_users(self, amount):
        """
        Distributes the amount of users for each WebLocust-class according to it's weight
        returns a list "bucket" with the weighted users
        根据权重分发各个users类占有的并发数量bucket，amount为总并发数
        """
        bucket = []
        weight_sum = sum([user.weight for user in self.user_classes])
        residuals = {} # 残差
        for user in self.user_classes:
            if self.environment.host is not None:
                user.host = self.environment.host

            # create users depending on weight
            # 根据权重创建用户
            percent = user.weight / float(weight_sum)
            num_users = int(round(amount * percent))
            bucket.extend([user for x in range(num_users)])
            # used to keep track of the amount of rounding was done if we need
            # to add/remove some instances from bucket
            # 用于跟踪在我们需要从桶中添加/删除一些实例时完成的量
            residuals[user] = amount * percent - round(amount * percent)
        if len(bucket) < amount:
            # We got too few User classes in the bucket, so we need to create a few extra users,
            # and we do this by iterating over each of the User classes - starting with the one
            # where the residual from the rounding was the largest - and creating one of each until
            # we get the correct amount
            # 如果我们得到用户类比要求的少,我们就需要遍历对比残差值，那个用户类的残差值最大，就添加一个该用户类，直到bucket和aomount相等,
            # 直到我们得到正确的数量
            for user in [l for l, r in sorted(residuals.items(), key=lambda x: x[1], reverse=True)][
                : amount - len(bucket)
            ]:
                bucket.append(user)
        elif len(bucket) > amount:
            # We've got too many users due to rounding errors so we need to remove some
            # 如果我们得到的用户类比要求的多，我们就对比残差值，哪个用户类的残差值最小，就删除一个该用户类
            for user in [l for l, r in sorted(residuals.items(), key=lambda x: x[1])][: len(bucket) - amount]:
                bucket.remove(user)

        return bucket

    # 生成用户
    def spawn_users(self, spawn_count, spawn_rate, wait=False):
        # 执行压力测试并发任务
        # spawn_count： 并发数
        # spawn_rate：孵化速率
        # wait： task任务执行间隔
        bucket = self.weight_users(spawn_count) # 把并发数分到各个user类
        spawn_count = len(bucket)
        
        # 如果是首次启动/重启性能测试，状态为孵化中？
        if self.state == STATE_INIT or self.state == STATE_STOPPED:
            self.state = STATE_SPAWNING

        existing_count = len(self.user_greenlets)  # 现有的用户数
        # 报告以多快的速度生成多大的用户数（现在已生成多少用户数）
        logger.info(
            "Spawning %i users at the rate %g users/s (%i users already running)..."
            % (spawn_count, spawn_rate, existing_count)
        )
        # 获取每一个user_class,初始执行次数为0
        occurrence_count = dict([(l.__name__, 0) for l in self.user_classes])

        def spawn():
            sleep_time = 1.0 / spawn_rate
            while True:
                if not bucket:
                    # 当bucket为空时，表示已经孵化完成
                    logger.info(
                        "All users spawned: %s (%i already running)"
                        % (
                            ", ".join(["%s: %d" % (name, count) for name, count in occurrence_count.items()]),
                            existing_count,
                        )
                    )
                    self.environment.events.spawning_complete.fire(user_count=len(self.user_greenlets))
                    return
                # 从并发任务中随机抽取一个user_class执行
                user_class = bucket.pop(random.randint(0, len(bucket) - 1))
                # 将被执行的user_class+1
                occurrence_count[user_class.__name__] += 1
                new_user = user_class(self.environment)
                new_user.start(self.user_greenlets)
                if len(self.user_greenlets) % 10 == 0:
                    logger.debug("%i users spawned" % len(self.user_greenlets))
                if bucket:
                    gevent.sleep(sleep_time)

        # 执行压力测试
        spawn()
        # 如果添加了wait参数，则暂停所有的user
        if wait:
            self.user_greenlets.join()
            logger.info("All users stopped\n")

    def stop_users(self, user_count, stop_rate=None):
        """
        Stop `user_count` weighted users at a rate of `stop_rate`
        以“stop_rate”的比率停止“user_count”加权用户
        """
        if user_count == 0 or stop_rate == 0:
            return

        bucket = self.weight_users(user_count)
        user_count = len(bucket)
        to_stop = []
        for g in self.user_greenlets:
            for l in bucket:
                user = g.args[0]
                if isinstance(user, l):
                    to_stop.append(user)
                    bucket.remove(l)
                    break

        if not to_stop:
            return

        if stop_rate is None or stop_rate >= user_count:
            sleep_time = 0
            logger.info("Stopping %i users" % (user_count))
        else:
            sleep_time = 1.0 / stop_rate
            logger.info("Stopping %i users at rate of %g users/s" % (user_count, stop_rate))

        async_calls_to_stop = Group()
        stop_group = Group()

        while True:
            user_to_stop: User = to_stop.pop(random.randint(0, len(to_stop) - 1))
            logger.debug("Stopping %s" % user_to_stop._greenlet.name)
            if user_to_stop._greenlet is greenlet.getcurrent():
                # User called runner.quit(), so dont block waiting for killing to finish"
                # 用户调用了runner.quit()，所以不要阻止等待杀死完成
                user_to_stop._group.killone(user_to_stop._greenlet, block=False)
            elif self.environment.stop_timeout:
                async_calls_to_stop.add(gevent.spawn_later(0, User.stop, user_to_stop, force=False))
                stop_group.add(user_to_stop._greenlet)
            else:
                async_calls_to_stop.add(gevent.spawn_later(0, User.stop, user_to_stop, force=True))
            if to_stop:
                gevent.sleep(sleep_time)
            else:
                break

        async_calls_to_stop.join()

        if not stop_group.join(timeout=self.environment.stop_timeout):
            # 并不是所有用户都在%s秒内完成任务&终止。阻止他们
            logger.info(
                "Not all users finished their tasks & terminated in %s seconds. Stopping them..."
                % self.environment.stop_timeout
            )
            stop_group.kill(block=True)
        # 用户已被停止
        logger.info("%i Users have been stopped" % user_count)

    def monitor_cpu(self):
        process = psutil.Process()
        while True:
            self.current_cpu_usage = process.cpu_percent()
            if self.current_cpu_usage > 90 and not self.cpu_warning_emitted:
                # CPU使用率超过90%!这可能会限制您的吞吐量，甚至可能给出不一致的响应时间度量!如何在多个CPU内核或机器上分配负载
                logging.warning(
                    "CPU usage above 90%! This may constrain your throughput and may even give inconsistent response "
                    "time measurements! See https://docs.locust.io/en/stable/running-locust-distributed.html "
                    "for how to distribute the load over multiple CPU cores or machines"
                )
                self.cpu_warning_emitted = True
            gevent.sleep(CPU_MONITOR_INTERVAL)

    def start(self, user_count, spawn_rate, wait=False):
        """
        Start running a load test
        开始运行负载测试
        :param user_count: Number of users to start
        :param spawn_rate: Number of users to spawn per second每秒生成的用户数量
        :param wait: If True calls to this method will block until all users are spawned.
                     If False (the default), a greenlet that spawns the users will be
                     started and the call to this method will return immediately.
        如果为True，则对该方法的调用将阻塞，直到生成所有用户。如果为False(默认值)，则会启动一个生成用户的greenlet，并立即返回对该方法的调用。
        """
        if self.state != STATE_RUNNING and self.state != STATE_SPAWNING:
            self.stats.clear_all()
            self.exceptions = {}
            self.cpu_warning_emitted = False
            self.worker_cpu_warning_emitted = False
            self.target_user_count = user_count

        if self.state != STATE_INIT and self.state != STATE_STOPPED:
            logger.debug(
                "Updating running test with %d users, %.2f spawn rate and wait=%r" % (user_count, spawn_rate, wait)
            )
            self.state = STATE_SPAWNING
            if self.user_count > user_count:
                # Stop some users
                stop_count = self.user_count - user_count
                self.stop_users(stop_count, spawn_rate)
            elif self.user_count < user_count:
                # Spawn some users
                spawn_count = user_count - self.user_count
                self.spawn_users(spawn_count=spawn_count, spawn_rate=spawn_rate)
            else:
                self.environment.events.spawning_complete.fire(user_count=self.user_count)
        else:
            self.spawn_rate = spawn_rate
            self.spawn_users(user_count, spawn_rate=spawn_rate, wait=wait)

    def start_stepload(self, user_count, spawn_rate, step_user_count, step_duration):
        if user_count < step_user_count:
            logger.error(
                "Invalid parameters: total user count of %d is smaller than step user count of %d"
                % (user_count, step_user_count)
            )
            return
        self.total_users = user_count

        if self.stepload_greenlet:
            logger.info("There is an ongoing swarming in Step Load mode, will stop it now.")
            self.stepload_greenlet.kill()
        logger.info(
            "Start a new swarming in Step Load mode: total user count of %d, spawn rate of %d, step user count of %d, step duration of %d "
            % (user_count, spawn_rate, step_user_count, step_duration)
        )
        self.state = STATE_INIT
        self.stepload_greenlet = self.greenlet.spawn(self.stepload_worker, spawn_rate, step_user_count, step_duration)
        self.stepload_greenlet.link_exception(greenlet_exception_handler)

    def stepload_worker(self, spawn_rate, step_users_growth, step_duration):
        current_num_users = 0
        while self.state == STATE_INIT or self.state == STATE_SPAWNING or self.state == STATE_RUNNING:
            current_num_users += step_users_growth
            if current_num_users > int(self.total_users):
                logger.info("Step Load is finished")
                break
            self.start(current_num_users, spawn_rate)
            logger.info("Step loading: start spawn job of %d user" % (current_num_users))
            gevent.sleep(step_duration)

    def start_shape(self):
        if self.shape_greenlet:
            logger.info("There is an ongoing shape test running. Editing is disabled")
            return

        logger.info("Shape test starting. User count and spawn rate are ignored for this type of load test")
        self.state = STATE_INIT
        self.shape_greenlet = self.greenlet.spawn(self.shape_worker)
        self.shape_greenlet.link_exception(greenlet_exception_handler)

    def shape_worker(self):
        logger.info("Shape worker starting")
        while self.state == STATE_INIT or self.state == STATE_SPAWNING or self.state == STATE_RUNNING:
            new_state = self.environment.shape_class.tick()
            if new_state is None:
                logger.info("Shape test stopping")
                self.stop()
            elif self.shape_last_state == new_state:
                gevent.sleep(1)
            else:
                user_count, spawn_rate = new_state
                logger.info("Shape test updating to %d users at %.2f spawn rate" % (user_count, spawn_rate))
                self.start(user_count=user_count, spawn_rate=spawn_rate)
                self.shape_last_state = new_state

    def stop(self):
        """
        Stop a running load test by stopping all running users
        通过停止所有正在运行的用户来停止正在运行的负载测试
        """
        self.state = STATE_CLEANUP
        # if we are currently spawning users we need to kill the spawning greenlet first
        # 如果我们目前正在生成用户，我们需要先杀死生成的greenlet
        if self.spawning_greenlet and not self.spawning_greenlet.ready():
            self.spawning_greenlet.kill(block=True)
        self.stop_users(self.user_count)
        self.state = STATE_STOPPED
        self.cpu_log_warning()

    def quit(self):
        """
        Stop any running load test and kill all greenlets for the runner
        停止任何正在运行的负载测试并终止运行器的所有greenlet
        """
        self.stop()
        self.greenlet.kill(block=True)

    def log_exception(self, node_id, msg, formatted_tb):
        key = hash(formatted_tb)
        row = self.exceptions.setdefault(key, {"count": 0, "msg": msg, "traceback": formatted_tb, "nodes": set()})
        row["count"] += 1
        row["nodes"].add(node_id)
        self.exceptions[key] = row


class LocalRunner(Runner):
    """
    Runner for running single process load test
    用于运行单流程负载测试的转轮
    """

    def __init__(self, environment):
        """
        :param environment: Environment instance
        """
        super().__init__(environment)

        # register listener thats logs the exception for the local runner
        # 注册记录本地运行器异常的侦听器
        def on_user_error(user_instance, exception, tb):
            formatted_tb = "".join(traceback.format_tb(tb))
            self.log_exception("local", str(exception), formatted_tb)

        self.environment.events.user_error.add_listener(on_user_error)

    def start(self, user_count, spawn_rate, wait=False):
        self.target_user_count = user_count
        # 你选择的刷出率非常高(>100)，这是众所周知的，有时会导致问题。你真的需要这么快吗?
        if spawn_rate > 100:
            logger.warning(
                "Your selected spawn rate is very high (>100), and this is known to sometimes cause issues. Do you really need to ramp up that fast?"
            )

        if self.state != STATE_RUNNING and self.state != STATE_SPAWNING:
            # if we're not already running we'll fire the test_start event
            # 如果我们还没有运行，我们将触发test_start事件
            self.environment.events.test_start.fire(environment=self.environment)

        if self.spawning_greenlet:
            # kill existing spawning_greenlet before we start a new one
            # 在我们开始一个新的greenlet之前，杀死现有的spawning_greenlet
            self.spawning_greenlet.kill(block=True)
        self.spawning_greenlet = self.greenlet.spawn(
            lambda: super(LocalRunner, self).start(user_count, spawn_rate, wait=wait)
        )
        self.spawning_greenlet.link_exception(greenlet_exception_handler)

    def stop(self):
        if self.state == STATE_STOPPED:
            return
        super().stop()
        self.environment.events.test_stop.fire(environment=self.environment)


class DistributedRunner(Runner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 设置分布式统计事件侦听器
        setup_distributed_stats_event_listeners(self.environment.events, self.stats)


class WorkerNode(object):
    def __init__(self, id, state=STATE_INIT, heartbeat_liveness=HEARTBEAT_LIVENESS):
        self.id = id
        self.state = state
        self.user_count = 0
        self.heartbeat = heartbeat_liveness
        self.cpu_usage = 0
        self.cpu_warning_emitted = False


class MasterRunner(DistributedRunner):
    """
    Runner used to run distributed load tests across multiple processes and/or machines.
    用于跨多个进程和/或计算机运行分布式负载测试的运行程序

    MasterRunner doesn't spawn any user greenlets itself. Instead it expects
    :class:`WorkerRunners <WorkerRunner>` to connect to it, which it will then direct
    to start and stop user greenlets. Stats sent back from the
    :class:`WorkerRunners <WorkerRunner>` will aggregated.
    MasterRunner本身不会生成任何用户greenlet。
    相反，它期望:class: ' WorkerRunners &lt;WorkerRunner&gt; '连接到它，然后它将引导它启动和停止用户greenlets。
    从:class: ' WorkerRunners &lt;WorkerRunner&gt; '发回的统计信息将被聚合。
    """

    def __init__(self, environment, master_bind_host, master_bind_port):
        """
        :param environment: Environment instance 环境实例
        :param master_bind_host: Host/interface to use for incoming worker connections 用于传入worker连接的主机/接口
        :param master_bind_port: Port to use for incoming worker connections 用于传入worker连接的端口
        """
        super().__init__(environment)
        self.worker_cpu_warning_emitted = False
        self.master_bind_host = master_bind_host
        self.master_bind_port = master_bind_port

        class WorkerNodesDict(dict):
            # 设置worker节点的压测状态
            def get_by_state(self, state):
                return [c for c in self.values() if c.state == state]

            @property
            def all(self):
                return self.values()

            @property
            def ready(self):
                return self.get_by_state(STATE_INIT)

            @property
            def spawning(self):
                return self.get_by_state(STATE_SPAWNING)

            @property
            def running(self):
                return self.get_by_state(STATE_RUNNING)

            @property
            def missing(self):
                return self.get_by_state(STATE_MISSING)

        self.clients = WorkerNodesDict()
        # 绑定master节点远程rpc调用服务器
        try:
            self.server = rpc.Server(master_bind_host, master_bind_port)
        except RPCError as e:
            # 套接字绑定失败:地址已被使用
            if e.args[0] == "Socket bind failure: Address already in use":
                port_string = master_bind_host + ":" + master_bind_port if master_bind_host != "*" else master_bind_port
                logger.error(
                    f"The Locust master port ({port_string}) was busy. Close any applications using that port - perhaps an old instance of Locust master is still running? ({e.args[0]})"
                )
                # 蝗虫的master port被占用。关闭使用该端口的任何应用程序—也许一个旧的Locust master实例仍在运行?
                sys.exit(1)
            else:
                raise

        self.greenlet.spawn(self.heartbeat_worker).link_exception(greenlet_exception_handler)
        self.greenlet.spawn(self.client_listener).link_exception(greenlet_exception_handler)

        # listener that gathers info on how many users the worker has spawned
        # 侦听器，该侦听器收集关于worker生成了多少用户的信息
        def on_worker_report(client_id, data):
            if client_id not in self.clients:
                # 不认识的工人丢弃的报告
                logger.info("Discarded report from unrecognized worker %s", client_id)
                return

            self.clients[client_id].user_count = data["user_count"]

        self.environment.events.worker_report.add_listener(on_worker_report)

        # register listener that sends quit message to worker nodes
        # 注册发送退出消息到工作节点的侦听器
        def on_quitting(environment, **kw):
            self.quit()

        self.environment.events.quitting.add_listener(on_quitting)

    # user_count属性，用以返回各worker节点并发数之和
    @property
    def user_count(self):
        return sum([c.user_count for c in self.clients.values()])

    def cpu_log_warning(self):
        warning_emitted = Runner.cpu_log_warning(self)
        if self.worker_cpu_warning_emitted:
            # 在测试期间，workers的CPU使用率超过了阈值!
            logger.warning("CPU usage threshold was exceeded on workers during the test!")
            warning_emitted = True
        return warning_emitted

    def start(self, user_count, spawn_rate):
        """
        user_count: 并发任务数量
        spawn_rate：每秒并发数
        """
        self.target_user_count = user_count
        num_workers = len(self.clients.ready) + len(self.clients.running) + len(self.clients.spawning)
        if not num_workers:
            logger.warning(
                "You are running in distributed mode but have no worker servers connected. "
                "Please connect workers prior to swarming."
            )
            # 您在分布式模式下运行，但没有连接任何worker服务器。请在蜂群前连接workers。
            return

        self.spawn_rate = spawn_rate
        worker_num_users = user_count // (num_workers or 1)
        worker_spawn_rate = float(spawn_rate) / (num_workers or 1)
        remaining = user_count % num_workers
        # 发送用户数量和孵化速率。和准备好的客户端
        logger.info(
            "Sending spawn jobs of %d users and %.2f spawn rate to %d ready clients"
            % (worker_num_users, worker_spawn_rate, num_workers)
        )
        # 你选择的刷出率非常高(>100/工人)，这是众所周知的，有时会导致问题。你真的需要这么快吗?
        if worker_spawn_rate > 100:
            logger.warning(
                "Your selected spawn rate is very high (>100/worker), and this is known to sometimes cause issues. Do you really need to ramp up that fast?"
            )

        if self.state != STATE_RUNNING and self.state != STATE_SPAWNING:
            self.stats.clear_all()
            self.exceptions = {}
            self.environment.events.test_start.fire(environment=self.environment)

        for client in self.clients.ready + self.clients.running + self.clients.spawning:
            data = {
                "spawn_rate": worker_spawn_rate,
                "num_users": worker_num_users,
                "host": self.environment.host,
                "stop_timeout": self.environment.stop_timeout,
            }

            if remaining > 0:
                data["num_users"] += 1
                remaining -= 1

            self.server.send_to_client(Message("spawn", data, client.id))

        self.state = STATE_SPAWNING

    def stop(self):
        if self.state not in [STATE_INIT, STATE_STOPPED, STATE_STOPPING]:
            self.state = STATE_STOPPING

            if self.environment.shape_class:
                self.shape_last_state = None

            for client in self.clients.all:
                self.server.send_to_client(Message("stop", None, client.id))
            self.environment.events.test_stop.fire(environment=self.environment)

    def quit(self):
        if self.state not in [STATE_INIT, STATE_STOPPED, STATE_STOPPING]:
            # fire test_stop event if state isn't already stopped
            # 如果状态尚未停止，则触发test_stop事件
            self.environment.events.test_stop.fire(environment=self.environment)

        for client in self.clients.all:
            self.server.send_to_client(Message("quit", None, client.id))
        gevent.sleep(0.5)  # wait for final stats report from all workers 等待所有workers的最终统计报告
        self.greenlet.kill(block=True)

    def check_stopped(self):
        if not self.state == STATE_INIT and all(
            map(lambda x: x.state != STATE_RUNNING and x.state != STATE_SPAWNING, self.clients.all)
        ):
            self.state = STATE_STOPPED

    # worker的心跳
    def heartbeat_worker(self):
        while True:
            gevent.sleep(HEARTBEAT_INTERVAL)
            if self.connection_broken: # 连接断了
                self.reset_connection()
                continue

            for client in self.clients.all:
                if client.heartbeat < 0 and client.state != STATE_MISSING:
                    # worker发送心跳失败，将状态设置为丢失。
                    logger.info("Worker %s failed to send heartbeat, setting state to missing." % str(client.id))
                    client.state = STATE_MISSING
                    client.user_count = 0
                    if self.worker_count - len(self.clients.missing) <= 0:
                        logger.info("The last worker went missing, stopping test.") # 最后一个worker失踪了，停止了测试
                        self.stop()
                        self.check_stopped()
                else:
                    client.heartbeat -= 1

    def reset_connection(self):
        logger.info("Reset connection to worker")
        try:
            self.server.close()
            self.server = rpc.Server(self.master_bind_host, self.master_bind_port)
        except RPCError as e:
            # 重新设置连接时临时失败:%s，将稍后重试。
            logger.error("Temporary failure when resetting connection: %s, will retry later." % (e))
    # 客户端监听器
    def client_listener(self):
        while True:
            try:
                client_id, msg = self.server.recv_from_client()
            except RPCError as e:
                # 从客户端接收时发现的RPCError:
                logger.error("RPCError found when receiving from client: %s" % (e))
                self.connection_broken = True
                gevent.sleep(FALLBACK_INTERVAL)
                continue
            self.connection_broken = False
            msg.node_id = client_id
            if msg.type == "client_ready":
                id = msg.node_id
                self.clients[id] = WorkerNode(id, heartbeat_liveness=HEARTBEAT_LIVENESS)
                logger.info(
                    "Client %r reported as ready. Currently %i clients ready to swarm."
                    % (id, len(self.clients.ready + self.clients.running + self.clients.spawning))
                )
                if self.state == STATE_RUNNING or self.state == STATE_SPAWNING:
                    # balance the load distribution when new client joins
                    # 在新客户端加入时平衡负载分配
                    self.start(self.target_user_count, self.spawn_rate)
                # emit a warning if the worker's clock seem to be out of sync with our clock 如果worker的时钟与我们的时钟不同步，则发出警告
                # if abs(time() - msg.data["time"]) > 5.0:
                #      warnings.warn("The worker node's clock seem to be out of sync. For the statistics to be correct the different locust servers need to have synchronized clocks.")
                # 工作节点的时钟似乎不同步。要使统计数据正确，不同的蝗虫服务器需要有同步的时钟。
            elif msg.type == "client_stopped":
                del self.clients[msg.node_id]
                logger.info("Removing %s client from running clients" % (msg.node_id))
            elif msg.type == "heartbeat":
                if msg.node_id in self.clients:
                    c = self.clients[msg.node_id]
                    c.heartbeat = HEARTBEAT_LIVENESS
                    c.state = msg.data["state"]
                    c.cpu_usage = msg.data["current_cpu_usage"]
                    if not c.cpu_warning_emitted and c.cpu_usage > 90:
                        self.worker_cpu_warning_emitted = True  # used to fail the test in the end
                        c.cpu_warning_emitted = True  # used to suppress logging for this node
                        logger.warning(
                            "Worker %s exceeded cpu threshold (will only log this once per worker)" % (msg.node_id)
                        )
            elif msg.type == "stats":
                self.environment.events.worker_report.fire(client_id=msg.node_id, data=msg.data)
            elif msg.type == "spawning":
                self.clients[msg.node_id].state = STATE_SPAWNING
            elif msg.type == "spawning_complete":
                self.clients[msg.node_id].state = STATE_RUNNING
                self.clients[msg.node_id].user_count = msg.data["count"]
                if len(self.clients.spawning) == 0:
                    count = sum(c.user_count for c in self.clients.values())
                    self.environment.events.spawning_complete.fire(user_count=count)
            elif msg.type == "quit":
                if msg.node_id in self.clients:
                    del self.clients[msg.node_id]
                    logger.info(
                        "Client %r quit. Currently %i clients connected." % (msg.node_id, len(self.clients.ready))
                    )
                    if self.worker_count - len(self.clients.missing) <= 0:
                        logger.info("The last worker quit, stopping test.")
                        self.stop()
                        if self.environment.parsed_options and self.environment.parsed_options.headless:
                            self.quit()
            elif msg.type == "exception":
                self.log_exception(msg.node_id, msg.data["msg"], msg.data["traceback"])

            self.check_stopped()

    @property
    def worker_count(self):
        return len(self.clients.ready) + len(self.clients.spawning) + len(self.clients.running)


class WorkerRunner(DistributedRunner):
    """
    Runner used to run distributed load tests across multiple processes and/or machines.

    WorkerRunner connects to a :class:`MasterRunner` from which it'll receive
    instructions to start and stop user greenlets. The WorkerRunner will periodically
    take the stats generated by the running users and send back to the :class:`MasterRunner`.
    """

    def __init__(self, environment, master_host, master_port):
        """
        :param environment: Environment instance
        :param master_host: Host/IP to use for connection to the master
        :param master_port: Port to use for connecting to the master
        """
        super().__init__(environment)
        self.worker_state = STATE_INIT
        self.client_id = socket.gethostname() + "_" + uuid4().hex
        self.master_host = master_host
        self.master_port = master_port
        self.client = rpc.Client(master_host, master_port, self.client_id)
        self.greenlet.spawn(self.heartbeat).link_exception(greenlet_exception_handler)
        self.greenlet.spawn(self.worker).link_exception(greenlet_exception_handler)
        self.client.send(Message("client_ready", None, self.client_id))
        self.greenlet.spawn(self.stats_reporter).link_exception(greenlet_exception_handler)

        # register listener for when all users have spawned, and report it to the master node
        def on_spawning_complete(user_count):
            self.client.send(Message("spawning_complete", {"count": user_count}, self.client_id))
            self.worker_state = STATE_RUNNING

        self.environment.events.spawning_complete.add_listener(on_spawning_complete)

        # register listener that adds the current number of spawned users to the report that is sent to the master node
        def on_report_to_master(client_id, data):
            data["user_count"] = self.user_count

        self.environment.events.report_to_master.add_listener(on_report_to_master)

        # register listener that sends quit message to master
        def on_quitting(environment, **kw):
            self.client.send(Message("quit", None, self.client_id))

        self.environment.events.quitting.add_listener(on_quitting)

        # register listener thats sends user exceptions to master
        def on_user_error(user_instance, exception, tb):
            formatted_tb = "".join(traceback.format_tb(tb))
            self.client.send(Message("exception", {"msg": str(exception), "traceback": formatted_tb}, self.client_id))

        self.environment.events.user_error.add_listener(on_user_error)

    def heartbeat(self):
        while True:
            try:
                self.client.send(
                    Message(
                        "heartbeat",
                        {"state": self.worker_state, "current_cpu_usage": self.current_cpu_usage},
                        self.client_id,
                    )
                )
            except RPCError as e:
                logger.error("RPCError found when sending heartbeat: %s" % (e))
                self.reset_connection()
            gevent.sleep(HEARTBEAT_INTERVAL)

    def reset_connection(self):
        logger.info("Reset connection to master")
        try:
            self.client.close()
            self.client = rpc.Client(self.master_host, self.master_port, self.client_id)
        except RPCError as e:
            logger.error("Temporary failure when resetting connection: %s, will retry later." % (e))

    def worker(self):
        while True:
            try:
                msg = self.client.recv()
            except RPCError as e:
                logger.error("RPCError found when receiving from master: %s" % (e))
                continue
            if msg.type == "spawn":
                self.worker_state = STATE_SPAWNING
                self.client.send(Message("spawning", None, self.client_id))
                job = msg.data
                self.spawn_rate = job["spawn_rate"]
                self.target_user_count = job["num_users"]
                self.environment.host = job["host"]
                self.environment.stop_timeout = job["stop_timeout"]
                if self.spawning_greenlet:
                    # kill existing spawning greenlet before we launch new one
                    self.spawning_greenlet.kill(block=True)
                self.spawning_greenlet = self.greenlet.spawn(
                    lambda: self.start(user_count=job["num_users"], spawn_rate=job["spawn_rate"])
                )
                self.spawning_greenlet.link_exception(greenlet_exception_handler)
            elif msg.type == "stop":
                self.stop()
                self.client.send(Message("client_stopped", None, self.client_id))
                self.client.send(Message("client_ready", None, self.client_id))
                self.worker_state = STATE_INIT
            elif msg.type == "quit":
                logger.info("Got quit message from master, shutting down...")
                self.stop()
                self._send_stats()  # send a final report, in case there were any samples not yet reported
                self.greenlet.kill(block=True)

    def stats_reporter(self):
        while True:
            try:
                self._send_stats()
            except RPCError as e:
                logger.error("Temporary connection lost to master server: %s, will retry later." % (e))
            gevent.sleep(WORKER_REPORT_INTERVAL)

    def _send_stats(self):
        data = {}
        self.environment.events.report_to_master.fire(client_id=self.client_id, data=data)
        self.client.send(Message("stats", data, self.client_id))
