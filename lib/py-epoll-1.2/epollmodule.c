/* py-epoll 1.0
   A Python module interface to epoll(4)
   Copyright (C) 2005 Ben Woolley <user ben at host tautology.org>
   Modified July 2007 by Jacob Potter

   This is free software; you can redistribute it and/or
   modify it under the terms of the GNU Lesser General Public
   License as published by the Free Software Foundation; either
   version 2.1 of the License, or (at your option) any later version.

   This is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   Lesser General Public License for more details.

   You should have received a copy of the GNU Lesser General Public
   License along with the GNU C Library; if not, write to the Free
   Software Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
   02111-1307 USA.  */

#include <Python.h>
#include <sys/epoll.h>

static PyObject * method_epoll_create(PyObject *self, PyObject *args) {

	int size;
	int sts;

	if (!PyArg_ParseTuple(args, "i", &size)) {
		return NULL;
	}

	sts = epoll_create(size);
	if (sts == -1) {
		PyErr_SetFromErrno(PyExc_OSError);
		return NULL;
	} else {
		return Py_BuildValue("i", sts);
	}
}

static PyObject * method_epoll_ctl(PyObject *self, PyObject *args) {

	struct epoll_event ev;

	int epfd;
	int epop;
	int fd;
	uint32_t epevents;

	int sts;

	if (!PyArg_ParseTuple(args, "iiik", &epfd, &epop, &fd, &epevents)) {
		return NULL;
	}

	ev.events = epevents;
	ev.data.fd = fd;

	sts = epoll_ctl(epfd, epop, fd, &ev);

	if (sts == -1) {
		PyErr_SetFromErrno(PyExc_OSError);
		return NULL;
	} else {
		return Py_BuildValue("i", sts);
	}
}

static PyObject * method_epoll_wait(PyObject *self, PyObject *args) {
	struct epoll_event *events;

	int kdpfd;
	int maxevents;
	int timeout;
	int nfds;
	int i;	

	PyObject *eplist;

	if (!PyArg_ParseTuple(args, "iii", &kdpfd, &maxevents, &timeout)) {
		return NULL;
	}

	events = (struct epoll_event*) malloc( sizeof(struct epoll_event) * maxevents );

	Py_BEGIN_ALLOW_THREADS;
	nfds = epoll_wait(kdpfd, events, maxevents, timeout);
	Py_END_ALLOW_THREADS;

	switch(nfds) {
	case -1:
		PyErr_SetFromErrno(PyExc_OSError);
		free(events);
		return NULL;
	case 0:
		free(events);
		return PyList_New (0);
	default:
		eplist = PyList_New (nfds);

		for (i = 0; i < nfds; i++) {
			int evevents;
			int evfd;
			PyObject *eptuple;

			evevents = events[i].events;
			evfd = events[i].data.fd;
			eptuple = Py_BuildValue("ki", evevents, evfd);

			PyList_SET_ITEM(eplist, i, eptuple);
		}

		free(events);
		return eplist;
	}
}

static PyMethodDef EpollMethods[] = {
	{
		"epoll_create",
		method_epoll_create,
		METH_VARARGS,
		"epoll_create(size) = 0\n"
		"\n"
		"Direct interface to epoll_create(2), except that errors are turned into Python exceptions. \n"
		"Example creating an epoll file descriptor with an initial backing store of 10 events: \n"
		"\n"
		"from epoll import *\n"
		"epfd = epoll_create(10)"
	},
	{
		"epoll_ctl",
		method_epoll_ctl,
		METH_VARARGS,
		"epoll_ctl(epfd, op, fd, event_mask) = 0\n"
		"\n"
		"Direct interface to epoll_ctl(2), except that errors are turned into Python exceptions, and "
		"the last argument of struct epoll_event is split up into two arguments corresponding to "
		"epoll_event.events and epoll_event.data.fd so that it has one more argument than the actual "
		"syscall does. \n"
		"Example for telling epoll that it will need to watch for incoming connections to a non-blocking "
		"server socket: \n"
		"\n"
		"epoll_ctl(epfd, EPOLL_CTL_ADD, server.fileno(), EPOLLIN, server.fileno())"
	},
	{
		"epoll_wait",
		method_epoll_wait,
		METH_VARARGS,
		"epoll_wait(epfd, maxevents, timeout) = [] or [(events, udata), ...]\n"
		"\n"
		"Direct interface to epoll_wait(2), except that errors are turned into Python exceptions, "
		"and that you ignore the second argument of struct epoll_event, which will be returned as a "
		"list of tuples (epop, udata) where epop is the set of events that have been triggered "
		"and udata is whatever was passed in the last parameter of epoll_ctl().\n"
		"Example asking for up to 10 events, polling for 1 second: \n"
		"\n"
		"events = epoll.epoll_wait(epfd, 10, 1000)"
	},
	{ NULL, NULL, 0, NULL }
};

static void insint (PyObject *d, char *name, int value) {
	PyObject *v = PyInt_FromLong((long) value);
	if (!v || PyDict_SetItemString(d, name, v)) {
		PyErr_Clear();
	}

	Py_XDECREF(v);
}

PyMODINIT_FUNC initepoll(void) {
	PyObject *m;

	m = Py_InitModule("epoll", EpollMethods);

	PyObject * d = PyModule_GetDict (m);

	insint (d, "EPOLLIN", EPOLLIN);
	insint (d, "EPOLLOUT", EPOLLOUT);
	insint (d, "EPOLLPRI", EPOLLPRI);
	insint (d, "EPOLLERR", EPOLLERR);
	insint (d, "EPOLLHUP", EPOLLHUP);
	insint (d, "EPOLLET", EPOLLET);
	insint (d, "EPOLLONESHOT", EPOLLONESHOT);

	insint (d, "EPOLL_CTL_ADD", EPOLL_CTL_ADD);
	insint (d, "EPOLL_CTL_MOD", EPOLL_CTL_MOD);
	insint (d, "EPOLL_CTL_DEL", EPOLL_CTL_DEL);

	PyModule_AddStringConstant(m, "__doc__", "Direct interface to the Linux epoll(4) API, for handling asynchronous I/O.");
}
