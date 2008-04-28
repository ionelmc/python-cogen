

var Connection = new Class({
    options: {
        onServerMessage: Class.empty, 
        onPrivateMessage: Class.empty,
        onError: Class.empty,
        onRemoveUser: Class.empty
    },
    
    initialize: function(server, nickname, channel, options){
        this.setOptions(options);
        this.connected = false;
        this.server = server;
        this.nickname = nickname;
        this.initial_channel = channel;
        this.pull = new XHR({
            method: 'get', 
            autoCancel: true,
            onSuccess: this.pull_success.bind(this),
            onFailure: this.pull_failure.bind(this)
        });
        this.push = new XHR({
            method: 'post', 
            onSuccess: this.push_success.bind(this),
            onFailure: this.push_failure.bind(this)
        });
        this.push.setHeader('Content-Type', 'text/json');
        this.pull.send('/connect/'+this.server, null);
        this.fireEvent('onConnect', this);
        this.channels = {};
        
    },
    
    pull_success: function (text) {
        if (!this.connected) {
            this.connected = true;
            this.id = text;
        } else {
            Json.evaluate(text).each(this.processMessage.bind(this));
        }
        this.pull.send('/pull/'+this.id);
    },
    
    pull_failure: function (ev) {
    
    },
    
    push_success: function (ev) {
    
    },
    
    push_failure: function (ev) {
    
    },
    
    processMessage: function(event) {
        var prefix = event[0],
            command = event[1],
            params = event[2];
        //~ if (['NOTICE', 'ERROR', 'CONNECTED', 'CONNECTING', 'CONNECT_TIMEOUT'].contains(command))
        console.log([prefix, command, params]);
        var handler = this['cmd_'+command];
        if (handler) {
            if (handler.call(this, prefix, params)) {
                // handler didn't do anything usefull with it, dump it in the status tab
                this.fireEvent('onServerMessage', [prefix, command, params]);
            }
        } else {
            this.fireEvent('onServerMessage', [prefix, command, params]);
        }
    },
    parsePrefix: function(prefix) {
        prefix = prefix.split('!', 2);
        
        var ret = { host: prefix.pop(), user:null };
        if (prefix.length) {
            ret.user = prefix.pop();
        }
        return ret;
    },
    channel: function(name) {
        var chan = this.channels[name];
        if (! chan) {
            this.channels[name] = chan = new Channel(this, name);
        }
        return chan;
    },
    cmd_CONNECTED: function(prefix, params) {
        var payload = Json.toString([
            ['USER', this.nickname, this.nickname, this.server, this.nickname],
            ['NICK', this.nickname],
            ['JOIN', this.initial_channel]
        ]);
        console.log(payload);
        this.push.send('/push/'+this.id, payload);        
    },
    cmd_PING: function(prefix, params) {
        this.push.send('/push/'+this.id, Json.toString([['PONG', params[0]]]));
    },
    cmd_NAMREPLY: function(prefix, params) {
        console.info('namerepl', params)
        var chan = params[2];
        var chantype = params[1];
        var users = params[3].trim().split(' ');
        console.info('namerepl', users);
        this.channel(chan).users.extend(users);
    },
    cmd_ENDOFNAMES: function(prefix, params) {
        this.channel(params[1]).fireEvent('onAddUsers', [this.channel(params[1]).users]);
    },
    cmd_JOIN: function(prefix, params) {
        var addr = this.parsePrefix(prefix);
        if (addr.user == this.nickname) {
            this.fireEvent('onChanJoin', [this, params[0]]);
        } else {
            this.channel(params[0]).fireEvent('onEvent', [sprintf("%s(%s) has joined %s.", addr.user, addr.host, params[0])]);    
            this.channel(params[0]).fireEvent('onAddUsers', [[addr.user]]);    
        }
    },
    cmd_QUIT: function(prefix, params) {
        var addr = this.parsePrefix(prefix);
        if (addr.user == this.nickname) {
            this.fireEvent('onChanPart', [this, params[1]]);
        } else {
            this.fireEvent('onRemoveUser', [addr.user, params[1 ]]);    
        }
    },
    cmd_PART: function(prefix, params) {
        this.cmd_QUIT(prefix, params);
    },
    cmd_PRIVMSG: function(prefix, params) {
        var target = params[0];
        var message = params[1];
        var addr = this.parsePrefix(prefix);
        if (target[0] == '#') {
            this.channel(params[0]).fireEvent('onMessage', [addr.user, message]);    
        } else {
            return true;
        }
    //~ },
    //~ cmd_: function(prefix, params) {
    }
});
Connection.implement(new Events, new Options);

var Channel = new Class({
    options: {
        onMessage: Class.empty,
        onPart: Class.empty,
        onEvent: Class.empty,
        onAddUsers: Class.empty
    },
    initialize: function(conn, name) {
        this.conn = conn;
        this.name = name;
        this.users = []
    }
});
Channel.implement(new Events, new Options);

