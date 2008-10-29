from ctypes import WINFUNCTYPE
from ctypes import windll, pythonapi, cast, WinError
from ctypes import c_int, c_uint, c_long, c_ulong, c_void_p, byref, c_char_p 
from ctypes import c_ushort, c_ubyte, c_char, WINFUNCTYPE, c_short, c_ubyte
from ctypes import Structure, Union, py_object, POINTER, pointer, sizeof
from ctypes.wintypes import HANDLE, ULONG, DWORD, BOOL, LPCSTR, LPCWSTR, WinError
import os

NULL = c_ulong()

IOC_WS2 = 0x08000000
IOC_OUT = 0x40000000
IOC_IN = 0x80000000
IOC_INOUT = IOC_IN | IOC_OUT
SIO_GET_EXTENSION_FUNCTION_POINTER =  IOC_INOUT | IOC_WS2 | 6
SOL_SOCKET = 0xffff
SO_PROTOCOL_INFOA = 0x2004
SO_PROTOCOL_INFOW = 0x2005

SOCKET = SIZE_T = c_uint

class _US(Structure):
    _fields_ = [
        ("Offset",          DWORD),
        ("OffsetHigh",      DWORD),
    ]

class _U(Union):
    _fields_ = [
        ("s",               _US),
        ("Pointer",         c_void_p),
    ]

    _anonymous_ = ("s",)

class OVERLAPPED(Structure):
    _fields_ = [
        ("Internal",        POINTER(ULONG)),
        ("InternalHigh",    POINTER(ULONG)),

        ("u",               _U),

        ("hEvent",          HANDLE),

        # Custom fields.
        ("channel",         py_object),
    ]

    _anonymous_ = ("u",)
    
class WSABUF(Structure):
    _fields_ = [
        ('len', c_ulong),
        ('buf', c_char_p)
    ]

class GUID(Structure):
    _fields_ = [
        ('Data1', c_ulong),
        ('Data2', c_ushort),
        ('Data3', c_ushort),
        ('Data4', c_ubyte * 8)
    ]

    def __init__(self, l, w1, w2, b1, b2, b3, b4, b5, b6, b7, b8):
        self.Data1 = l
        self.Data2 = w1
        self.Data3 = w2
        self.Data4[:] = (b1, b2, b3, b4, b5, b6, b7, b8)

WSAID_CONNECTEX = GUID(0x25a207b9,0xddf3,0x4660,0x8e,0xe9,0x76,0xe5,0x8c,0x74,0x06,0x3e)
WSAID_ACCEPTEX = GUID(0xb5367df1,0xcbac,0x11cf,0x95,0xca,0x00,0x80,0x5f,0x48,0xa1,0x92)

MAX_PROTOCOL_CHAIN = 7
WSAPROTOCOL_LEN = 255
class WSAPROTOCOLCHAIN(Structure):
    _fields_ = [
        ('ChainLen', c_int),
        ('ChainEntries', DWORD * MAX_PROTOCOL_CHAIN)
    ]

class WSAPROTOCOL_INFO(Structure):
    _fields_ = [
        ('dwServiceFlags1', DWORD),
        ('dwServiceFlags2', DWORD),
        ('dwServiceFlags3', DWORD),
        ('dwServiceFlags4', DWORD),
        ('dwProviderFlags', DWORD),
        ('ProviderId', GUID),
        ('dwCatalogEntryId', DWORD),
        ('ProtocolChain', WSAPROTOCOLCHAIN),
        ('iVersion', c_int),
        ('iAddressFamily', c_int),
        ('iMaxSockAddr', c_int),
        ('iMinSockAddr', c_int),
        ('iSocketType', c_int),
        ('iProtocol', c_int),
        ('iProtocolMaxOffset', c_int),
        ('iNetworkByteOrder', c_int),
        ('iSecurityScheme', c_int),
        ('dwMessageSize', DWORD),
        ('dwProviderReserved', DWORD),
        ('szProtocol', c_char * (WSAPROTOCOL_LEN+1)),
    ]
 
