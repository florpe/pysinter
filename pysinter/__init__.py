
from collections import namedtuple
from os import environ, read, readv, writev, close
from resource import getpagesize

from janus import Queue

__version__ = '0.1.0'


# Constants for FUSE interaction
ENCODING = 'utf-8'
BYTEORDER = 'little'
MINIMUM_BUFFER_SIZE = 8192

HEADER_SIZE_RECV = 40
HEADER_SIZE_SEND = 16
HEADER_SIZE_WRITE = 40

ROOT_INODE = 1

# Convenience constants
MAX16 = 0xffff
MAX32 = 0xffffffff
MAX64 = 0xffffffffffffffff


# Convenience functions for changing representation
frombytes = lambda x: int.from_bytes(x, BYTEORDER)
to16 = lambda x: int.to_bytes(x, 2, BYTEORDER)
to32 = lambda x: int.to_bytes(x, 4, BYTEORDER)
to64 = lambda x: int.to_bytes(x, 8, BYTEORDER)

def pad64(inpt):
    residue = len(inpt) % 64
    if not residue:
        return inpt
    return inpt + bytes(64 - residue)

Header = namedtuple('Header', ('opcode', 'unique', 'nodeid', 'uid', 'gid', 'pid'))

class FUSEError(Exception):
    def __init__(self, errno, *args):
        self.errno = errno
        self.msg = None if not args else args[0]
        self.params = tuple(args[1:])
        return None

def parse_header_req(buffer):
    return Header(
        frombytes(buffer[4:8])
        , bytes(buffer[8:16])
        , frombytes(buffer[16:24])
        , frombytes(buffer[24:28])
        , frombytes(buffer[28:32])
        , frombytes(buffer[32:36])
#        , frombytes(buffer[36:40]) # Padding
        )

class Sinter():
    '''
    A class to expose a FUSE-mounted file descritor as a pair of async-capable
    RX and TX queues.
    '''
    def __init__(self, fd=None, bufsize=MINIMUM_BUFFER_SIZE):
        '''
        Initialize buffers and queues. If fd is a string, extract the FUSE
        descriptor from an environment variable.
        '''
        if bufsize < MINIMUM_BUFFER_SIZE:
            raise ValueError(
                f"Buffer size must be at least {MINIMUM_BUFFER_SIZE}"
                )
        if fd is None:
            raise ValueError("File descriptor for FUSE device is missing.")
        if isinstance(fd, int):
            self._fd = fd
        elif isinstance(fd, str):
            self._fd = int(environ[fd])
        else:
            raise ValueError("Could not interpret value for FUSE device.")
        self._recvbuf = bytearray(bufsize)
        self._sendbuf = bytearray(HEADER_SIZE_SEND)
        self._tx = Queue()
        self.tx_sync = self._tx.sync_q
        self.tx_async = self._tx.async_q
        self._rx = Queue()
        self.rx_sync = self._rx.sync_q
        self.rx_async = self._rx.async_q

        self.receiving = True #Is this the right way to stop the operation?
        self.sending = True #Is this the right way to stop the operation?

        self._major = None #TODO: Remove
        self._minor = None #TODO: Remove
        return None
    def negotiate(self, major, minor, flags=0, max_readahead=MAX32, max_background=MAX16):
        '''
        Legacy - should not be here.
        '''
        raise NotImplementedError
        header, initdata, body = self._recv() #Outdated, should do the parsing itself
        assert header.opcode == FUSE_INIT
        if major < initdata.major:
            resbody = to32(major)
            self._send(header, 0, resbody)
            header, initdata, body = self._recv()
            assert header.opcode == FUSE_INIT
            assert major == initdata.major #Is this the right thing to do?
        elif initdata.major < major:
            major = initdata.major
            minor = initdata.minor #Is this the right thing to do?
        else:
            pass
        agreed_minor = min(minor, initdata.minor)
        flagbytes = to64(flags)
        max_write = len(self._recvbuf) - HEADER_SIZE_RECV - HEADER_SIZE_WRITE
        assert max_write > 0
        max_pages = (max_write - 1) // (getpagesize() + 1)
        resbody = b''.join([
            to32(major)
            , to32(minor)
            , to32(max_readahead)
            , flagbytes[:4]
            , to16(max_background)
            , to16((max_background * 3) // 4) # Hardcoded congestion threshold
            , to32(max_write)
            , to32(1) # time_gran
            , to16(max_pages) # max_pages
            , to16(0) # map_alignment?
            , flagbytes[4:8] # flags2
            , 7*to32(0) # Padding
            ])
        self._send(header, 0, resbody)
        return major, agreed_minor
    def _recv(self):
        '''
        Read from fd and queue synchronously.
        '''
        buffer = self._recvbuf
        numread = readv(self._fd, (buffer,))
        if numread < HEADER_SIZE_RECV:
            raise RuntimeError(f"Read only {numread} bytes from FUSE fd")
        total = frombytes(buffer[:4])
        header = parse_header_req(buffer)
        head = bytes(buffer[HEADER_SIZE_RECV:numread])

        remainder = total - numread
        if remainder <= 0:
            return header, head
        if remainder < MINIMUM_BUFFER_SIZE:
            backupnum = readv(self._fd, (buffer,))
            if backupnum != remainder:
                raise RuntimeError(
                    f"Read {backupnum} bytes from FUSE fd, expected {remainder}"
                )
            return header, head + bytes(buffer[:remainder])
        return header, head + read(self._fd, remainder)
    def _send(self, header, errno, msg):
        '''
        Read from queue and write to fd synchronously.
        '''
        if msg is None:
            return True
        total = len(msg) + HEADER_SIZE_SEND
        sendbuf = self._sendbuf
        sendbuf[:4] = to32(total)
        sendbuf[4:8] = to32(errno)
        sendbuf[8:16] = header.unique
        if msg:
            writebuffers = (sendbuf, msg)
        else:
            writebuffers = (sendbuf,)
        print(f'@@@ {total=} {writebuffers=}')
        numsent = writev(self._fd, writebuffers)
        return (numsent == total)
    def recv_loop(self):
        '''
        Run self._recv() in a loop.
        '''
        while self.receiving:
            msg = self._recv()
            self.rx_sync.put(msg)
        return None
    def send_loop(self):
        '''
        Run self._send(...) in a loop.
        '''
        while self.sending:
            header, errno, msg = self.tx_sync.get()
            self._send(header, errno, msg)
        return None
