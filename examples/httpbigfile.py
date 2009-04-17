import os
#~ val = os.urandom(1024)#*1024)

f = file('BIGFILE', 'wb')
f.write("POST / HTTP/1.1\r\n")
f.write("Host: localhost\r\n")
f.write("Connection: close\r\n")
f.write("Transfer-Encoding: chunked\r\n")
#~ f.write("Content-Length: 104857600\r\n")

f.write("\r\n")
#~ f.write("\r\n")

for i in xrange(100):
    val = chr(i+35)*1024*1024

    f.write(hex(len(val))[2:]+"\r\n")
    f.write(val)
    f.write("\r\n")
#~ f.write("\r\n")
f.write("0\r\n\r\n")
