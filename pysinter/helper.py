

from stat import S_IFDIR, S_IFREG
from pysinter import FUSEError, ROOT_INODE, MAX32, pad64, to32, to64, ENCODING, BYTEORDER

DEFAULT_NEGOTIATE_OPTIONS = {
    'maxReadAhead': MAX32,
    'maxBackground': 4,
    'congestionThreshold': 4,
    'maxWrite': 4096,
    'timeGran': 0,
    'maxPages': 16
    }

def fuse_negotiate(inpt, major=7, minor=31, flags=0, options=None):
    if options is None:
        opts = dict(DEFAULT_NEGOTIATE_OPTIONS)
    else:
        opts = dict(options)
        for k, v in DEFAULT_NEGOTIATE_OPTIONS.items():
            opts.setdefault(k, v)
    opts['major'] = major
    opts['minor'] = minor
    opts['flags'] = inpt.get('flags', 0) & flags
    return opts

def mk_dyn_negotiate(major=7, minor=31, flags=0, options=None):
    async def dyn_negotiate(_, inpt):
        return 0, fuse_negotiate(
            inpt
            , major=7
            , minor=31
            , flags=0
            , options=None
            )
    return dyn_negotiate

