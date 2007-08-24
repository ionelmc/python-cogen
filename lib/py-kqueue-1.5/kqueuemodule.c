/*-
 * Copyright (c) 2000 Doug White
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 *
 */

/* kqueuemodule.c: Python module for kqueue support.
 * Version 1.1 (Added copyright)
 *
 * Doug White
 * 
 */

#include <Python.h>
#include "structmember.h"
#include <stdio.h>
#include <errno.h>
#include <time.h>
#include <sys/types.h>
#include <sys/event.h>

#define MAX_KEVENTS 512

// ----------------------------------------------------------------------
//			    KQEventObject
// ----------------------------------------------------------------------

typedef struct {
  PyObject_HEAD
  struct kevent e;
} KQEventObject;

staticforward PyTypeObject KQEvent_Type;

#define KQEventObject_Check(v)  ((v)->ob_type == &KQEvent_Type)

static KQEventObject *
newKQEventObject (PyObject *arg)
{
  // return PyObject_New (KQEventObject, &KQEvent_Type);
  return PyObject_NEW (KQEventObject, &KQEvent_Type);
}

/* KQEvent methods */

static void
KQEvent_dealloc(KQEventObject *self)
{
  // PyObject_Del(self);
  PyMem_DEL (self);
}

// --------------------------------------------------------------------------------
#define OFF(x) offsetof(KQEventObject, x)

//      struct kevent {
// 	     uintptr_t ident;	     /* identifier for this event */
// 	     short     filter;	     /* filter for event */
// 	     u_short   flags;	     /* action flags for kqueue */
// 	     u_int     fflags;	     /* filter flag value */
// 	     intptr_t  data;	     /* filter data value */
// 	     void      *udata;	     /* opaque user data identifier */
//      };

static struct memberlist KQEvent_memberlist[] = {
  {"ident",	T_UINT,		OFF(e.ident)},
  {"filter",	T_SHORT,	OFF(e.filter)},
  {"flags",	T_USHORT,	OFF(e.flags)},
  {"fflags",	T_UINT,		OFF(e.fflags)},
  {"data",	T_INT,		OFF(e.data)},
  {"udata",	T_OBJECT,	OFF(e.udata)},
  {NULL}	/* Sentinel */
};

static PyObject *
KQEvent_getattr(KQEventObject *f, char *name)
{
  return PyMember_Get((char *)f, KQEvent_memberlist, name);
}

static int
KQEvent_setattr(KQEventObject *f, char *name, PyObject *value)
{
  return PyMember_Set((char *)f, KQEvent_memberlist, name, value);
}

#if 0
static
void
dump_kevent (struct kevent * k)
{
  fprintf (
    stderr,
    "kevent(%d,%d,%x,%x,%x,%p)",
    k->ident,
    k->filter,
    k->flags,
    k->fflags,
    k->data,
    k->udata
    );
}
#endif

static PyObject *
KQEvent_repr(KQEventObject *s)
{
  char buf[1024];
  snprintf (
      buf,
      sizeof(buf),
      "<KQEvent ident=%d filter=%d flags=%x fflags=%x data=%x udata=%p>",
      s->e.ident, s->e.filter, s->e.flags, s->e.fflags, s->e.data, s->e.udata
      );
  return PyString_FromString(buf);
}

statichere PyTypeObject KQEvent_Type = {
  PyObject_HEAD_INIT(NULL)
  0,                             // ob_size
  "KQEvent",                     // tp_name
  sizeof(KQEventObject),         // tp_basicsize
  0,                             // tp_itemsize
  //  methods 
  (destructor)KQEvent_dealloc,   // tp_dealloc
  0,                             // tp_print
  (getattrfunc)KQEvent_getattr,  // tp_getattr
  (setattrfunc)KQEvent_setattr,  // tp_setattr
  0,                             // tp_compare
  (reprfunc)KQEvent_repr,        // tp_repr
  0,                             // tp_as_number
  0,                             // tp_as_sequence
  0,                             // tp_as_mapping
  0,                             // tp_hash
};

static PyObject *
kqsyscall_kevent_descriptor (PyObject *self, PyObject *args)
{
  KQEventObject *rv = newKQEventObject (args);
  if (!rv) {
    return NULL;
  } else {
    // defaults
    rv->e.ident  = 0;
    rv->e.filter = EVFILT_READ;
    rv->e.flags  = EV_ADD | EV_ENABLE;
    rv->e.fflags = 0;
    rv->e.data   = 0;
    rv->e.udata  = NULL;
    
    if (!PyArg_ParseTuple (args, "i|hhiiO:KEvent",
			   &(rv->e.ident),
			   &(rv->e.filter),
			   &(rv->e.flags),
			   &(rv->e.fflags),
			   &(rv->e.data),
			   &(rv->e.udata))) {
      Py_DECREF (rv);
      return NULL;
    } else {
      return (PyObject *)rv;
    }
  }
}

