

from stat import S_IFDIR, S_IFREG
from pysinter import FUSEError, ROOT_INODE, MAX32, pad64, to32, to64, ENCODING, BYTEORDER

def mk_dirent(inode, name, filetype, cookie):
    '''
    The cookie may be included in another READDIR request indicate the offset.
    Having at least one byte of padding ensures that the name will be 
    null-terminated.
    '''
    if isinstance(name, str):
        name = name.encode(ENCODING)
    namelen = len(name)
    padlen = namelen % 8
    if not padlen:
        padlen = 8
    return b''.join([
        to64(inode)
        , to64(cookie)
        , to32(namelen)
        , to32(filetype >> 12)
        , name
        , bytes(padlen)
        ])

