
from asyncio import run
from json import load, dumps
from logging import getLogger

from pysinter import Sinter, MAX32, FUSEError
from pysinter.dynamic import Operations
from pysinter.examples.hello import FS_HELLO
from pysinter.examples.passthrough import LIBC

LOGGER = getLogger(__name__)

async def main():
    '''
    Testing the components. No threading, the FUSE read write loop runs
    synchronously in this function.

    TODO: A bit of an interface. Specifying protocol location and version
            would be nice, for example.
    '''
    with open('../sinter/protocol/protocol.json') as handle:
        protocol = load(handle)
    s = Sinter(fd='FUSEFD')
    ops = Operations(LOGGER, protocol["v7.31"], FS_HELLO)
    tx = s.tx_async
    tx_sync = s.tx_sync
    while True:
        header, msg = s._recv()
        parsed = ops.parse(header.opcode, msg)
        print('\nRequest', header, parsed, msg)
        try:
            await ops._complete_one(tx, header, msg)
            header, errno, resmsg = tx_sync.get()
            try:
                print('\nRegular reply', header, parsed, ops.parse_output(header.opcode, resmsg), '\n', resmsg.hex())
            except ValueError:
                pass
        except FUSEError as e:
            print('\nThrew error', header, parsed, e)
            errno = e.errno
            resmsg = b''
        s._send(header, errno, resmsg)


if __name__ == "__main__":
    run(main())
