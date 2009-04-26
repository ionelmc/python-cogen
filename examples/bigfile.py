import os
val = os.urandom(1024*1024)
f = file('BIGFILE', 'wb')
for i in xrange(100):
    f.write(val)
