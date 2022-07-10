
from asyncio import create_task, all_tasks, gather
from copy import deepcopy
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

def _struct_key(inpt):
    fieldval = inpt[1]
    offset = fieldval['offset']
    if offset is None:
        offset = INFINITY
    cstringpos = fieldval.get('cstringposition', INFINITY)
    return (offset, cstringpos)

def _replace_struct(logger, structs, schema, schema_is_struct=False):
    if schema_is_struct:
        res = {
            None: {
                'structname': schema['structname']
                , 'pad_to': schema.get('pad_to', 0)
                }
            }
        schema = deepcopy(schema['fields'])
    else:
        schema = deepcopy(schema)
        res = {}
    for fieldname, fieldval in sorted(schema.items(), key=_struct_key):
        structname = fieldval.get('struct')
        resval = deepcopy(fieldval)
        if structname is not None: #Recursion shouldn't go too deep here
            struct = _replace_struct(
                logger.getChild(structname)
                , structs
                , structs[structname]
                , schema_is_struct=True
                )
            resval['struct'] = struct
        res[fieldname] = resval
    return res

def _generate_fields(logger, schema, inpt, is_single_instance=False, is_struct=False, pos=0):
    logger.debug('Generating: %s , %s', schema, inpt)
    #TODO: Padding
    meta = schema.get(None, {})
    for fname, fshape in schema.items():
        if fname is None:
            continue
        struct = fshape.get('struct')
        if struct:
            #TODO: Repeating structs
            if fshape.get('zero_or_more') and not is_single_instance:
                instances = inpt.get(fname, [])
                if isinstance(instances, dict):
                    raise ValueError(
                        'Zero-or-more struct fields demand an iterable of dicts'
                        , fname, fshape, instances, inpt
                        )
            else:
                single_instance = inpt.get(fname, {})
                if not isinstance(single_instance, dict):
                    raise ValueError(
                        'Exactly-once struct fields demand a dict'
                        , fname, fshape, inpt
                        )
                instances = (single_instance,)
            for instancenum, instance in enumerate(instances):
                for pos, val in _generate_fields(
                    logger.getChild(fname).getChild(str(instancenum))
                    , struct
                    , instance
                    , is_single_instance=True
                    , is_struct=True
                    , pos=pos
                    ):
                    yield pos, val
            continue
        size = fshape['size']
        if size is None:
            cstrpos = schema.get('cstringposition')
            if cstrpos is None:
                val = inpt.get(fname, b'')
                logger.debug(
                    'Yielding data field %s value %s'
                    , fname, val
                    )
            else:
                val = inpt.get(fname, b'') + b'\x00'
                logger.debug(
                    'Yielding cstring field %s value %s'
                    , fname, val
                    )
        elif size <= 64:
            bytesize = size // 8
            #Assuming endianness here
            signed = fshape.get('signed')
            val = inpt.get(fname, 0).to_bytes(
                bytesize
                , BYTEORDER
                , signed=signed
                )
            logger.debug(
                    'Yielding small value field %s value %s'
                    , fname, val
                    )
        else:
            bytesize = size // 8
            val = inpt.get(fname, bytes(bytesize))
            if len(val) != bytesize:
                raise ValueError('Bad field size', fname, val, schema)
            logger.debug(
                'Yielding large value field %s value %s'
                , fname, val
                )
        pos = pos + len(val)
        yield pos, val
    pad_to = meta.get('pad_to', 0) // 8
    if pad_to:
        missing = -pos % pad_to
        if missing:
            yield pos + missing, bytes(missing)

def _parse_fields(logger, schema, inpt, position):
    res = {}
    meta = schema.get(None, {})
    for fname, fshape in schema.items():
        if fname is None:
            continue
        struct = fshape.get('struct')
        if struct:
            position, fval = _parse_fields(
                logger.getChild(struct[None]['structname'])
                , struct
                , inpt
                , position
                )
            res[fname] = fval
            continue
        size = fshape['size']
        if size is None:
            cstrpos = fshape.get('cstringposition')
            if cstrpos is None:
                #TODO: This only works if this struct is last in line
                res[fname] = inpt[position:]
                position = len(inpt)
                break
            nullbytepos = inpt.find(b'\x00', position)
            if nullbytepos == -1:
                raise ValueError(
                    'Bad C string'
                    , fname, fshape, position, inpt
                    )
            res[fname] = inpt[position:nullbytepos]
            position = nullbytepos + 1
            continue
        realsize = size // 8
        val_raw = inpt[position:position+realsize] 
        if realsize <= 8:
            signed = fshape.get('signed')
            res[fname] = int.from_bytes(
                val_raw
                , byteorder=BYTEORDER
                , signed=signed
                )
        else:
            res[fname] = val_raw
        position = position + realsize
    pad_to = meta.get('pad_to', 0) // 8
    if pad_to:
        position = position + (-position % pad_to)
    return position, res

class Formatter():
    def __init__(self, logger, structs, name, schema):
        self._name = name
        self._logger = logger
        if schema == -1:
            self._schema = None
            self._exception = NotImplementedError
        elif schema is None:
            self._schema = None
            self._exception = ConnectionError(
                'This opcode does not support this operation'
                , self._name
                )
        else:
            self._schema = _replace_struct(logger, structs, schema)
            self._exception = None
        return None
    def parse(self, inpt):
        '''
        Parsing: From message to dictionary.
        '''
        if self._exception:
            raise self._exception
        respos, res = _parse_fields(
            self._logger.getChild('parse')
            , self._schema
            , inpt
            , 0
            )
        if respos != len(inpt):
            raise ValueError(
                'Incomplete parse'
                , self._name, respos, res, self._schema, inpt
                )
        return res
    def generate_fields(self, inpt):
        '''
        Formatting: From dictionary to stream of fields.
        '''
        if self._exception:
            raise self._exception
        return _generate_fields(
            self._logger.getChild('generate')
            , self._schema
            , inpt
            )


class Operations():
    '''
    A class to run per-opcode functions against a pair of asynchronous RX and
    TX queues as provided by an instance of the pysinter.Sinter class.
    The per-opcode functions are given as a dict and are expected to accept
    and produce dictionaries of field values. These dictionaries are extracted
    from and converted to FUSE messages according to the schema supplied with
    the first parameter.
    '''
    def __init__(self, logger, schema, action_by_opcode):
        self.active = True
        self._logger = logger
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
            opcode_value: Formatter(
                logger.getChild(opcode_name)
                , schema['structs']
                , opcode_name
                , schema['operations'].get(opcode_name, {}).get('request')
                )
            for opcode_name, opcode_value in schema['opcodes'].items()
            }
        self._formatter_response = {
            opcode_value: Formatter(
                logger.getChild(opcode_name)
                , schema['structs']
                , opcode_name
                , schema['operations'].get(opcode_name, {}).get('response')
                )
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
        return b''.join((field for _, field in fmt.generate_fields(inpt)))
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
