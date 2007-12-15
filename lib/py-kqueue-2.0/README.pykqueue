	py-kqueue module, version 2.0
      -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

This is a Python glue for kqueue(2)/kevent(2) event interface on
BSD systems.

kqueue() provides a generic method of notifying the user when an
event happens or a condition holds, based on the results of small
pieces of kernel code termed filters.  A kevent is identified by
the (ident, filter) pair; there may only be one unique kevent
per kqueue.

See the manpages for further information on kqueue system interface.
File pykqueue.txt (part of the module distribution) describes
the Python module API, which mirrors the system interface to most extend.

This module has been written and originally debugged on NetBSD 1.6K
with Python 2.2. It has also been tested on FreeBSD 4.7.

Features
-------
* exposes kqueue(2)/kevent(2) system calls, EV_SET() function
  to create kevent objects, and kqueue constants (EVFILT_*, EV_*, NOTE_*)
* exposes KFILTER_BYNAME/KFILTER_BYFILTER ioctls (if supported by OS)
* kevent udata can be any Python object and is transparently
  passed to/from the above system calls
* easy to modify and extend
* written for Python 2.2, uses distutils
* confirmed working on NetBSD 1.6K, FreeBSD 4.7; should work in any
  later version too

Installation
------------
Python 2.2 or later is required. The package may be buildable
with any Python2, but that was not tested.

Steps:
1. python setup.py build
2. python setup.py install

That's it :)

Author
------
Jaromir Dolecek <jdolecek@NetBSD.org>
Any ideas, bugfixes and improvements are welcome. I'd especially
welcome patches to make this working on FreeBSD and/or OpenBSD.

Availability
------------
The tar ball with distribution can be downloaded from 
	ftp://ftp.NetBSD.org/pub/NetBSD/misc/jdolecek/
The file name is py-kqueue-VERSION.tar.bz2, where VERSION is 2.0 or anything
later. A package is available in NetBSD pkgsrc.

Why not PyKQueue?
-----------------
There is another, older project PyKQueue, by Doug White <dwhite@freebsd.org>.
As of this writing (Nov 9 2002), it only supported Python 1.5, used mix
of python-code and C-code and generally did not glue the interface
to Python OO very nicely. Clean rewrite seemed like better solution
than trying to hack PyKQueue, especially since it needed some changes
to work with NetBSD struct kevent definition anyway. 
py-kqueue doesn't contain any code from PyKQueue, not even any
ideas (unless by haphazard).

$Id: README.pykqueue,v 1.2 2002/11/24 09:19:42 dolecek Exp $
