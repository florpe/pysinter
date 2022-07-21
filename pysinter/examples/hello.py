from errno import ENOENT
from json import dumps
from os import getuid, getgid
from stat import S_IFDIR, S_IFREG

from pysinter import FUSEError, ROOT_INODE, MAX32, pad64, to32, to64
from pysinter.dynamic import Operations, dyn_nop, dyn_nosend
from pysinter.helper import fuse_negotiate, mk_dyn_negotiate

FILE_HELLO = b'hello'
INODE_HELLO = ROOT_INODE + 1
MSG_HELLO = b'Hello, world!'

FILE_HELLO2 = b'hello2'
INODE_HELLO2 = ROOT_INODE + 2
MSG_HELLO2 = b'Once again - hello, world!'

ATTRS_HELLO = {
    "attr": {
        'ino': 0
        , 'size': len(MSG_HELLO)
        , 'timeandmode': {
            'mode': S_IFREG | 0o644
            , 'uid': getuid()
            , 'gid': getgid()
            }
        , 'blksize': 512
        , 'blocks': 1
        , 'nlink': 1
        }
    }
ATTRS_HELLO2 = {
    "attr": {
        'ino': 0
        , 'size': len(MSG_HELLO2)
        , 'timeandmode': {
            'mode': S_IFREG | 0o644
            , 'uid': getuid()
            , 'gid': getgid()
            }
        , 'blksize': 512
        , 'blocks': 1
        , 'nlink': 1
        }
    }
ATTRS_ROOT = {
    "attr": {
        'ino': 0
        , 'size': 0
        , 'timeandmode': {
            'mode': S_IFDIR | 0o755
            , 'uid': getuid()
            , 'gid': getgid()
            }
        , 'blksize': 512
        , 'nlink': 1
        }
    }

async def hello_getattr(header, parsed):
    '''
    Fixed getattr handler.
    '''
    node = header.nodeid
    if node == ROOT_INODE:
        return 0, ATTRS_ROOT
    if node == INODE_HELLO:
        return 0, ATTRS_HELLO
    if node == INODE_HELLO2:
        return 0, ATTRS_HELLO2
    raise FUSEError(ENOENT)

async def hello_lookup(header, parsed):
    '''
    Lookup handler that checks for the FILE_HELLO filename.
    '''
    if header.nodeid != ROOT_INODE:
        raise FUSEError(ENOENT)
    if parsed['name'] == FILE_HELLO:
        return 0, {'entry': {
            ** ATTRS_HELLO
            , 'nodeId': INODE_HELLO
            }}
    if parsed['name'] == FILE_HELLO2:
        return 0, {'entry': {
            ** ATTRS_HELLO
            , 'nodeId': INODE_HELLO2
            }}
    print('Bad filename', parsed['name'], parsed)
    raise FUSEError(ENOENT)

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
    print('Readdir', parsed)
    cookie = parsed['cookie']
    print('Readdir cookie', cookie)
    if cookie == 0:
#        residue = (len(FILE_HELLO) + 1) % 8
#        padding = bytes(8 - residue) if residue else b''
        return 0, {"data": [
            {
                "ino": INODE_HELLO
                , "cookie": 1
                , "namelen": len(FILE_HELLO)
                , "type": (S_IFREG >> 12)
                , "name": FILE_HELLO
#                , "padding": padding
                }
            , {
                "ino": INODE_HELLO2
                , "cookie": 2
                , "namelen": len(FILE_HELLO2)
                , "type": (S_IFREG >> 12)
                , "name": FILE_HELLO2
#                , "padding": padding
                }
            ]}
    if cookie == 1:
        return {"data": [{
            "ino": INODE_HELLO2
            , "cookie": 2
            , "namelen": len(FILE_HELLO2)
            , "type": (S_IFREG >> 12)
            , "name": FILE_HELLO2
            }]}
    print('Readdir fell through', parsed)
    return 0, b''


async def hello_read(header, parsed):
    if header.nodeid == INODE_HELLO:
        return 0, {'data': MSG_HELLO}
    if header.nodeid == INODE_HELLO2:
        return 0, {'data': MSG_HELLO2}
    raise FUSEError(ENOENT)

#TODO: Can we cut some of these NOPs? They should be from before the fixing of the error codes
FS_HELLO = {
    'FUSE_INIT': mk_dyn_negotiate(major=7, minor=31)
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



