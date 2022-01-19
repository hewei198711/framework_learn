import gevent
from gevent import monkey
 
 
# 切换是在 IO 操作时自动完成，所以gevent需要修改Python自带的一些标准库
# 这一过程在启动时通过monkey patch完成
monkey.patch_all()
 
 
def func_a():
    while 1:
        print('-------A-------')
        # 用来模拟一个耗时操作，注意不是time模块中的sleep
        # 每当碰到耗时操作，会自动跳转至其他协程
        gevent.sleep(2)
        print("*************")

        
 
 
def func_b():
    while 1:
        print('-------B-------')
        gevent.sleep(1)
        print("+++++++++++++++")
 
 
# gevent.joinall([gevent.spawn(fn)
g1 = gevent.spawn(func_a)  # 创建一个协程
g2 = gevent.spawn(func_b)
g1.join()  # 等待协程执行结束
g2.join()