
from asyncio import run
from json import load, dumps

from pysinter import Sinter, MAX32, FUSEError
from pysinter.dynamic import Operations
from pysinter.examples.hello import FS_HELLO

async def main():
    with open('../sinter/protocol/protocol.json') as handle:
        protocol = load(handle)
    s = Sinter(fd='FUSEFD')
    ops = Operations(protocol["v7.31"], FS_HELLO)
    tx = s.tx_async
    tx_sync = s.tx_sync
    while True:
        header, msg = s._recv()
        parsed = ops.parse(header.opcode, msg)
        try:
            await ops._complete_one(tx, header, msg)
            header, errno, resmsg = tx_sync.get()
            print('\nRegular reply', header, parsed, ops.parse_output(header.opcode, resmsg))
        except FUSEError as e:
            print('\nThrew error', header, parsed, e)
            errno = e.errno
            resmsg = b''
        s._send(header, errno, resmsg)


async def main_():
    print("Hello, world!")
    with open('../sinter/protocol/protocol.json') as handle:
        protocol = load(handle)
    print(dumps(protocol, indent=2))
    s = Sinter(fd='FUSEFD')
    ops = Operations(protocol["v7.31"], FS_HELLO)
    first_header, first_body = s._recv()
    parsed = ops.parse(first_header.opcode, first_body)
    print(first_header)
    print(first_body)
    print(parsed)
    response = {
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
    formatted = ops.format(first_header.opcode, response)
    print(formatted)
    res = s._send(first_header, 0, formatted)
    print(res)
    second_header, second_body = s._recv()
    parsed = ops.parse(second_header.opcode, second_body)
    print(second_header)
    print(second_body)
    print(parsed)
    # Get fd
    # Run sample FS


if __name__ == "__main__":
    run(main())
