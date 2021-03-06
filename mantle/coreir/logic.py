from magma import *
from magma.bit_vector import BitVector
from magma.compatibility import IntegerTypes
import operator
from functools import reduce


def get_length(value):
    if isinstance(value, (BitType, ClockType, EnableType, ResetType)):
        return None
    elif isinstance(value, ArrayType):
        return len(value)
    else:
        raise NotImplementedError("Cannot get_length of"
                " {}".format(type(value)))


@cache_definition
def DefineFoldOp(DefineOp, name, height, width):
    if width is None:
        T = Bit
    else:
        T = Bits(width)
    IO = []
    for i in range(height):
        IO += ["I{}".format(i), In(T)]
    IO += ["O", Out(T)]
    circ = DefineCircuit("fold_{}{}{}".format(name, height, width), *IO)
    reduce_args = [getattr(circ, "I{}".format(i)) for i in range(height)]
    Op2 = DefineOp(2, width)
    wire(reduce(lambda x, y: Op2()(x, y), reduce_args), circ.O)
    EndDefine()
    return circ


def declare_bit_binop(name, python_op):
    def simulate(self, value_store, state_store):
        in0 = BitVector(value_store.get_value(self.in0))
        in1 = BitVector(value_store.get_value(self.in1))
        out = python_op(in0, in1).as_bool_list()[0]
        value_store.set_value(self.out, out)

    coreir_circ = DeclareCircuit("{}".format(name),
                          'in0', In(Bit), 'in1', In(Bit), 'out', Out(Bit),
                          simulate=simulate,
                          verilog_name = "coreir_" + name,
                          coreir_lib = "corebit")

    circ = DefineCircuit("{}_wrapped".format(name),
        'I0', In(Bit), 'I1', In(Bit), 'O', Out(Bit))
    inst = coreir_circ()
    wire(circ.I0, inst.in0)
    wire(circ.I1, inst.in1)
    wire(circ.O, inst.out)
    EndDefine()
    return circ

def DefineCoreirReduce(op_name, python_op, width):
    def simulate(self, value_store, state_store):
        in_ = BitVector(value_store.get_value(getattr(self, "in")))
        out = reduce(python_op, in_)
        value_store.set_value(self.out, out)
    decl = DeclareCircuit(op_name, "in", In(Bits(width)), "out", Out(Bit),
            coreir_name = op_name,
            coreir_lib = "coreir",
            coreir_genargs = {"width": width},
            simulate = simulate)
    return decl

def DefineCoreirReduceAnd(width):
    return DefineCoreirReduce("andr", operator.and_, width)

def DefineCoreirReduceOr(width):
    return DefineCoreirReduce("orr", operator.or_, width)
    # class ReduceAnd(Circuit):
    #     name = f"reduce_and_{width}"
    #     IO = ["I", In(Bits(width)), "O", Out(Bit)]
    #     @classmethod
    #     def definition(io):
    #         circ = decl()
    #         wire(getattr(circ, "in"), io.I)
    #         wire(circ.out, io.O)
    # return ReduceAnd


BitAnd = declare_bit_binop("and", operator.and_)
BitOr  = declare_bit_binop("or", operator.or_)
BitXOr = declare_bit_binop("xor", operator.xor)


def declare_bits_binop(name, python_op):
    def simulate(self, value_store, state_store):
        in0 = BitVector(value_store.get_value(self.in0))
        in1 = BitVector(value_store.get_value(self.in1))
        out = python_op(in0, in1).as_bool_list()
        # print(f"{python_op}({in0}, {in1}), {out}")
        value_store.set_value(self.out, out)

    @cache_definition
    def Declare(N):
        T = Bits(N)
        coreir_circ = DeclareCircuit("{}{}".format(name, N),
                              'in0', In(T), 'in1', In(T), 'out', Out(T),
                              simulate       = simulate,
                              verilog_name   = "coreir_" + name,
                              coreir_name    = name,
                              coreir_lib     = "coreir",
                              coreir_genargs = {"width": N})
        circ = DefineCircuit("{}{}_wrapped".format(name, N),
            'I0', In(T), 'I1', In(T), 'O', Out(T))
        inst = coreir_circ()
        wire(circ.I0, inst.in0)
        wire(circ.I1, inst.in1)
        wire(circ.O, inst.out)
        EndDefine()
        return circ

    return Declare

DefineCoreirAnd = declare_bits_binop("and", operator.and_)

