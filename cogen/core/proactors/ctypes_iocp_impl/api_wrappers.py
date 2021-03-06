from ctypes import WINFUNCTYPE, GetLastError, \
            windll, pythonapi, cast, WinError, create_string_buffer, \
            c_ushort, c_ubyte, c_char, WINFUNCTYPE, c_short, c_ubyte, \
            c_int, c_uint, c_long, c_ulong, c_void_p, byref, c_char_p, \
            Structure, Union, py_object, POINTER, pointer, sizeof, string_at

from ctypes.wintypes import HANDLE, ULONG, DWORD, BOOL, LPCSTR, LPCWSTR, WinError

from msvcrt import get_osfhandle
from socket import socket as stdsocket
    
from api_consts import *

import os

NULL = c_ulong()
SOCKET = SIZE_T = c_uint

LPDWORD = POINTER(DWORD)
PULONG_PTR = POINTER(c_ulong)

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
        ("object",         py_object),
    ]

    _anonymous_ = ("u",)

LPOVERLAPPED = POINTER(OVERLAPPED)

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
WSAID_TRANSMITFILE = GUID(0xb5367df0,0xcbac,0x11cf,0x95,0xca,0x00,0x80,0x5f,0x48,0xa1,0x92)

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

class TRANSMIT_FILE_BUFFERS(Structure):
    _fields_ = [
        ('Head', c_void_p),
        ('HeadLength', DWORD),
        ('Tail', c_void_p),
        ('TailLength', DWORD)
    ]

class sockaddr(Structure):
    _fields_ = [
        ('sa_family', c_ushort),
        ('sa_data', c_char * 14)
    ]

ACCEPT_BUFF_SZ = 2*sizeof(sockaddr)

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

addrinfo_p = POINTER(addrinfo)

def _error_throw(result, func, args):
    if result:
        raise WinError()
    return result

def _bool_error_throw(result, func, args):
    if not result:
        raise WinError()
    return result

def _error_check(result, func, args):
    if result:
        return GetLastError()
    return result

def _bool_error_check(result, func, args):
    if not result:
        return GetLastError()
    return 0

CreateIoCompletionPort = windll.kernel32.CreateIoCompletionPort
CreateIoCompletionPort.argtypes = (HANDLE, HANDLE, POINTER(c_ulong), DWORD)
CreateIoCompletionPort.restype = HANDLE
CreateIoCompletionPort.errcheck = _bool_error_throw

GetQueuedCompletionStatus = windll.kernel32.GetQueuedCompletionStatus
GetQueuedCompletionStatus.argtypes = (HANDLE, POINTER(DWORD), POINTER(c_ulong), POINTER(POINTER(OVERLAPPED)), DWORD)
GetQueuedCompletionStatus.restype = BOOL
GetQueuedCompletionStatus.errcheck = _bool_error_check

PostQueuedCompletionStatus = windll.kernel32.PostQueuedCompletionStatus
# BOOL = HANDLE CompletionPort, DWORD dwNumberOfBytesTransferred, ULONG_PTR dwCompletionKey, LPOVERLAPPED lpOverlapped
PostQueuedCompletionStatus.argtypes = (HANDLE, DWORD, POINTER(c_long), POINTER(OVERLAPPED))
PostQueuedCompletionStatus.restype = BOOL
PostQueuedCompletionStatus.errcheck = _bool_error_check

CancelIo = windll.kernel32.CancelIo
# BOOL = HANDLE hFile
CancelIo.argtypes = (HANDLE,)
CancelIo.restype = BOOL
CancelIo.errcheck = _bool_error_check

getaddrinfo = windll.ws2_32.getaddrinfo
# int = const char *nodename, const char *servname, const struct addrinfo *hints, struct addrinfo **res
getaddrinfo.argtypes = (c_char_p, c_char_p, POINTER(addrinfo), POINTER(POINTER(addrinfo)))
getaddrinfo.restype = c_int
getaddrinfo.errcheck = _error_throw

getsockopt = windll.ws2_32.getsockopt
# int = SOCKET s, int level, int optname, char *optval, int *optlen
getsockopt.argtypes = (SOCKET, c_int, c_int, c_char_p, POINTER(c_int))
getsockopt.restype = c_int
getsockopt.errcheck = _error_throw

WSARecv = windll.ws2_32.WSARecv
# int = SOCKET s, LPWSABUF lpBuffers, DWORD dwBufferCount, LPDWORD lpNumberOfBytesRecvd, LPDWORD lpFlags, LPWSAOVERLAPPED lpOverlapped, LPWSAOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine
WSARecv.argtypes = (SOCKET, POINTER(WSABUF), DWORD, POINTER(DWORD), POINTER(DWORD), POINTER(OVERLAPPED), c_void_p)
WSARecv.restype = c_int
WSARecv.errcheck = _error_check

WSASend = windll.ws2_32.WSASend
# int = SOCKET s, LPWSABUF lpBuffers, DWORD dwBufferCount, LPDWORD lpNumberOfBytesSent, DWORD dwFlags, LPWSAOVERLAPPED lpOverlapped, LPWSAOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine
WSASend.argtypes = (SOCKET, POINTER(WSABUF), DWORD, POINTER(DWORD), DWORD, POINTER(OVERLAPPED), c_void_p)
WSASend.restype = c_int
WSASend.errcheck = _error_check

