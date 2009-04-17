import sys
import errno
from socket import error as soerror
try:
    import sendfile
except:
    sendfile = None

from ..coroutines import CoroutineException
from ..sockets import Socket, SocketError, ConnectionClosed
from ..util import priority


def perform_recv(act):
    act.buff = act.sock._fd.recv(act.len)
    if act.buff:
        return act
    else:
        raise ConnectionClosed("Empty recv.")

def perform_send(act):
    act.sent = act.sock._fd.send(act.buff)
    return act.sent and act

def perform_sendall(act):
    act.sent += act.sock._fd.send(act.buff[act.sent:])
    return act.sent==len(act.buff) and act

def perform_accept(act):
    act.conn, act.addr = act.sock._fd.accept()
    act.conn.setblocking(0)
    act.conn = act.sock.__class__(_sock=act.conn)
    return act

def perform_connect(act):
    if act.connect_attempted:
        try:
            act.sock._fd.getpeername()
        except soerror, exc:
            if exc[0] not in (errno.EAGAIN, errno.EWOULDBLOCK,
                            errno.EINPROGRESS, errno.ENOTCONN):
                return
        return act
    err = act.sock._fd.connect_ex(act.addr)
    act.connect_attempted = True
    if err:
        if err == errno.EISCONN:
            return act
        if err not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS):
            raise SocketError(err, errno.errorcode[err])
    else: # err==0 means successful connect
        return act

def wrapped_sendfile(act, offset, length):
    """
    Calls the sendfile system call or simulate with file read and socket send if
    unavailable.
    """
    if sendfile:
        offset, sent = sendfile.sendfile(
            act.sock.fileno(),
            act.file_handle.fileno(),
            offset, length
        )
    else:
        act.file_handle.seek(offset)
        sent = act.sock._fd.send(act.file_handle.read(length))
    return sent

def perform_sendfile(act):
    if act.length:
        if act.blocksize:
            act.sent += wrapped_sendfile(
                act,
                act.offset + act.sent,
                min(act.length-act.sent, act.blocksize)
            )
        else:
            act.sent += wrapped_sendfile(act, act.offset+act.sent, act.length-act.sent)
        if act.sent == act.length:
            return act
    else:
        if act.blocksize:
            sent = wrapped_sendfile(act, act.offset+act.sent, act.blocksize)
        else:
            sent = wrapped_sendfile(act, act.offset+act.sent, act.blocksize)
            # we would use self.length but we don't have any,
            #  and we don't know the file's length
        act.sent += sent
        if not sent:
            return act