class sockaddr(Structure):
    _fields_ = [
        ('sa_family', c_ushort),
        ('sa_data', c_char * 14)
    ]
    
    
class in_addr(Structure):
    _fields_ = [
        ('s_b1', c_ubyte),
        ('s_b2', c_ubyte),
        ('s_b3', c_ubyte),
        ('s_b4', c_ubyte)
    ]

class sockaddr_in(Structure):
    _fields_ = [
        ('sin_family', c_ushort),
        ('sin_port', c_ushort),
        ('sin_addr', in_addr),
        ('sin_zero', c_char * 8)
    ]
    
class addrinfo(Structure):
    pass
    
addrinfo._fields_ = [
    ('ai_flags', c_int),
    ('ai_family', c_int),
    ('ai_socktype', c_int),
    ('ai_protocol', c_int),
    ('ai_addrlen', c_uint),
    ('ai_canonname', c_char_p),
    ('ai_addr', POINTER(sockaddr)),
    ('ai_next', POINTER(addrinfo))
]

def _error_check(result, func, args):
    if result:
        raise WinError()
    return result

def _bool_error_check(result, func, args):
    if not result:
        raise WinError()
    return result
    
CreateIoCompletionPort = windll.kernel32.CreateIoCompletionPort
CreateIoCompletionPort.argtypes = (HANDLE, HANDLE, POINTER(c_ulong), DWORD)
CreateIoCompletionPort.restype = HANDLE

GetQueuedCompletionStatus = windll.kernel32.GetQueuedCompletionStatus
GetQueuedCompletionStatus.argtypes = (HANDLE, POINTER(DWORD), POINTER(c_ulong), POINTER(POINTER(OVERLAPPED)), DWORD)
GetQueuedCompletionStatus.restype = BOOL

getaddrinfo = windll.ws2_32.getaddrinfo
# const char *nodename, const char *servname, const struct addrinfo *hints, struct addrinfo **res
getaddrinfo.argtypes = (c_char_p, c_char_p, POINTER(addrinfo), POINTER(POINTER(addrinfo)))
getaddrinfo.restype = c_int
getaddrinfo.errcheck = _error_check

getsockopt = windll.ws2_32.getsockopt
# SOCKET s, int level, int optname, char *optval, int *optlen
getsockopt.argtypes = (SOCKET, c_int, c_int, c_char_p, POINTER(c_int))
getsockopt.restype = c_int
getsockopt.errcheck = _error_check

WSARecv = windll.ws2_32.WSARecv
# SOCKET s, LPWSABUF lpBuffers, DWORD dwBufferCount, LPDWORD lpNumberOfBytesRecvd, LPDWORD lpFlags, LPWSAOVERLAPPED lpOverlapped, LPWSAOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine
WSARecv.argtypes = (SOCKET, POINTER(WSABUF), DWORD, POINTER(DWORD), POINTER(DWORD), POINTER(OVERLAPPED), c_void_p)
WSARecv.restype = c_int

WSASend = windll.ws2_32.WSASend
# SOCKET s, LPWSABUF lpBuffers, DWORD dwBufferCount, LPDWORD lpNumberOfBytesSent, DWORD dwFlags, LPWSAOVERLAPPED lpOverlapped, LPWSAOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine
WSASend.argtypes = (SOCKET, POINTER(WSABUF), DWORD, POINTER(DWORD), DWORD, POINTER(OVERLAPPED), c_void_p)
WSASend.restype = c_int


AcceptEx = windll.Mswsock.AcceptEx
# SOCKET sListenSocket, SOCKET sAcceptSocket, PVOID lpOutputBuffer, DWORD dwReceiveDataLength, DWORD dwLocalAddressLength, DWORD dwRemoteAddressLength, LPDWORD lpdwBytesReceived, LPOVERLAPPED lpOverlapped
AcceptEx.argtypes = (SOCKET, SOCKET, c_void_p, DWORD, DWORD, DWORD, POINTER(DWORD), POINTER(OVERLAPPED))
AcceptEx.restype = BOOL
AcceptEx.errcheck = _bool_error_check