AcceptEx = windll.Mswsock.AcceptEx
# BOOL = SOCKET sListenSocket, SOCKET sAcceptSocket, PVOID lpOutputBuffer, DWORD dwReceiveDataLength, DWORD dwLocalAddressLength, DWORD dwRemoteAddressLength, LPDWORD lpdwBytesReceived, LPOVERLAPPED lpOverlapped
AcceptEx.argtypes = (SOCKET, SOCKET, c_void_p, DWORD, DWORD, DWORD, POINTER(DWORD), POINTER(OVERLAPPED))
AcceptEx.restype = BOOL
AcceptEx.errcheck = _bool_error_check

GetAcceptExSockaddrs = windll.Mswsock.GetAcceptExSockaddrs
# void = PVOID lpOutputBuffer, DWORD dwReceiveDataLength, DWORD dwLocalAddressLength, DWORD dwRemoteAddressLength, LPSOCKADDR *LocalSockaddr, LPINT LocalSockaddrLength, LPSOCKADDR *RemoteSockaddr, LPINT RemoteSockaddrLength
GetAcceptExSockaddrs.argtypes = (c_void_p, DWORD, DWORD, DWORD, POINTER(sockaddr), POINTER(c_int), POINTER(sockaddr), POINTER(c_int))
GetAcceptExSockaddrs.restype = None

# int = SOCKET s, DWORD dwIoControlCode, LPVOID lpvInBuffer, DWORD cbInBuffer, LPVOID lpvOutBuffer, DWORD cbOutBuffer, LPDWORD lpcbBytesReturned, LPWSAOVERLAPPED lpOverlapped, LPWSAOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine
WSAIoctl = windll.ws2_32.WSAIoctl
WSAIoctl.argtypes = (SOCKET, DWORD, c_void_p, DWORD, c_void_p, DWORD, POINTER(DWORD), POINTER(OVERLAPPED), c_void_p)
WSAIoctl.restype = c_int
WSAIoctl.errcheck = _error_throw

# BOOL = SOCKET s, const struct sockaddr *name, int namelen, PVOID lpSendBuffer, DWORD dwSendDataLength, LPDWORD lpdwBytesSent, LPOVERLAPPED lpOverlapped
ConnectExType = WINFUNCTYPE(BOOL, c_int, POINTER(sockaddr), c_int, c_void_p, DWORD, POINTER(DWORD), POINTER(OVERLAPPED))

def _GetConnectExPtr(given_socket=None):
    bogus_sock = given_socket or stdsocket()
    bogus_bytes = DWORD()
    ConnectEx = ConnectExType(0)
    ret = WSAIoctl(
        bogus_sock.fileno(), SIO_GET_EXTENSION_FUNCTION_POINTER, byref(WSAID_CONNECTEX), sizeof(WSAID_CONNECTEX),
        byref(ConnectEx), sizeof(ConnectEx), byref(bogus_bytes), None, None
    )
    return ConnectEx

ConnectEx = _GetConnectExPtr()
ConnectEx.errcheck = _bool_error_check

#~ BOOL = SOCKET hSocket, HANDLE hFile, DWORD nNumberOfBytesToWrite, DWORD nNumberOfBytesPerSend, LPOVERLAPPED lpOverlapped,LPTRANSMIT_FILE_BUFFERS lpTransmitBuffers, DWORD dwFlags
TransmitFileType = WINFUNCTYPE(BOOL, SOCKET, HANDLE, DWORD, DWORD, POINTER(OVERLAPPED), POINTER(TRANSMIT_FILE_BUFFERS), DWORD)

def _GetTransmitFilePtr(given_socket=None):
    bogus_sock = given_socket or stdsocket()
    bogus_bytes = DWORD()
    TransmitFile = TransmitFileType(0)
    ret = WSAIoctl(
        bogus_sock.fileno(), SIO_GET_EXTENSION_FUNCTION_POINTER, byref(WSAID_TRANSMITFILE), sizeof(WSAID_TRANSMITFILE),
        byref(TransmitFile), sizeof(TransmitFile), byref(bogus_bytes), None, None
    )
    return TransmitFile

TransmitFile = _GetTransmitFilePtr()
TransmitFile.errcheck = _bool_error_check

CloseHandle = windll.kernel32.CloseHandle
CloseHandle.argtypes = (HANDLE,)
CloseHandle.restype = BOOL

_get_osfhandle = windll.msvcr71._get_osfhandle
_get_osfhandle.argtypes = (c_int,)
_get_osfhandle.restype = c_long

# Python API

pythonapi.PyBuffer_New.argtypes = (c_ulong,)
pythonapi.PyBuffer_New.restype = py_object
AllocateBuffer = pythonapi.PyBuffer_New

pythonapi.PyErr_SetFromErrno.argtypes = (py_object,)
pythonapi.PyErr_SetFromErrno.restype = py_object