def DefineOp(op_name, DefineCoreirReduce, height, width):
    if width is None:
        T = Bit
    else:
        T = Bits(width)
    IO = []
    for i in range(height):
        IO += ["I{}".format(i), In(T)]
    IO += ["O", Out(T)]
    circ = DefineCircuit(f"{op_name}{height}x{width}", *IO)
    if width is None:
        reduce = DefineCoreirReduce(height)()
        for j in range(height):
            wire(getattr(reduce, "in")[j], getattr(circ, f"I{j}"))
        wire(reduce.out, circ.O)
    else:
        for i in range(width):
            reduce = DefineCoreirReduce(height)()
            for j in range(height):
                wire(getattr(reduce, "in")[j], getattr(circ, f"I{j}")[i])
            wire(reduce.out, circ.O[i])
    EndDefine()
    return circ

@cache_definition
def DefineAnd(height=2, width=None):
    if height is 2:
        if width is None:
            return BitAnd
        else:
            return DefineCoreirAnd(width)
    return DefineOp("And", DefineCoreirReduceAnd, height, width)


def And(height, width=None, **kwargs):
    return DefineAnd(height, width)(**kwargs)

def ReduceAnd(height=2, **kwargs):
    return uncurry(And(height, **kwargs))


@cache_definition
def DefineNAnd(height=2, width=None):
    if width is None:
        T = Bit
    else:
        T = Bits(width)
    IO = []
    for i in range(height):
        IO += ["I{}".format(i), In(T)]
    IO += ["O", Out(T)]
    circ = DefineCircuit("NAnd{}{}".format(height, width),
        *IO)
    inputs = [getattr(circ, 'I{}'.format(i)) for i in range(height)]
    if width is None:
        inv = Not()
    else:
        inv = Invert(width)
    out = inv(And(height, width)(*inputs))
    wire(out, circ.O)
    EndDefine()
    return circ


def NAnd(height, width=None, **kwargs):
    return DefineNAnd(height, width)(**kwargs)

def ReduceNAnd(height=2, **kwargs):
    return uncurry(NAnd(height, **kwargs))


def simulate_bit_not(self, value_store, state_store):
    _in = BitVector(value_store.get_value(getattr(self, "in")))
    out = (~_in).as_bool_list()[0]
    value_store.set_value(self.out, out)


DefineCoreirNot = DeclareCircuit("not", 'in', In(Bit), 'out', Out(Bit),
    simulate=simulate_bit_not, verilog_name="coreir_bitnot", coreir_lib="corebit")

@cache_definition
def DefineNot(width=None):
    if width != None:
        raise ValueError("Not is only defined as a 1-bit operation, width must"
                " be None")
    return DefineCoreirNot

def Not(width=None):
    return DefineNot(width)()


def not_(arg, **kwargs):
    return Not(get_length(arg), **kwargs)(arg)



DefineCoreirOr  = declare_bits_binop("or", operator.or_)


@cache_definition
def DefineOr(height=2, width=None):
    if height is 2:
        if width is None:
            return BitOr
        else:
            return DefineCoreirOr(width)
    return DefineOp("Or", DefineCoreirReduceOr, height, width)


def Or(height, width=None, **kwargs):
    return DefineOr(height, width)(**kwargs)

def ReduceOr(height=2, **kwargs):
    return uncurry(Or(height, **kwargs))


@cache_definition
def DefineNOr(height=2, width=None):
    if width is None:
        T = Bit
    else:
        T = Bits(width)
    IO = []
    for i in range(height):
        IO += ["I{}".format(i), In(T)]
    IO += ["O", Out(T)]
    circ = DefineCircuit("NOr{}{}".format(height, width),
        *IO)
    inputs = [getattr(circ, 'I{}'.format(i)) for i in range(height)]
    if width is None:
        inv = Not()
    else:
        inv = Invert(width)
    out = inv(Or(height, width)(*inputs))
    wire(out, circ.O)
    EndDefine()
    return circ


def NOr(height, width=None, **kwargs):
    return DefineNOr(height, width)(**kwargs)

def ReduceNOr(height=2, **kwargs):
    return uncurry(NOr(height, **kwargs))


DefineCoreirXOr = declare_bits_binop("xor", operator.xor)


@cache_definition
def DefineXOr(height=2, width=None):
    if height is 2:
        if width is None:
            return BitXOr
        else:
            return DefineCoreirXOr(width)
    else:
        return DefineFoldOp(DefineXOr, "xor", height, width)


def XOr(height, width=None, **kwargs):
    return DefineXOr(height, width)(**kwargs)

def ReduceXOr(height=2, **kwargs):
    return uncurry(XOr(height, **kwargs))


@cache_definition
def DefineNXOr(height=2, width=None):
    if width is None:
        T = Bit
    else:
        T = Bits(width)
    IO = []
    for i in range(height):
        IO += ["in{}".format(i), In(T)]
    IO += ["out", Out(T)]
    circ = DefineCircuit("NXOr{}{}".format(height, width),
        *IO)
    inputs = [getattr(circ, 'in{}'.format(i)) for i in range(height)]
    if width is None:
        inv = Not()
    else:
        inv = Invert(width)
    out = inv(XOr(height, width)(*inputs))
    wire(out, circ.out)
    EndDefine()
    return circ


