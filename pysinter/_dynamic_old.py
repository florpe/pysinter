
from asyncio import create_task, all_tasks, gather
from errno import ENOSYS
from json import dumps

from pysinter import FUSEError, ENCODING, BYTEORDER, frombytes

INFINITY = float('inf')

async def dyn_nop(header, parsed):
    '''
    Do nothing.
    '''
    return 0, {}
async def dyn_nosend(header, parsed):
    '''
    Do nothing, not even header replying.
    '''
    return 0, None

def _flatten(structs, schema, offset=0):
    '''
    Extracts information about field makeup from the schema, recursing into
    nested struct fields. Assumption: The field names do not conflict with
    the struct member names.
    '''
    pos = 0
    for k, v in schema.items():
        structname = v.get('struct')
        raw_size = v['size']
        raw_offset = v['offset']
        if raw_offset is not None and pos is not None:
            if raw_offset // 8 != pos:
                raise ValueError('Documented offset does not match experimental data', k, v, schema)
        if raw_size is not None:
            fieldsize = raw_size // 8
            newpos = pos + fieldsize
        else:
            fieldsize = None
            newpos = None
        if structname is None:
            yield k, (None if pos is None else offset + pos, fieldsize, dict(v))
        else:
            for subentry in _flatten(structs, structs[structname]['fields'], offset=offset + pos):
                yield subentry
        pos = newpos

def _after_flatten_key(inpt):
    '''
    Sort after flattening.
    '''
    offset = inpt[1][0]
    if offset is None:
        offset = INFINITY
    return offset, inpt[1][2].get('cstringposition', INFINITY)

class Formatter():
    '''
    Parsing and formatting FUSE messages for one opcode and one direction
    according to the schema.
    '''
    def __init__(self, structs, name, schema):
        '''
        Initialization: Schema extraction and flattening.
        '''
        self._name = name
        self._structs = structs
        if schema == None:
            self._exception = ConnectionError('This opcode does not support this operation', self._name)
            self._schema = None
        elif schema == -1:
            self._exception = NotImplementedError
            self._schema = None
        else:
            self._exception = None
            self._schema = tuple(sorted(_flatten(structs, schema), key=_after_flatten_key))
        return None
    def parse(self, inpt):
        '''
        Parsing: From message to dictionary.
        '''
        if self._exception is not None:
            raise self._exception
        res = {}
        pos = 0
        for fieldname, (offset, size, data) in self._schema:
            if size is None:
                cstrpos = data.get('cstringposition')
                if cstrpos is None:
                    res[fieldname] = inpt[pos:]
                    break
                nullbytepos = inpt.find(b'\x00', pos)
                if nullbytepos == -1:
                    raise ValueError('Bad C string', inpt, self._name, fieldname, self._schema)
                res[fieldname] = inpt[pos:nullbytepos]
                pos = nullbytepos + 1
                continue
            fieldbytes = inpt[pos:pos+size]
            if size <= 8:
                res[fieldname] = frombytes(fieldbytes)
                if data.get('signed', False) and 0x80 & inpt[pos]: #Assuming endianness here
                    res = res - 256**size #Is this correct?
            else:
                res[fieldname] = fieldbytes
            pos = pos + size
        return res
    def generate_fields(self, inpt):
        '''
        Formatting: From dictionary to stream of fields.
        '''
        if self._exception is not None:
            raise self._exception
        for fieldname, (offset, size, data) in self._schema:
            if size is None:
                outval = inpt.get(fieldname, b'')
                cstrpos = data.get('cstringposition')
                if cstrpos is None:
                    yield outval
                    break
                yield outval + b'\x00'
                continue
            if size <= 8:
                outval = inpt.get(fieldname, 0)
                yield outval.to_bytes(size, BYTEORDER, signed=data.get('signed', False))
            else:
                yield inpt.get(fieldname, bytes(size))




class Operations():
    '''
    A class to run per-opcode functions against a pair of asynchronous RX and
    TX queues as provided by an instance of the pysinter.Sinter class.
    The per-opcode functions are given as a dict and are expected to accept
    and produce dictionaries of field values. These dictionaries are extracted
    from and converted to FUSE messages according to the schema supplied with
    the first parameter.
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
        self._formatter_request = {
            opcode_value: Formatter(schema['structs'], opcode_name, schema['operations'].get(opcode_name, {}).get('request'))
            for opcode_name, opcode_value in schema['opcodes'].items()
            }
        self._formatter_response = {
            opcode_value: Formatter(schema['structs'], opcode_name, schema['operations'].get(opcode_name, {}).get('response'))
            for opcode_name, opcode_value in schema['opcodes'].items()
            }
        return None
    def format(self, opcode, inpt):
        '''
        Run the opcode's response formatter.
        '''
        if inpt is None:
            return None
        fmt = self._formatter_response.get(opcode)
        if fmt is None:
            raise FUSEError(ENOSYS, "Opcode without formatter", opcode, inpt)
        return b''.join(fmt.generate_fields(inpt))
    def parse(self, opcode, inpt):
        '''
        Run the opcode's request parser.
        '''
        fmt = self._formatter_request.get(opcode)
        if fmt is None:
            raise FUSEError(ENOSYS, "Opcode without formatter", opcode, inpt)
        return fmt.parse(inpt)
    def parse_output(self, opcode, inpt):
        '''
        Run the opcode's response parser.
        '''
        fmt = self._formatter_response.get(opcode)
        if fmt is None:
            raise FUSEError(ENOSYS, "Opcode without formatter", opcode, inpt)
        return fmt.parse(inpt)
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
