
from asyncio import create_task, all_tasks, gather
from asyncio import create_task, all_tasks, gather
from errno import ENOSYS

from pysinter import FUSEError, ENCODING, BYTEORDER, frombytes

INFINITY = float('inf')

async def dyn_nop(header, parsed):
    '''
    Do nothing.
    '''
    return 0, {}

class Operations():
    '''
    A class to run per-opcode functions against a pair of asynchronous RX and
    TX queues as provided by an instance of the pysinter.Sinter class.
    The per-opcode functions are given as a dict and are expected to accept
    and produce dictionaries of field values. These dictionaries are extracted
    from and converted to FUSE messages according to the schema supplied with
    the first parameter.

    TODO: Currently all the formatting happens using dicts straight from the
            schema. Perhaps it would be nice to have a Formatter class to take
            care of verification and ensure efficient operation.
    '''
    def __init__(self, schema, action_by_opcode):
        self.active = True
        self._action_by_opcode = {
            opcode_value: action_by_opcode.get(opcode_name)
            for opcode_name, opcode_value in schema['opcodes'].items()
            }
        self._opcode_name_to_value = dict(schema['opcodes'].items())
        self._opcode_value_to_name = {
            opcode_value: opcode_name
            for opcode_name, opcode_value in schema['opcodes'].items()
            }
        self._format_in = {
            opcode_value: _sorted_by_pos(schema['operations'].get(opcode_name, {}).get('request'))
            for opcode_name, opcode_value in schema['opcodes'].items()
            }
        self._format_out = {
            opcode_value: _sorted_by_pos(schema['operations'].get(opcode_name, {}).get('response'))
            for opcode_name, opcode_value in schema['opcodes'].items()
            }
        return None
    def format(self, opcode, inpt):
        if inpt is None:
            return None
        fmt = self._format_out.get(opcode)
        if fmt is None:
            raise FUSEError(ENOSYS, "Opcode without formatter", opcode, inpt)
        return b''.join(_format_gen(fmt, inpt))
    def parse(self, opcode, inpt):
        fmt = self._format_in.get(opcode)
        if fmt is None:
            raise FUSEError(ENOSYS, "Opcode without parser", opcode, inpt)
        return self._parse(fmt, inpt)
    def parse_output(self, opcode, inpt):
        fmt = self._format_out.get(opcode)
        if fmt is None:
            raise FUSEError(ENOSYS, "Opcode without formatter", opcode, inpt)
        return self._parse(fmt, inpt)
    def _parse(self, fmt, inpt):
        resdict = {}
        for fieldname, spec in fmt.items():
            if spec.get('padding'):
                continue
            offset = spec['offset'] // 8
            size_raw = spec['size']
            if size_raw is None: #NULL terminated string or blob
                cstrpos = spec.get('cstringposition')
                if cstrpos is None:
                    resdict[fieldname] = inpt[offset:]
                    continue
                while True:
                    lastpos = offset
                    nullbytepos = inpt.find(b'\x00', lastpos)
                    if nullbytepos == -1:
                        raise ValueError('Bad C string', inpt, spec)
                    if not cstrpos:
                        resdict[fieldname] = inpt[lastpos:nullbytepos]
                        break
                    cstrpos = cstrpos - 1
                continue
            size = size_raw // 8
            if size <= 8:
                res = frombytes(inpt[offset:offset+size])
                if spec.get('signed', False) and 0x80 & inpt[offset]: #Assuming endianness here
                    res = res - 256**size #Is this correct?
                resdict[fieldname] = res
            else:
                resdict[fieldname] = inpt[offset:offset+size]
        return resdict
    async def _complete_one(self, tx, header, msg):
        opcode = header.opcode
        operation = self._action_by_opcode.get(opcode)
        if operation is None:
            raise FUSEError(ENOSYS, "Unknown or unimplemented opcode", header, msg)
        parsed = self.parse(opcode, msg)
        try:
            opres = await operation(header, parsed)
            errno, res = opres
            if isinstance(res, bytes):
                formatted = res
            else:
                formatted = self.format(opcode, res)
        except FUSEError as e:
            errno = e.errno
            formatted = b''
        return await tx.put((header, errno, formatted))
    async def operate(self, rx, tx):
        while self.active:
            header, msg = await rx.get()
            create_task(self._complete_one(tx, header, msg))
        await gather(*all_tasks()) #TODO: Make sure we only catch FUSE tasks here
        return None


def _sort_by_pos(tpl):
    v = tpl[1]
    offset = v['offset']
    if offset is None:
        offset = INFINITY
    return (offset, v.get('cstringposition', INFINITY))

def _sorted_by_pos(inpt):
    '''
    Helper that enables correct operation even when the schema does not
    give an operation's fields ordered by their positions.

    TODO: Validate that the schema does not leave gaps and has no misplaced
    variable-length fields.
    '''
    if not isinstance(inpt, dict):
        return inpt
    res = {}
    for k, v in sorted(inpt.items(), key=_sort_by_pos):
        res[k] = v
    return res

def _format_gen(fmt, inpt):
    if fmt is None:
        return
    for k, v in fmt.items():
        if v.get('padding', False):
            yield bytes(size)
            continue
        res = inpt.get(k)
        size_raw = v['size']
        if size_raw is None:
            if v.get('cstringposition') is None:
                if res is None:
                    yield b''
                    continue
                if isinstance(res, bytes):
                    yield res
                    continue
                raise ValueError(
                    'Data field must be given as bytes'
                    , k, res, v, inpt
                    )
            elif isinstance(res, bytes):
                try:
                    assert res.index(0) == len(res) - 1
                except (IndexError, AssertionError) as e:
                    raise ValueError(
                        'String fields must contain exactly one null ' +
                            'byte that must be placed at index -1 .'
                        , k, res, v, inpt
                        ) from e
                yield res
                continue
            elif isinstance(res, str):
                yield res.encode(ENCODING) + b'\x00'
                continue
            else:
                raise ValueError(
                    'String fields must be given as str or ' +
                        'null-terminated bytes'
                    , k, res, v, inpt
                    )
        size = size_raw // 8
        if res is None:
            yield bytes(size)
            continue
        elif isinstance(res, bytes):
            if len(res) != size:
                raise ValueError(
                    'Bad bytes size for field'
                    , k, res, v, inpt
                    )
            yield res
            continue
        elif isinstance(res, int):
            signed = v.get('signed', False)
            try:
                yield res.to_bytes(size, BYTEORDER, signed=signed)
            except OverflowError as e:
                raise ValueError(
                    'Bad int size for field'
                    , k, res, v, inpt
                    ) from e
            continue
        else:
            raise ValueError(
                'Fixed-length fields must be given as bytes, int, or None'
                , k, res, v, inpt
                )
