#!/usr/pkg/bin/python

from kqueue import *
t = open("/tmp/foo.q", "w+")
kev = EV_SET(t.fileno(), EVFILT_READ, EV_ADD | EV_ENABLE)
kq = kqueue()
kev.udata = (1, 2, 3, 4)
kq.kevent(kev)
del(kev)
q = kq.kevent(None, 3)
print q
print "Foo: ", t.read()
q = kq.kevent(None, 3)