def NXOr(height, width=None, **kwargs):
    return DefineXOr(height, width)(**kwargs)

def ReduceNXOr(height=2, **kwargs):
    return uncurry(NXOr(height, **kwargs))


def simulate_bits_invert(self, value_store, state_store):
    _in = BitVector(value_store.get_value(getattr(self, "in")))
    out = (~_in).as_bool_list()
    value_store.set_value(self.out, out)

@cache_definition
def DefineInvert(width):
    T = Bits(width)
    decl = DeclareCircuit("Invert{}".format(width),
            'in', In(T), 'out', Out(T),
            simulate       = simulate_bits_invert,
            verilog_name   = "coreir_not",
            coreir_name    = "not",
            coreir_lib     = "coreir",
            coreir_genargs = {"width": width})
    circ = DefineCircuit("Invert{}_wrapped".format(width),
        "I", In(T), "O", Out(T))
    prim = decl()
    wire(circ.I, getattr(prim, "in"))
    wire(circ.O, prim.out)
    EndDefine()
    return circ

def Invert(width=None, **kwargs):
    return DefineInvert(width)(**kwargs)


def invert(arg, **kwargs):
    return Invert(get_length(arg), **kwargs)(arg)


@cache_definition
def DefineLSL(width):
    T = Bits(width)
    def simulate(self, value_store, state_store):
        in0 = BitVector(value_store.get_value(self.in0))
        in1 = BitVector(value_store.get_value(self.in1))
        out = (in0 << in1).as_bool_list()
        value_store.set_value(self.out, out)

    return DeclareCircuit("shl{}".format(width), 'in0', In(T), 'in1',
            In(UInt(width)), 'out', Out(T), verilog_name="coreir_shl",
            coreir_name="shl", coreir_lib="coreir", simulate=simulate,
            coreir_genargs={"width": width})


def LSL(width, **kwargs):
    return DefineLSL(width)(**kwargs)


def lsl(I0, I1, **kwargs):
    if not get_length(I0) == get_length(I1):
        raise ValueError("All arguments should have the same length")
    width = get_length(I0)
    return LSL(width, **kwargs)(I0, I1)


@cache_definition
def DefineLSR(width):
    T = Bits(width)
    def simulate(self, value_store, state_store):
        in0 = BitVector(value_store.get_value(self.in0))
        in1 = BitVector(value_store.get_value(self.in1))
        out = (in0 << in1).as_bool_list()
        value_store.set_value(self.out, out)

    return DeclareCircuit("lshr{}".format(width), 'in0', In(T), 'in1',
            In(UInt(width)), 'out', Out(T), verilog_name="coreir_lshr",
            coreir_name="lshr", coreir_lib="coreir", simulate=simulate,
            coreir_genargs={"width": width})


def LSR(width, **kwargs):
    return DefineLSR(width)(**kwargs)


def lsr(I0, I1, **kwargs):
    if not get_length(I0) == get_length(I1):
        raise ValueError("All arguments should have the same length")
    width = get_length(I0)
    return LSR(width, **kwargs)(I0, I1)


@cache_definition
def DefineStaticLeftShift(width, shift_amount):
    T = Bits(width)
    class _StaticLeftShift(Circuit):
        name = 'StaticLeftShift_{}{}'.format(width, shift_amount)

        IO = ["I", In(T), "O", Out(T)]

        @classmethod
        def definition(io):
            output = concat(io.I[shift_amount:width], bits(0, shift_amount))
            wire(output, io.O)
    return _StaticLeftShift

def StaticLeftShift(width, shift_amount, **kwargs):
    return DefineStaticLeftShift(width, shift_amount)(**kwargs)

def static_left_shift(arg, shift_amount, **kwargs):
    width = get_length(arg)
    return StaticLeftShift(width, shift_amount, **kwargs)(arg)

@cache_definition
def DefineStaticRightShift(width, shift_amount):
    T = Bits(width)
    class _StaticRightShift(Circuit):
        name = 'StaticRightShift_{}{}'.format(width, shift_amount)

        IO = ["I", In(T), "O", Out(T)]

        @classmethod
        def definition(io):
            output = concat(bits(0, shift_amount), io.I[:width-shift_amount])
            wire(output, io.O)
    return _StaticRightShift

def StaticRightShift(width, shift_amount, **kwargs):
    return DefineStaticRightShift(width, shift_amount)(**kwargs)

def static_right_shift(arg, shift_amount, **kwargs):
    width = get_length(arg)
    return StaticRightShift(width, shift_amount, **kwargs)(arg)
