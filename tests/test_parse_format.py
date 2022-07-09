
from json import dumps, load
from logging import getLogger

from pysinter.dynamic import Operations
# from pysinter.examples.hello import FS_HELLO

PROTOSOURCE = '../sinter/protocol/protocol.json'
VERSION = 'v7.31'
LOGGER = getLogger(__name__)

def mk_operations():
    with open(PROTOSOURCE) as handle:
        protocol = load(handle)
    return Operations(LOGGER, protocol[VERSION], {})

def test_mk_operations():
    mk_operations()

def test_generate_fields():
    ops = mk_operations()
    for k, v in ops._opcode_name_to_value.items():
        try:
            res = ops.format(v, {})
        except (ConnectionError, NotImplementedError):
            continue
        LOGGER.debug('Opcode %s result %s', k, res.hex())

def test_generate_parse():
    ops = mk_operations()
    for k, v in ops._opcode_name_to_value.items():
        try:
            res = ops.format(v, {})
        except (ConnectionError, NotImplementedError):
            continue
        fields = ops.parse_output(v, res)
        LOGGER.debug('Opcode %s result %s', k, fields)

