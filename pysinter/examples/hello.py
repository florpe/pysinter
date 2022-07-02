
from errno import ENOSYS, ENOENT, EACCES, ENOTSUP
from os import getuid, getgid
from stat import S_IFDIR, S_IFREG

from pysinter import FUSEError, ROOT_INODE, MAX32, pad64, to32, to64
from pysinter.dynamic import Operations, dyn_nop, dyn_nosend

FILE_HELLO = b'hello'
MSG_HELLO = b'hello, world'
DIRENT_HELLO = b''.join([
    to64(ROOT_INODE + 1)
    , to64(32)
    , to32(len(FILE_HELLO) + 1)
    , to32(S_IFREG >> 12)
    , pad64(FILE_HELLO)
    ])

ATTRS_HELLO = {
    'ino': 0
    , 'size': len(MSG_HELLO)
    , 'mode': S_IFREG | 0o644
    , 'uid': getuid()
    , 'gid': getgid()
    , 'blksize': 512
    , 'blocks': 1
    , 'nlink': 1
    }
ATTRS_ROOT = {
    'ino': 0
    , 'size': 0
    , 'mode': S_IFDIR | 0o755
    , 'uid': getuid()
    , 'gid': getgid()
    , 'blksize': 512
    , 'nlink': 1
    }

async def hello_fakeinit(header, parsed):
    '''
    An init handler that just assumes a version.
    '''
    print('Faking init!')
    return 0, {
        'major': 7
        , 'minor': 31
        , 'maxReadAhead': MAX32
        , 'flags': 0
        , 'maxBackground': 4
        , 'congestionThreshold': 4
        , 'maxWrite': 1024
        , 'timeGran': 0
        , 'maxPages': 16
        }

async def hello_getattr(header, parsed):
    '''
    Fixed getattr handler.
    '''
    node = header.nodeid
    if node == ROOT_INODE:
        return 0, ATTRS_ROOT
    return 0, ATTRS_HELLO

async def hello_lookup(header, parsed):
    '''
    Lookup handler that checks for the FILE_HELLO filename.
    '''
    if header.nodeid != ROOT_INODE:
        raise FUSEError(ENOENT)
    if parsed['name'] != FILE_HELLO:
        print('Bad filename', parsed['name'])
        raise FUSEError(ENOENT)
    return 0, {
        ** ATTRS_HELLO
        , 'nodeId': ROOT_INODE + 1
        }

async def hello_opendir(header, parsed):
    '''
    Opendir handler.
    '''
    if header.nodeid != ROOT_INODE:
        raise FUSEError(ENOENT)
    return 0, {'fh': ROOT_INODE}

async def hello_readdir(header, parsed):
    '''
    Readdir handler that employs the fixed DIRENT_HELLO directory entry.
    '''
    if header.nodeid != ROOT_INODE:
        raise FUSEError(ENOENT)
    if parsed['offset'] == 0:
        return 0, {'data': DIRENT_HELLO}
    return 0, {'data': b''}

async def hello_read(header, parsed):
    return 0, {'data': MSG_HELLO}

FS_HELLO = {
    'FUSE_INIT': hello_fakeinit
    , 'FUSE_GETATTR' : hello_getattr
    , 'FUSE_LOOKUP' : hello_lookup
    , 'FUSE_OPENDIR' : hello_opendir
    , 'FUSE_READDIR': hello_readdir
    , 'FUSE_RELEASEDIR': dyn_nop
    , 'FUSE_FORGET': dyn_nosend
    , 'FUSE_GETXATTR': dyn_nop
    , 'FUSE_LISTXATTR': dyn_nop
    , 'FUSE_OPEN': dyn_nop
    , 'FUSE_RELEASE': dyn_nop
    , 'FUSE_FLUSH': dyn_nop
    , 'FUSE_READ': hello_read
    }



