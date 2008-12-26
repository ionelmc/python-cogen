Installation
============

Cogen dependencies on bsd/linux are py-sendfile and py-epoll/py-kqueue on 
python <2.6. On windows cogen can optionally use pywin32.
On 2.6 `cogen` can use the builtin select.epoll and select.kqueue.


These docs are intended for the trunk version so you'll need to get that. Some 
socket related api has changed since cogen 0.1.9.

Get the sources::
    
    svn co http://cogen.googlecode.com/svn/trunk/ cogen

Then::

    python setup.py install
    
or::
    
    python setup.py develop

Or even just::
    
    easy_install cogen==dev