var Context = new Class({
    changeTab: function(event) {
        this.app.changeTab(this.id);
    },
    checkInput: function(event) {
        var event = new Event(event);
        if (event.key == 'enter') {
            var val = this.input.getValue();
            this.input.value = '';
            this.processInput(val);
        }
    },
    initialize: function(type, conn, name, app, id){
        this.type = type;
        this.conn = conn;
        this.name = name;
        this.app = app;
        this.id = id;
        
        if (this.type == 'status' || this.type == 'query') {
            this.tab = EL('li', {id:'tab_'+this.id}, EL('a', {href:"#"}, "Status: "+conn.server))
                
            this.cnt = EL('div', {id:'cnt_'+this.id, 'class':'status'}, 
                    this.text = EL('div', {'class':'textarea', id:'text_'+this.id}, '--- Status for ' + this.conn.server + ' ---'),
                    this.input = EL('input', {'class':'inputarea', id:'input_'+this.id})
            )
        }
        if (this.type == 'chan') {
            this.tab = EL('li', {id:'tab_'+this.id}, EL('a', {href:"#"}, this.name))
            this.cnt = EL('div', {id:'cnt_'+this.id, 'class':'channel'}, 
                this.text = EL('div', {'class':'textarea', id:'text_'+this.id}, 'Joining '+this.name),
                this.userlist = EL('div', {'class':'userlist', id:'userlist_'+this.id}),
                this.input = EL('input', {'class':'inputarea', id:'input_'+this.id})
            )
        }
        this.app.addTab(this);
        this.tab.addEvent("click", this.changeTab.bind(this));
        this.input.addEvent("keydown", this.checkInput.bind(this));
        if (this.type == 'status') {
            this.conn.addEvent('onServerMessage', this.printStatus.bind(this));
        }
        if (this.type == 'chan') {
            this.conn.channel(this.name).addEvent('onMessage',  this.printChanMessage.bind(this));
            this.conn.channel(this.name).addEvent('onEvent',    this.printChanEvent.bind(this));
            this.conn.channel(this.name).addEvent('onAddUsers', this.addUsers.bind(this));
            this.conn.addEvent('onRemoveUser', this.removeUser.bind(this));
        }
        console.debug("EVENTS REGISTERED FOR "+this.name);
        //~ tab.injectInside("tabbar");
        //~ cnt.injectInside("tabcontents");
    },
    addUsers: function(users) {
        users.each(function(user) {
            EL('span', {}, user).inject(this.userlist);
            this.userlist.appendText(' ');
        }.bind(this));
    },
    removeUser: function(user, reason) {
        console.error(this.userlist.getChildren());
        this.userlist.getChildren().each(function (el) {
            console.info(el, el.getText(), user);
            if (el.getText() == user) {
                el.remove();
                this.printChanEvent(sprintf("%s has left %s (%s).", user, this.name, reason));
            }
        }.bind(this));
    },
    printChanEvent: function(event) {
        var time = new Date();
        var line = EL('div', {'class':'line'}, 
            EL('span', {'class':'time'}, "["+time.getHours()+":"+time.getMinutes()+":"+time.getSeconds()+"]"), ' ', 
            EL('span', {'class':'event'}, "*"), ' ', 
            EL('span', {'class':'event_message'}, event));
        line.injectInside(this.text);
        new Fx.Scroll("text_"+this.id).set(0).toBottom();
    },
    printChanMessage: function(user, message) {
        var time = new Date();
        var line = EL('div', {'class':'line'}, 
            EL('span', {'class':'time'}, "["+time.getHours()+":"+time.getMinutes()+":"+time.getSeconds()+"]"), ' ', 
            EL('span', {'class':'user'}, "<"+user+">"), ' ', 
            EL('span', {'class':'message'}, message));
        line.injectInside(this.text);
        new Fx.Scroll("text_"+this.id).set(0).toBottom();
    },
    printStatus: function(prefix, command, params) {
        var time = new Date();
        var line = EL('div', {'class':'line'}, 
            EL('span', {'class':'time'}, "["+time.getHours()+":"+time.getMinutes()+":"+time.getSeconds()+"]"), ' ', 
            EL('span', {'class':'prefix'}, prefix), ' ', 
            EL('span', {'class':'command'}, command), ' ', 
            EL('span', {'class':'data'}, Json.toString(params)));
        line.injectInside(this.text);
        new Fx.Scroll("text_"+this.id).set(0).toBottom();
    },
    processInput: function (data) {
        if (this.type == 'chan') {
            if (data[0] == '/') {
                var args = data.split(' ', 2)
                var cmd = args.shift().slice(1);
                if (args.length) 
                    args = args.pop().split(' ');
                args.unshift(cmd);
                var payload = Json.toString([args]);
                console.log(payload);
                this.conn.push.send('/push/'+this.conn.id, payload);
            } else {
                this.conn.push.send('/push/'+this.conn.id, Json.toString([['PRIVMSG', this.name, data]]));
                this.printChanMessage(this.conn.nickname, data);
            }
        } 
        if (this.type == 'status') {
            var args = data.split(' ', 2)
            var cmd = args.shift();
            if (cmd[0] == '/') {
                cmd = cmd.slice(1)
            }
            if (args.length) 
                args = args.pop().split(' ');
            args.unshift(cmd);
            var payload = Json.toString([args]);
            console.log(payload);
            this.conn.push.send('/push/'+this.conn.id, payload);
        }
        if (this.type == 'query') {
            //TODO
        }
    }
});


