
from asyncio import run
from json import load, dumps
from logging import getLogger
from os import open as osopen, close as osclose, O_RDWR

from pysinter import Sinter, MAX32, FUSEError
from pysinter.dynamic import Operations
# from pysinter.examples.hello import FS_HELLO
from pysinter.examples.passthrough import Passthrough

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
    pt = Passthrough('.')
    ops = Operations(LOGGER, protocol["v7.31"], pt.make())
    tx = s.tx_async
    tx_sync = s.tx_sync
    while True:
        header, msg = s._recv()
        parsed = ops.parse(header.opcode, msg)
        print('\nRequest', header, parsed, msg)
        try:
            await ops._complete_one(tx, header, msg)
            header, errno, resmsg = tx_sync.get()
        except FUSEError as e:
            print('\nThrew error', header, parsed, e)
            errno = e.errno
            resmsg = b''
        if resmsg is None:
            print('\nNo reply necessary', header, parsed, resmsg)
        else:
            try:
                parsed_output = ops.parse_output(header.opcode, resmsg)
                print('\nRegular reply', header, parsed, parsed_output, '\nRaw reply body:', resmsg.hex())
            except ValueError:
                print('Value Error while parsing output', header, parsed, '\nRaw reply body:', resmsg.hex())
        s._send(header, errno, resmsg)


if __name__ == "__main__":
    run(main())
