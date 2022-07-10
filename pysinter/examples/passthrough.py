
from ctypes import CDLL
from ctypes.util import find_library

from pysinter import FUSEError, ROOT_INODE, MAX32, pad64, to32, to64
from pysinter.helper import fuse_negotiate

'''
Work in progress - this passthrough FUSE client should become sufficiently
featureful to meaningfully test dynamically loaded documentation.
'''

LIBC = CDLL(find_library('c'))

def mk_passthrough(fd, major=7, minor=31, flags=0):
    FS_PASSTHROUGH = {
        'FUSE_INIT': mk_dyn_negotiate(major=major, minor=minor, flags=flags)
    }

