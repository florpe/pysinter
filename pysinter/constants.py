
#TODO: Get rid of the flag constants here and extract them from the schema instead.

# Flags for struct fuse_setattr_in - field valid
FATTR_MODE	= (1 << 0)
FATTR_UID	= (1 << 1)
FATTR_GID	= (1 << 2)
FATTR_SIZE	= (1 << 3)
FATTR_ATIME	= (1 << 4)
FATTR_MTIME	= (1 << 5)
FATTR_FH	= (1 << 6)
FATTR_ATIME_NOW	= (1 << 7)
FATTR_MTIME_NOW	= (1 << 8)
FATTR_LOCKOWNER	= (1 << 9)
FATTR_CTIME	= (1 << 10)

# Flags used by OPEN requests
FATTR_MODE	= (1 << 0)
FATTR_UID	= (1 << 1)
FATTR_GID	= (1 << 2)
FATTR_SIZE	= (1 << 3)
FATTR_ATIME	= (1 << 4)
FATTR_MTIME	= (1 << 5)
FATTR_FH	= (1 << 6)
FATTR_ATIME_NOW	= (1 << 7)
FATTR_MTIME_NOW	= (1 << 8)
FATTR_LOCKOWNER	= (1 << 9)
FATTR_CTIME	= (1 << 10)

# INIT request/reply flags - field flags.
# Because pysinter treats the fields flags and flags2 as one
# 64 bit field, no special casing is necessary for offsets
# beyond 32.
FUSE_ASYNC_READ		= (1 << 0)
FUSE_POSIX_LOCKS	= (1 << 1)
FUSE_FILE_OPS		= (1 << 2)
FUSE_ATOMIC_O_TRUNC	= (1 << 3)
FUSE_EXPORT_SUPPORT	= (1 << 4)
FUSE_BIG_WRITES		= (1 << 5)
FUSE_DONT_MASK		= (1 << 6)
FUSE_SPLICE_WRITE	= (1 << 7)
FUSE_SPLICE_MOVE	= (1 << 8)
FUSE_SPLICE_READ	= (1 << 9)
FUSE_FLOCK_LOCKS	= (1 << 10)
FUSE_HAS_IOCTL_DIR	= (1 << 11)
FUSE_AUTO_INVAL_DATA	= (1 << 12)
FUSE_DO_READDIRPLUS	= (1 << 13)
FUSE_READDIRPLUS_AUTO	= (1 << 14)
FUSE_ASYNC_DIO		= (1 << 15)
FUSE_WRITEBACK_CACHE	= (1 << 16)
FUSE_NO_OPEN_SUPPORT	= (1 << 17)
FUSE_PARALLEL_DIROPS    = (1 << 18)
FUSE_HANDLE_KILLPRIV	= (1 << 19)
FUSE_POSIX_ACL		= (1 << 20)
FUSE_ABORT_ERROR	= (1 << 21)
FUSE_MAX_PAGES		= (1 << 22)
FUSE_CACHE_SYMLINKS	= (1 << 23)
FUSE_NO_OPENDIR_SUPPORT = (1 << 24)
FUSE_EXPLICIT_INVAL_DATA = (1 << 25)
FUSE_MAP_ALIGNMENT	= (1 << 26)
FUSE_SUBMOUNTS		= (1 << 27)
FUSE_HANDLE_KILLPRIV_V2	= (1 << 28)
FUSE_SETXATTR_EXT	= (1 << 29)
FUSE_INIT_EXT		= (1 << 30)
FUSE_INIT_RESERVED	= (1 << 31)
FUSE_SECURITY_CTX	= (1 << 32)
FUSE_HAS_INODE_DAX	= (1 << 33)

# Opcodes - enum fuse_opcode
FUSE_LOOKUP		= 1
FUSE_FORGET		= 2
FUSE_GETATTR		= 3
FUSE_SETATTR		= 4
FUSE_READLINK		= 5
FUSE_SYMLINK		= 6
FUSE_MKNOD		= 8
FUSE_MKDIR		= 9
FUSE_UNLINK		= 10
FUSE_RMDIR		= 11
FUSE_RENAME		= 12
FUSE_LINK		= 13
FUSE_OPEN		= 14
FUSE_READ		= 15
FUSE_WRITE		= 16
FUSE_STATFS		= 17
FUSE_RELEASE		= 18
FUSE_FSYNC		= 20
FUSE_SETXATTR		= 21
FUSE_GETXATTR		= 22
FUSE_LISTXATTR		= 23
FUSE_REMOVEXATTR	= 24
FUSE_FLUSH		= 25
FUSE_INIT		= 26
FUSE_OPENDIR		= 27
FUSE_READDIR		= 28
FUSE_RELEASEDIR		= 29
FUSE_FSYNCDIR		= 30
FUSE_GETLK		= 31
FUSE_SETLK		= 32
FUSE_SETLKW		= 33
FUSE_ACCESS		= 34
FUSE_CREATE		= 35
FUSE_INTERRUPT		= 36
FUSE_BMAP		= 37
FUSE_DESTROY		= 38
FUSE_IOCTL		= 39
FUSE_POLL		= 40
FUSE_NOTIFY_REPLY	= 41
FUSE_BATCH_FORGET	= 42
FUSE_FALLOCATE		= 43
FUSE_READDIRPLUS	= 44
FUSE_RENAME2		= 45
FUSE_LSEEK		= 46
FUSE_COPY_FILE_RANGE	= 47
