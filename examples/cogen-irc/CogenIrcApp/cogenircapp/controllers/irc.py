import logging

from pylons import request, response, session
from pylons import tmpl_context as c
from pylons.controllers.util import abort, redirect_to, url_for
from pylons.decorators import validate
from formencode import validators
from cogenircapp.lib.base import BaseController
import cogenircapp.model as model

log = logging.getLogger(__name__)



from cogen.core.coroutines import coro, debug_coroutine
from cogen.core import events, sockets
from cogen.core.util import priority
from cogen.core import queue
from cogen.web import async

import simplejson
import time
import socket

def parsemsg(s): # stolen from twisted.words
    """Breaks a message from an IRC server into its prefix, command, and arguments.
    """
    prefix = ''
    trailing = []
    if not s:
        raise Exception("Empty line.")
    if s[0] == ':':
        prefix, s = s[1:].split(' ', 1)
    if s.find(' :') != -1:
        s, trailing = s.split(' :', 1)
        args = s.split()
        args.append(trailing)
    else:
        args = s.split()
    command = args.pop(0)
    return prefix, command, args
    
class Connection:
    def __init__(self, server, reconnect_interval=60, sock_timo=45):
        self.server = server
        self.reconnect_interval = reconnect_interval
        self.connected = False
        self.sock_timo = sock_timo
        self.events = queue.Queue(100) # Max pending events, well, messages 
                    # from the server. After that we'll lose the connection.
        self.last_pull = time.time()
    @debug_coroutine
    def pull(self):
        """This coroutine handles the server connection, does a basic parse on
        the received messages and put them in a queue named events.
        The controllers pull method will take the messages from that queue.
        """
        self.sock = sockets.Socket()
        self.sock.settimeout(self.sock_timo)
        yield events.AddCoro(self.monitor)
        while not self.connected:
            try:
                addr = self.server.split(':')
                if len(addr) < 2:
                    addr.append(6667)
                else:
                    addr[1] = int(addr[1])
                yield self.events.put(('', 'CONNECTING', ''), timeout=self.sock_timo)
                yield self.sock.connect(tuple(addr))
                self.connected = True
            except events.OperationTimeout, e:
                yield self.events.put(('', 'CONNECT_TIMEOUT', str(e)), timeout=self.sock_timo)
                yield events.Sleep(self.reconnect_interval)
                
        yield self.events.put_nowait(('', 'CONNECTED', ''))
        fobj = self.sock.makefile()
        while 1:
            try:
                line = yield fobj.readline(8192)
                prefix, command, params = parsemsg(line.rstrip('\r\n'))    
                if command in numeric_events:
                    command = numeric_events[command].upper()
                print 'PULLME:', (prefix, command, params)
                yield self.events.put((prefix, command, params), timeout=self.sock_timo)
            except Exception, e:
                yield self.events.put(('', 'ERROR', str(e)), timeout=self.sock_timo)
                break
    @coro
    def monitor(self):
        while 1:
            yield events.Sleep(60)
            if self.last_update + 65 < time.time():
                self.sock.shutdown(socket.SHUT_RDWR)

from pylons.templating import render_mako as render

class IrcController(BaseController):
    """
    This controller supports multiple server connections.
    """
    def index(self):
        request.environ['beaker.session']._sess
        if 'connections' not in session:
            session['connections'] = {}
            session.save()
        yield 'bla'

    def push(self, id):
        "Sends a message to the specified connection (id)"
        conn = session['connections'].get(id, None)
        if conn:
            msgs = simplejson.loads(request.body)
            for msg in msgs:
                try:
                    cmd = msg.pop(0).upper()
                    assert ' ' not in cmd, "Bad message"
                    if cmd in ('USER', ):
                        sufix = " :"+msg.pop() 
                    else:
                        sufix = ''
                    assert not [i for i in msg if ' ' in i], "Bad message"
                    
                    print 'PUSH:', (cmd, msg, sufix)
                    
                    if msg:
                        payload = "%s %s%s\r\n" % (cmd, ' '.join(msg), sufix)
                    else:
                        payload = "%s%s\r\n" % (cmd, sufix)
                    yield request.environ['cogen.call'](conn.sock.sendall)(
                            payload.encode('utf-8'))
                    if isinstance(request.environ['cogen.wsgi'].result, Exception):
                        yield simplejson.dumps(('', 'ERROR', str(e)))
                    else:
                        yield simplejson.dumps(('', 'PUSH_OK', ''))
                except Exception, e:
                    yield simplejson.dumps(('', 'ERROR', str(e)))
        else:
            yield simplejson.dumps(('', 'ERROR', 'Invalid connection id.'))
    
    def connect(self, server):
        "Connects to a server and return a connection id."
        if 'connections' not in session:
            session['connections'] = {}
            session.save()
            
        conns = session['connections']
        id = str(len(conns))
        conn = Connection(server)
        conns[id] = conn
        yield request.environ['cogen.core'].events.AddCoro(conn.pull)
        yield id
            
    def pull(self, id):
        """Take the messages from the queue and if there are none wait 30 
        seconds till returning an empty message.
        
        Also, cogen's wsgi async extensions are in the environ and prefixed with
        'cogen.'
        """
        conn = session['connections'].get(id, None)
        conn.last_update = time.time()
        if conn:
            ev_list = []
            while 1:
                # ok, so this might look a bit ugly but the concept is very simple
                #  you yield a special object from the environ that does some magic
                #  and the wsgi server will resume the app when it has the result
                yield request.environ['cogen.call'](conn.events.get)(timeout=0.1)
                event = request.environ['cogen.wsgi'].result
                # also, we can't have better exception handling in this wsgi
                # contraption and we need to check the result for exceptions
                if not event:
                    break
                elif isinstance(event, (queue.Empty, events.OperationTimeout)):
                    break
                elif isinstance(event, Exception):
                    ev_list.append(('', 'ERROR', str(event)))
                    break
                else:
                    ev_list.append(event)
            if ev_list:        
                print 'PULL:', ev_list
                yield simplejson.dumps(ev_list)
            else:
                # if we don't have any updates atm, we'll wait 30 secs for one
                yield request.environ['cogen.call'](conn.events.get)(timeout=30)
                event = request.environ['cogen.wsgi'].result
                if isinstance(event, events.OperationTimeout):
                    yield simplejson.dumps([])
                elif isinstance(event, Exception):
                    yield simplejson.dumps([('', 'ERROR', str(event))])
                else:
                    print 'PULL1:', event
                    yield simplejson.dumps([event])
        else:
            yield simplejson.dumps(('', 'ERROR', 'Invalid connection id.'))



