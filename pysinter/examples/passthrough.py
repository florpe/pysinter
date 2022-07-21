
from errno import ENOENT
from hashlib import blake2b
from os import open as osopen, close as osclose, stat, scandir, fsencode, pread
from os.path import join as pjoin
from stat import S_IFDIR, S_IFREG

from ctypes import CDLL
from ctypes.util import find_library

from pysinter import FUSEError, ROOT_INODE, BYTEORDER, MAX32, pad64, to32, to64
from pysinter.helper import fuse_negotiate, mk_dyn_negotiate

'''
Work in progress - this passthrough FUSE client should become sufficiently
featureful to meaningfully test dynamically loaded documentation.
'''

LIBC = CDLL(find_library('c'))

def stat_to_attr(data, ino=0):
    return {
        'ino': ino
        , 'size': data.st_size
        , 'timeandmode': {
            'mode': data.st_mode
            , 'atime': int(data.st_atime)
            , 'mtime': int(data.st_mtime)
            , 'ctime': int(data.st_ctime)
            , 'atimensec': data.st_atime_ns % 1000000000
            , 'mtimensec': data.st_mtime_ns % 1000000000
            , 'ctimensec': data.st_ctime_ns % 1000000000
            }
        , 'uid': data.st_uid
        , 'gid': data.st_gid
        , 'blksize': data.st_blksize
        , 'nlink': data.st_nlink
        }

class Passthrough():
    def __init__(self, root, major=7, minor=31, flags=0):
        if isinstance(root, str):
            root = root.encode('utf-8')
        rootdata = stat(root)
        self._root_ino = rootdata.st_ino
        #Inode is taken from underlying filesystem
        #TODO: Make sure that ROOT_INODE is not accidentally reused
        self._ino_to_path = {self._root_ino: root}
        self._major = major
        self._minor = minor
        self._flags = flags
        return None
    def _path(self, ino, name=None):
        return self._ino_to_path.setdefault(ino, name)
    async def getattr(self, header, parsed):
        node = header.nodeid
        if node == ROOT_INODE:
            node = self._root_ino
        data = stat(self._path(node))
        return 0, {'attr': stat_to_attr(data)}
    async def lookup(self, header, parsed):
        node = header.nodeid
        if node == ROOT_INODE:
            node = self._root_ino
        name = parsed['name']
        fullname = pjoin(self._path(node), name)
        try:
            data = stat(fullname, follow_symlinks=False)
        except FileNotFoundError as e:
            raise FUSEError(ENOENT) from e
        ino = data.st_ino
        if ino == ROOT_INODE:
            raise NotImplementedError(
                'Cannot cope with inode same as ROOT_INODE yet'
                , fullname
                )
        self._path(ino, name=fullname)
        attr = stat_to_attr(data, ino=ino)
        res = {'entry': {
            'attr': attr
            , 'nodeId': ino
            }}
        return 0, res
    async def opendir(self, header, parsed):
        node = header.nodeid
        if node == ROOT_INODE:
            node = self._root_ino
        return 0, {
            'fh': osopen(self._path(node), parsed['flags'])
            }
    async def releasedir(self, header, parsed):
        osclose(parsed['fh'])
        return 0, {}
    async def readdir(self, header, parsed):
        node = header.nodeid
        if node == ROOT_INODE:
            node = self._root_ino
        dirname = self._path(node)
        cookie = parsed['cookie'].to_bytes(8, BYTEORDER)
        entries = []
        entries_raw = list(sorted(
            (dirent_cookie, dirent, dirent.stat(follow_symlinks=False))
            for dirent_cookie, dirent in (
                (blake2b(dirent.name, digest_size=8).digest(), dirent)
                for dirent in scandir(path=dirname)
                )
            if cookie < dirent_cookie #Assume we won't accidentally find the preimage of 0
            ))
        for dirent_cookie, dirent, dirent_stat in entries_raw:
            dirent_ino = dirent_stat.st_ino
            dirent_name = dirent.name
            fullname = pjoin(dirname, dirent_name)
            self._path(dirent_ino, name=fullname)
            entries.append({
                'ino': dirent_ino
                , 'cookie': dirent_cookie
                , 'namelen': len(dirent_name)
                , 'type': dirent_stat.st_mode
                , 'name': dirent_name
                })
        return 0, {'data': entries}
    async def open(self, header, parsed):
        #TODO: openFlags
        node = header.nodeid
        if node == ROOT_INODE:
            node = self._root_ino
        return 0, {
            'fh': osopen(self._path(node), parsed['flags'])
            }
    async def read(self, header, parsed):
        #TODO: Flags
        #TODO: Locks
        return 0, {
            'data': pread(parsed['fh'], parsed['size'], parsed['offset'])
            }
    async def release(self, header, parsed):
        #TODO: Flags
        #TODO: Locks
        osclose(parsed['fh'])
        return 0, {}
    def make(self):
        return {
        'FUSE_INIT': mk_dyn_negotiate(major=self._major, minor=self._minor, flags=self._flags)
        , 'FUSE_GETATTR' : self.getattr
        , 'FUSE_OPENDIR': self.opendir
        , 'FUSE_RELEASEDIR': self.releasedir
        , 'FUSE_READDIR': self.readdir
        , 'FUSE_LOOKUP': self.lookup
        , 'FUSE_OPEN': self.open
        , 'FUSE_READ': self.read
        , 'FUSE_RELEASE': self.release
    }
            
