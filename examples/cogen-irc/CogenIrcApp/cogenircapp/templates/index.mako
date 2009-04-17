<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
    <meta http-equiv="content-type" content="text/html; charset=utf-8">
    <title></title>

<style type="text/css">
body {
	margin:0;
	padding:0;
    text-align:center;
}
#connect {
    margin: 0 auto;
}
#connect label{
    display: block;
}
#connect span {
    text-align:left;
    width: 5em;
    display: inline-block;
}
#connect label {
    display: block;
}
.error-message {
    color: red;
    font-weight: bold;
    display:inline !important;
}
</style>

<link rel="stylesheet" type="text/css" href="yui/build/fonts/fonts-min.css" />
</head>

<body class=" yui-skin-sam">

<center><h1>comet irc client powered by <a href="http://code.google.com/p/cogen/">cogen</a></h1></center>

<div id="connect">
<form method="POST" id="connect_form">
<label><span>Server: </span><input name="server" value="irc.freenode.net"/></label><form:error name="server">
<label><span>Channel: </span><input name="channel" value="#cogen"/></label><form:error name="channel">
<label><span>Nick: </span><input name="nickname" value="Guest"/></label><form:error name="nickname">
<br/>
<input type="submit" value="Connect"/>
</form>
</div>

</body>
</html>