# SOCKET s, DWORD dwIoControlCode, LPVOID lpvInBuffer, DWORD cbInBuffer, LPVOID lpvOutBuffer, DWORD cbOutBuffer, LPDWORD lpcbBytesReturned, LPWSAOVERLAPPED lpOverlapped, LPWSAOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine
WSAIoctl = windll.ws2_32.WSAIoctl
WSAIoctl.argtypes = (SOCKET, DWORD, c_void_p, DWORD, c_void_p, DWORD, POINTER(DWORD), POINTER(OVERLAPPED), c_void_p)
WSAIoctl.restype = c_int
WSAIoctl.errcheck = _error_check

# SOCKET s, const struct sockaddr *name, int namelen, PVOID lpSendBuffer,
ConnectExType = WINFUNCTYPE(BOOL, c_int, POINTER(sockaddr), c_int, c_void_p, DWORD, POINTER(DWORD), POINTER(OVERLAPPED))

def _GetConnectExPtr(given_socket=None):
    from socket import socket
    bogus_sock = given_socket or socket()
    bogus_bytes = DWORD()
    ConnectEx = ConnectExType(0)
    ret = WSAIoctl(
        bogus_sock.fileno(), SIO_GET_EXTENSION_FUNCTION_POINTER, byref(WSAID_CONNECTEX), sizeof(WSAID_CONNECTEX),
        byref(ConnectEx), sizeof(ConnectEx), byref(bogus_bytes), None, None
    )
    return ConnectEx

ConnectEx = _GetConnectExPtr()
#~ ConnectEx.errcheck = _bool_error_check

CloseHandle = windll.kernel32.CloseHandle
CloseHandle.argtypes = (HANDLE,)
CloseHandle.restype = BOOL

# Python API

pythonapi.PyBuffer_New.argtypes = (c_ulong,)
pythonapi.PyBuffer_New.restype = py_object

pythonapi.PyErr_SetFromErrno.argtypes = (py_object,)
pythonapi.PyErr_SetFromErrno.restype = py_object

# ----------------------------------------------------------------------------

if __name__ == "__main__":
    import socket
    s = socket.socket()
    prot_info = WSAPROTOCOL_INFO()
    prot_info_len = c_int(sizeof(prot_info))
    getsockopt(s.fileno(), SOL_SOCKET, SO_PROTOCOL_INFOA, cast(byref(prot_info), c_char_p), byref(prot_info_len))
    
    hints = addrinfo()
    hints.ai_family = prot_info.iAddressFamily;
    hints.ai_socktype = prot_info.iSocketType;
    hints.ai_protocol = prot_info.iProtocol;
    
    result = POINTER(addrinfo)()
    
    getaddrinfo("localhost", "5523", byref(hints), byref(result));
    
    print result.contents.ai_family
    print result.contents.ai_flags
    print result.contents.ai_family
    print result.contents.ai_socktype
    print result.contents.ai_protocol
    print result.contents.ai_addrlen
    print result.contents.ai_canonname
    print result.contents.ai_addr
    print '>', bool(result.contents.ai_next)
    
    print result.contents.ai_addr.contents
    print sizeof(sockaddr), sizeof(sockaddr_in)
    addr = cast(result.contents.ai_addr, POINTER(sockaddr_in)).contents
    print '>', addr.sin_port
    print socket.htons(addr.sin_port)
    
    print addr.sin_addr.s_b1
    print addr.sin_addr.s_b2
    print addr.sin_addr.s_b3
    print addr.sin_addr.s_b4
                      
    olap = OVERLAPPED()
    sent = POINTER(c_ulong)(c_ulong())
    print ConnectEx
    print dir(ConnectEx)
    s.bind(('0.0.0.0', 0))
    print ConnectEx(s.fileno(), result.contents.ai_addr, result.contents.ai_addrlen, None, 0, sent, olap) 

    import time
    time.sleep(10)