// ----------------------------------------------------------------------
//			    KQueueObject
// ----------------------------------------------------------------------

typedef struct {
  PyObject_HEAD
  int fd;
} KQueueObject;

staticforward PyTypeObject KQueue_Type;

#define KQueueObject_Check(v)	((v)->ob_type == &KQueue_Type)

static KQueueObject *
newKQueueObject (PyObject *arg)
{
  KQueueObject * self = PyObject_NEW (KQueueObject, &KQueue_Type);
  if (!self) {
    PyErr_SetFromErrno (PyExc_MemoryError);
    return NULL;
  } else {
    int kqfd = kqueue();
    if (kqfd < 0) {
      PyMem_DEL (self);
      PyErr_SetFromErrno (PyExc_OSError);
      return NULL;
    } else {
      self->fd = kqfd;
      return self;
    }
  }
}

static PyObject *
KQueue_new (PyObject * self, PyObject * args)
{
  if (!PyArg_ParseTuple (args, "")) {
    return NULL;
  } else {
    return (PyObject *) newKQueueObject (args);
  }
}

/* KQueue methods */

static void
KQueue_dealloc(KQueueObject *self)
{
  close (self->fd);
  PyMem_DEL(self);
}

/* Call kevent(2) and do appropriate digestion of lists. */

static PyObject *
KQueue_kevent (KQueueObject * self, PyObject * args) 
{
  int wantNumEvents=0;
  int timeout=0;
  int haveNumEvents=0;
  int gotNumEvents=0;
  int i=0;
  PyObject *kelist, *output;
  struct kevent *changelist;
  struct kevent *triggered;
  struct timespec totimespec;
  
  if(!PyArg_ParseTuple(args, "O!ii", &PyList_Type, &kelist, &wantNumEvents, &timeout)) {
    return NULL;
  }
  
  haveNumEvents = PyList_Size (kelist);

  /* If there's no events to process, don't bother. */
  if(haveNumEvents > 0) {

    if(!(changelist = calloc(haveNumEvents, sizeof(struct kevent)))) {
      PyErr_SetFromErrno (PyExc_MemoryError);
      return NULL;
    }
    
    for(i=0; i < haveNumEvents; i++) {
      PyObject * ei = PyList_GET_ITEM (kelist, i);
      
      if (!KQEventObject_Check (ei)) {
	PyErr_SetString (PyExc_TypeError, "arg 1 must be a list of <KQEvent> objects");
	free (changelist);
	return NULL;
      } else {
	/* copy this kevent into the array */
	memcpy (&(changelist[i]), &(((KQEventObject *)ei)->e), sizeof(struct kevent));
      }
    }
  } else {
    changelist = NULL;
  }

  /* Allocate some space to hold the triggered events */
  if(!(triggered = calloc(wantNumEvents, sizeof(struct kevent)))) {
    free (changelist);
    PyErr_SetFromErrno(PyExc_MemoryError);
    return NULL;
  }

  /* Build timespec for timeout */
  totimespec.tv_sec = timeout / 1000;
  totimespec.tv_nsec = (timeout % 1000) * 100000;

  // printf("timespec: sec=%d nsec=%d\n", totimespec.tv_sec, totimespec.tv_nsec);

  /* Make the call */

  gotNumEvents = kevent (self->fd, changelist, haveNumEvents, triggered, wantNumEvents, &totimespec);

  /* Don't need the input event list anymore, so get rid of it */
  free (changelist);

  switch(gotNumEvents) {
    /* error */  
  case -1: 
    PyErr_SetFromErrno(PyExc_OSError);
    free(triggered);
    return NULL;
    break;

    /* timeout */
  case 0:
    /* return empty list */
    free(triggered);
    return PyList_New (0);
    break;

    /* Succeeded, got something back; return it in a list */
  default:
    if ((output = PyList_New (gotNumEvents)) == NULL) {
      free (triggered);
      return NULL;
    }

    for(i=0; i < gotNumEvents; i++) {
      KQEventObject * ke = newKQEventObject (NULL);

      if (!ke) {
	Py_DECREF (output);
	return NULL;
      } else {
	// copy event data into our struct
	memmove ((void*)&(ke->e), &(triggered[i]), sizeof(struct kevent));
	PyList_SET_ITEM (output, i, (PyObject *)ke);
      }
    }
    break;
  }
  free(triggered);
  /* pass back the results */
  return output;
}

static PyMethodDef KQueue_methods[] = {
  {"kevent",	(PyCFunction)KQueue_kevent,	1},
  {NULL,		NULL}		/* sentinel */
};