var IRC = new Class({
    initialize: function() {
        this.connections = {};
        this.contexts = {};
        this.context_count = 0;
        this.currenttab = $('tab_connect');
        this.currentcnt = $('cnt_connect');
    },
    connect: function(server, nickname, channel) {
        $('connecting').setStyle('display', 'block');
        
        var conn = new Connection(server, nickname, channel, {
            onConnect: this.addConnection.bind(this),
            onChanJoin: this.addChannel.bind(this)
        });
    },
    changeTab: function(id) {
        if (this.currentcnt) {
            this.currentcnt.setStyle('display', 'none');
            this.currenttab.removeClass('active');
        }
        this.currentcnt = $('cnt_'+id);
        this.currenttab = $('tab_'+id);
        this.currentcnt.setStyle('display', 'block');
        this.currenttab.addClass('active');
        var input = $('input_'+id);
        if (input) input.focus();
    },
    addTab: function(ctx) {
        ctx.tab.injectInside("tabbar");
        ctx.cnt.injectInside("tabcontents");
        this.changeTab(ctx.id);
    },
    addConnection: function(conn) {
        this.connections[conn.id] = conn;
        var id = ++this.context_count;
        this.contexts[id] = new Context('status', conn, '[status]', this, id);
    },
    addChannel: function(conn, chan) {
        var id = ++this.context_count;
        this.contexts[id] = new Context('chan', conn, chan, this, id);
    }
});


window.addEvent('domready', function() {
    irc = new IRC();
    $('nickname_field').value = "Guest"+$random(10000,20000);
    $('connect_form').addEvent('submit', function (ev) {
        ev.preventDefault();
        irc.connect(
            $('server_field').getValue(),
            $('nickname_field').getValue(),
            $('channel_field').getValue()            
        );
    });
});
document.addEvent("keydown", function(event) {
    console.info(event);
}.bindAsEventListener());







function TEXT(str){
    return document.createTextNode(str);
}
function EL(type, props) {
    var el = new Element(type);
    for (var i=2; i<arguments.length; i++) {
        var child = arguments[i];
        if (child) { 
            if (typeof(child)=='string') {
                el.appendChild(TEXT(child));
            } else {
                el.appendChild(child);
            }
        }
    }
    return el.set(props);
}
function str_repeat(i, m) { for (var o = []; m > 0; o[--m] = i); return(o.join('')); }

function sprintf () {
  var i = 0, a, f = arguments[i++], o = [], m, p, c, x;
  while (f) {
    if (m = /^[^\x25]+/.exec(f)) o.push(m[0]);
    else if (m = /^\x25{2}/.exec(f)) o.push('%');
    else if (m = /^\x25(?:(\d+)\$)?(\+)?(0|'[^$])?(-)?(\d+)?(?:\.(\d+))?([b-fosuxX])/.exec(f)) {
      if (((a = arguments[m[1] || i++]) == null) || (a == undefined)) throw("Too few arguments.");
      if (/[^s]/.test(m[7]) && (typeof(a) != 'number'))
        throw("Expecting number but found " + typeof(a));
      switch (m[7]) {
        case 'b': a = a.toString(2); break;
        case 'c': a = String.fromCharCode(a); break;
        case 'd': a = parseInt(a); break;
        case 'e': a = m[6] ? a.toExponential(m[6]) : a.toExponential(); break;
        case 'f': a = m[6] ? parseFloat(a).toFixed(m[6]) : parseFloat(a); break;
        case 'o': a = a.toString(8); break;
        case 's': a = ((a = String(a)) && m[6] ? a.substring(0, m[6]) : a); break;
        case 'u': a = Math.abs(a); break;
        case 'x': a = a.toString(16); break;
        case 'X': a = a.toString(16).toUpperCase(); break;
      }
      a = (/[def]/.test(m[7]) && m[2] && a > 0 ? '+' + a : a);
      c = m[3] ? m[3] == '0' ? '0' : m[3].charAt(1) : ' ';
      x = m[5] - String(a).length;
      p = m[5] ? str_repeat(c, x) : '';
      o.push(m[4] ? a + p : p + a);
    }
    else throw ("Huh ?!");
    f = f.substring(m[0].length);
  }
  return o.join('');
}