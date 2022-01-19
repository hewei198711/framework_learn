import gevent
from gevent import Greenlet

g = Greenlet(gevent.sleep, 4)
g.start()
g.kill()
g.dead