class ProactorBase(object):
    """
    Base class for a proactor implemented with posix-style polling.



    """
    supports_multiplex_first = True

    def __init__(self, scheduler, resolution, **options):
        self.tokens = {}
        self.scheduler = scheduler
        self.resolution = resolution # seconds
        self.m_resolution = resolution*1000 # miliseconds
        self.n_resolution = resolution*1000000000 #nanoseconds
        self.set_options(**options)

    def __str__(self):
        return "<%s [%s]>" % (self.__class__.__name__, self.tokens)

    __repr__ = __str__

    def set_options(self, multiplex_first=True, **bogus_options):
        "Takes implementation specific options. To be overriden in a subclass."
        self.multiplex_first = multiplex_first
        self._warn_bogus_options(**bogus_options)

    def _warn_bogus_options(self, **opts):
        """
        Shows a warning for unsupported options for the current implementation.
        Called form set_options with remainig unsupported options.
        """
        if opts:
            import warnings
            for i in opts:
                warnings.warn("Unsupported option %s for %s" % (i, self), stacklevel=2)

    def __len__(self):
        return len(self.tokens)

    def request_recv(self, act, coro):
        "Requests a recv for `coro` corutine with parameters and completion \
        passed via `act`"
        return self.request_generic(act, coro, perform_recv)

    def request_send(self, act, coro):
        "Requests a send for `coro` corutine with parameters and completion \
        passed via `act`"
        return self.request_generic(act, coro, perform_send)

    def request_sendall(self, act, coro):
        "Requests a sendall for `coro` corutine with parameters and completion \
        passed via `act`"
        return self.request_generic(act, coro, perform_sendall)

    def request_accept(self, act, coro):
        "Requests a accept for `coro` corutine with parameters and completion \
        passed via `act`"
        return self.request_generic(act, coro, perform_accept)

    def request_connect(self, act, coro):
        "Requests a connect for `coro` corutine with parameters and completion \
        passed via `act`"
        result = self.try_run_act(act, perform_connect)
        if result:
            return result, coro
        else:
            self.add_token(act, coro, perform_connect)

    def request_sendfile(self, act, coro):
        "Requests a sendfile for `coro` corutine with parameters and completion \
        passed via `act`"
        return self.request_generic(act, coro, perform_sendfile)

    def request_generic(self, act, coro, perform):
        """
        Requests an socket operation (in the form of a callable `perform` that
        does the actual socket system call) for `coro` corutine with parameters
        and completion passed via `act`.

        The socket operation request parameters are passed in `act`.
        When request is completed the results will be set in `act`.

        Note: `act` is usualy a SocketOperation instance and the request_foo
        calls are usually made from a Foo subclass.
        """
        result = self.multiplex_first and self.try_run_act(act, perform)
        if result:
            return result, coro
        else:
            self.add_token(act, coro, perform)


    def add_token(self, act, coro, performer):
        """
        Adds a completion token `act` in the proactor with associated `coro`
        corutine and perform callable.
        """
        assert act not in self.tokens
        act.coro = coro
        self.tokens[act] = performer
        self.register_fd(act, performer)

    def remove_token(self, act):
        """
        Remove a token from the proactor.
        If removal succeeds (the token is in the proactor) return True.
        """
        if act in self.tokens:
            self.unregister_fd(act)
            del self.tokens[act]
            return True
        else:
            import warnings
            warnings.warn("%s isn't a registered token." % act)

    def close(self):
        for act in self.tokens:
            self.unregister_fd(act)
        self.tokens.clear()


    def try_run_act(self, act, func):
        try:
            return self.run_act(act, func)
        except:
            return CoroutineException(*sys.exc_info())

    def run_act(self, act, func):
        try:
            return func(act)
        except soerror, exc:
            if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS):
                return
            elif exc[0] == errno.EPIPE:
                raise ConnectionClosed(exc)
            else:
                raise SocketError(exc)


    def register_fd(self, act, performer):
        """
        Perform additional handling (like register the socket file descriptor in
        the poll, epoll, kqueue, iocp etc) when a token is added in the proactor.

        Overriden in a subclass.
        """

        pass

    def unregister_fd(self, act, fd=None):
        """
        Perform additional handling (like cleanup) when a token is removed from
        the proactor.

        Overriden in a subclass.
        """
        pass


    def handle_event(self, act):
        """
        Handle completion for a request.

        Calls the scheduler to run or schedule the associated coroutine.
        """

        if act in self.tokens:
            coro = act.coro
            op = self.try_run_act(act, self.tokens[act])
            if op:
                del self.tokens[act]
                if self.scheduler.ops_greedy:
                    while True:
                        op, coro = self.scheduler.process_op(coro.run_op(op), coro)
                        if not op and not coro:
                            break
                else:
                    if op.prio & priority.OP:
                        op, coro = self.scheduler.process_op(coro.run_op(op), coro)
                    if coro and op:
                        if op.prio & priority.CORO:
                            self.scheduler.active.appendleft( (op, coro) )
                        else:
                            self.scheduler.active.append( (op, coro) )
            else:
                return
        else:
            import warnings
            warnings.warn("Got event for unkown act: %s" % act)
        return True

    def yield_event(self, act):
        """
        Hande completion for a request and return an (op, coro) to be
        passed to the scheduler on the last completion loop of a proactor.
        """
        if act in self.tokens:
            coro = act.coro
            op = self.try_run_act(act, self.tokens[act])
            if op:
                del self.tokens[act]
                return op, coro

    def handle_error_event(self, act, detail, exc=SocketError):
        """
        Handle an errored event. Calls the scheduler to schedule the associated
        coroutine.
        """
        del self.tokens[act]
        self.scheduler.active.append((
            CoroutineException(exc, exc(detail)),
            act.coro
        ))