static PyObject *
KQueue_getattr(KQueueObject *self, char *name)
{
  if (strcmp (name, "fd") == 0) {
    return PyInt_FromLong (self->fd);
  } else {
    return Py_FindMethod(KQueue_methods, (PyObject *)self, name);
  }
}

statichere PyTypeObject KQueue_Type = {
	/* The ob_type field must be initialized in the module init function
	 * to be portable to Windows without using C++. */
	PyObject_HEAD_INIT(NULL)
	0,			/*ob_size*/
	"KQueue",			/*tp_name*/
	sizeof(KQueueObject),	/*tp_basicsize*/
	0,			/*tp_itemsize*/
	/* methods */
	(destructor)KQueue_dealloc, /*tp_dealloc*/
	0,			/*tp_print*/
	(getattrfunc)KQueue_getattr, /*tp_getattr*/
	0,			 /*tp_setattr*/
	0,			/*tp_compare*/
	0,			/*tp_repr*/
	0,			/*tp_as_number*/
	0,			/*tp_as_sequence*/
	0,			/*tp_as_mapping*/
	0,			/*tp_hash*/
};

// ----------------------------------------------------------------------
//			   module functions
// ----------------------------------------------------------------------


/* Method table */

static PyMethodDef KQSyscallMethods[] = {
  { "kqueue",			KQueue_new,			METH_VARARGS },
  { "kevent",			kqsyscall_kevent_descriptor,	METH_VARARGS },
  { NULL, NULL }
};

//
// Convenience routine to export an integer value.
//
// Errors are silently ignored, for better or for worse...
// [taken from socketmodule.c]
//

static void
insint (PyObject *d, char *name, int value)
{
  PyObject *v = PyInt_FromLong((long) value);
  if (!v || PyDict_SetItemString(d, name, v))
    PyErr_Clear();

  Py_XDECREF(v);
}

void
initkqueue(void)
{
  PyObject * m = Py_InitModule("kqueue", KQSyscallMethods);
  PyObject * d = PyModule_GetDict (m);

  // Constants

  // Event filters

  insint (d, "EVFILT_READ", EVFILT_READ);
  insint (d, "EVFILT_WRITE", EVFILT_WRITE);
  insint (d, "EVFILT_AIO", EVFILT_AIO);
  insint (d, "EVFILT_VNODE", EVFILT_VNODE);
  insint (d, "EVFILT_PROC", EVFILT_PROC);
  insint (d, "EVFILT_SIGNAL", EVFILT_SIGNAL);
  insint (d, "EVFILT_TIMER", EVFILT_TIMER);

  // Actions
  insint (d, "EV_ADD", EV_ADD);
  insint (d, "EV_DELETE", EV_DELETE);
  insint (d, "EV_ENABLE", EV_ENABLE);
  insint (d, "EV_DISABLE", EV_DISABLE);

  // Flags
  insint (d, "EV_ONESHOT", EV_ONESHOT);
  insint (d, "EV_CLEAR", EV_CLEAR);
  insint (d, "EV_SYSFLAGS", EV_SYSFLAGS);
  insint (d, "EV_FLAG1", EV_FLAG1);

  // Returned values
  insint (d, "EV_EOF", EV_EOF);
  insint (d, "EV_ERROR", EV_ERROR);

  // Kernel note flags (for EVFILT_{READ|WRITE} filter types

  insint (d, "NOTE_LOWAT", NOTE_LOWAT);

  // Kernel note flags (for VNODE filter types)

  insint (d, "NOTE_DELETE", NOTE_DELETE);
  insint (d, "NOTE_WRITE", NOTE_WRITE);
  insint (d, "NOTE_EXTEND", NOTE_EXTEND);
  insint (d, "NOTE_ATTRIB", NOTE_ATTRIB);
  insint (d, "NOTE_LINK", NOTE_LINK);
  insint (d, "NOTE_RENAME", NOTE_RENAME);
  insint (d, "NOTE_REVOKE", NOTE_REVOKE);

  // Kernel note flags (for PROC filter types)

  insint (d, "NOTE_EXIT", NOTE_EXIT);
  insint (d, "NOTE_FORK", NOTE_FORK);
  insint (d, "NOTE_EXEC", NOTE_EXEC);
  insint (d, "NOTE_PCTRLMASK", NOTE_PCTRLMASK);
  insint (d, "NOTE_PDATAMASK", NOTE_PDATAMASK);

  insint (d, "NOTE_TRACK", NOTE_TRACK);
  insint (d, "NOTE_TRACKERR", NOTE_TRACKERR);
  insint (d, "NOTE_CHILD", NOTE_CHILD);

}