numeric_events = {
    "001": "welcome",
    "002": "yourhost",
    "003": "created",
    "004": "myinfo",
    "005": "featurelist",
    "200": "tracelink",
    "201": "traceconnecting",
    "202": "tracehandshake",
    "203": "traceunknown",
    "204": "traceoperator",
    "205": "traceuser",
    "206": "traceserver",
    "207": "traceservice",
    "208": "tracenewtype",
    "209": "traceclass",
    "210": "tracereconnect",
    "211": "statslinkinfo",
    "212": "statscommands",
    "213": "statscline",
    "214": "statsnline",
    "215": "statsiline",
    "216": "statskline",
    "217": "statsqline",
    "218": "statsyline",
    "219": "endofstats",
    "221": "umodeis",
    "231": "serviceinfo",
    "232": "endofservices",
    "233": "service",
    "234": "servlist",
    "235": "servlistend",
    "241": "statslline",
    "242": "statsuptime",
    "243": "statsoline",
    "244": "statshline",
    "250": "luserconns",
    "251": "luserclient",
    "252": "luserop",
    "253": "luserunknown",
    "254": "luserchannels",
    "255": "luserme",
    "256": "adminme",
    "257": "adminloc1",
    "258": "adminloc2",
    "259": "adminemail",
    "261": "tracelog",
    "262": "endoftrace",
    "263": "tryagain",
    "265": "n_local",
    "266": "n_global",
    "300": "none",
    "301": "away",
    "302": "userhost",
    "303": "ison",
    "305": "unaway",
    "306": "nowaway",
    "311": "whoisuser",
    "312": "whoisserver",
    "313": "whoisoperator",
    "314": "whowasuser",
    "315": "endofwho",
    "316": "whoischanop",
    "317": "whoisidle",
    "318": "endofwhois",
    "319": "whoischannels",
    "321": "liststart",
    "322": "list",
    "323": "listend",
    "324": "channelmodeis",
    "329": "channelcreate",
    "331": "notopic",
    "332": "currenttopic",
    "333": "topicinfo",
    "341": "inviting",
    "342": "summoning",
    "346": "invitelist",
    "347": "endofinvitelist",
    "348": "exceptlist",
    "349": "endofexceptlist",
    "351": "version",
    "352": "whoreply",
    "353": "namreply",
    "361": "killdone",
    "362": "closing",
    "363": "closeend",
    "364": "links",
    "365": "endoflinks",
    "366": "endofnames",
    "367": "banlist",
    "368": "endofbanlist",
    "369": "endofwhowas",
    "371": "info",
    "372": "motd",
    "373": "infostart",
    "374": "endofinfo",
    "375": "motdstart",
    "376": "endofmotd",
    "377": "motd2",      
    "381": "youreoper",
    "382": "rehashing",
    "384": "myportis",
    "391": "time",
    "392": "usersstart",
    "393": "users",
    "394": "endofusers",
    "395": "nousers",
    "401": "nosuchnick",
    "402": "nosuchserver",
    "403": "nosuchchannel",
    "404": "cannotsendtochan",
    "405": "toomanychannels",
    "406": "wasnosuchnick",
    "407": "toomanytargets",
    "409": "noorigin",
    "411": "norecipient",
    "412": "notexttosend",
    "413": "notoplevel",
    "414": "wildtoplevel",
    "421": "unknowncommand",
    "422": "nomotd",
    "423": "noadmininfo",
    "424": "fileerror",
    "431": "nonicknamegiven",
    "432": "erroneusnickname", 
    "433": "nicknameinuse",
    "436": "nickcollision",
    "437": "unavailresource",  
    "441": "usernotinchannel",
    "442": "notonchannel",
    "443": "useronchannel",
    "444": "nologin",
    "445": "summondisabled",
    "446": "usersdisabled",
    "451": "notregistered",
    "461": "needmoreparams",
    "462": "alreadyregistered",
    "463": "nopermforhost",
    "464": "passwdmismatch",
    "465": "yourebannedcreep", 
    "466": "youwillbebanned",
    "467": "keyset",
    "471": "channelisfull",
    "472": "unknownmode",
    "473": "inviteonlychan",
    "474": "bannedfromchan",
    "475": "badchannelkey",
    "476": "badchanmask",
    "477": "nochanmodes",  
    "478": "banlistfull",
    "481": "noprivileges",
    "482": "chanoprivsneeded",
    "483": "cantkillserver",
    "484": "restricted",   
    "485": "uniqopprivsneeded",
    "491": "nooperhost",
    "492": "noservicehost",
    "501": "umodeunknownflag",
    "502": "usersdontmatch",
}
