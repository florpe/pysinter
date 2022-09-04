
from errno import ENOENT
from hashlib import blake2b
from os import open as osopen, chmod, chown, utime, close as osclose, stat, scandir, fsencode, pread, pwrite, remove as osremove
from os.path import join as pjoin
from stat import S_IFDIR, S_IFREG

from ctypes import CDLL
from ctypes.util import find_library

from pysinter import FUSEError, ROOT_INODE, BYTEORDER, ENCODING, MAX32, pad64, to32, to64
from pysinter.helper import fuse_negotiate, mk_dyn_negotiate, dyn_nosend, dyn_nop

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

def mk_entry(attr):
    return {
        'nodeId': attr['ino']
        , 'attr': attr
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
        if name is not None:
            self._ino_to_path[ino] = name
        return self._ino_to_path.get(ino)
    async def getattr(self, header, parsed):
        print('# GETTING ATTRIBUTE')
        node = header.nodeid
        if node == ROOT_INODE:
            node = self._root_ino
        try:
            data = stat(self._path(node))
        except FileNotFoundError as e:
            print(f'# Attribute file not found, {node=} {self._path(node)=}')
            raise FUSEError(ENOENT) from e
        res = {'attr': stat_to_attr(data)}
        print(f'# Attribute {node=}', res)
        return 0, res
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
        res = {'entry': [{
            'attr': attr
            , 'nodeId': ino
            }]}
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
    async def create(self, header, parsed):
        #TODO: Flags
        node = header.nodeid
        if node == ROOT_INODE:
            node = self._root_ino
        dirpath = self._path(node)
        fullpath = pjoin(dirpath, parsed['name'])
        flags = parsed['flags']
        fd = osopen(fullpath, flags, mode=(parsed['mode'] ^ parsed['umask']))
        try:
            statres = stat(fullpath, follow_symlinks=False)
        except FileNotFoundError as e:
            raise FUSEError(ENOENT) from e
        ino = statres.st_ino
        self._path(ino, name=fullpath)
        attr = stat_to_attr(statres, ino=ino)
        return 0, {
            'entry': mk_entry(attr)
            , 'fh': fd
            , 'openFlags': flags
            }
    async def unlink(self, header, parsed):
        node = header.nodeid
        if node == ROOT_INODE:
            node = self._root_ino
        dirpath = self._path(node)
        fullpath = pjoin(dirpath, parsed['name'])
        try:
            osremove(fullpath)
        except FileNotFoundError as e:
            raise FUSEError(ENOENT) from e
        return 0, {}
    async def forget(self, header, parsed):
        node = header.nodeid
        if node == ROOT_INODE:
            node = self._root_ino
        self._ino_to_path.pop(node, None)
        return 0, None
    async def write(self, header, parsed):
        #TODO: Flags
        #TODO: Locks
        data = parsed['data']
        assert len(data) == parsed['size']
        count = pwrite(parsed['fh'], data, parsed['offset'])
        return 0, {'size': count}
    async def setattr(self, header, parsed):
        #TODO: Flags
        #TODO: Locks
        node = header.nodeid
        if node == ROOT_INODE:
            node = self._root_ino
        time_mode = parsed['timeandmode']
        fullpath = self._path(node)
        print('@@@@', fullpath, time_mode)
        chmod(fullpath, time_mode['mode'])
        utime(fullpath, times=(time_mode['atime'], time_mode['mtime']))
        attr = stat_to_attr(stat(fullpath))
        return 0, {'attr': attr}
    def make(self):
        return {
        'FUSE_INIT': mk_dyn_negotiate(major=self._major, minor=self._minor, flags=self._flags)
        , 'FUSE_GETATTR' : self.getattr
        , 'FUSE_OPENDIR': self.opendir
        , 'FUSE_RELEASEDIR': self.releasedir
        , 'FUSE_READDIR': self.readdir
        , 'FUSE_CREATE': self.create
        , 'FUSE_UNLINK': self.unlink
        , 'FUSE_LOOKUP': self.lookup
        , 'FUSE_OPEN': self.open
        , 'FUSE_READ': self.read
        , 'FUSE_RELEASE': self.release
        , 'FUSE_FORGET': dyn_nosend
        , 'FUSE_WRITE': self.write
        , 'FUSE_SETATTR': self.setattr
        , 'FUSE_FLUSH': dyn_nop
    }
            
