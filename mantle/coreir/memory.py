from magma import *
from magma.bit_vector import BitVector


def gen_sim_mem(depth, width):
    def sim_mem(self, value_store, state_store):
        cur_clk = value_store.get_value(self.clk)

        if not state_store:
            state_store['mem'] = [
                BitVector(0, width) for _ in range(depth)
            ]
            state_store['prev_clk'] = cur_clk


        prev_clk = state_store['prev_clk']
        clk_edge = cur_clk and not prev_clk
        rdata = value_store.get_value(self.rdata)

        if clk_edge:
            index = BitVector(value_store.get_value(self.raddr)).as_int()
            rdata = state_store['mem'][index].as_bool_list()
        if clk_edge:
            if value_store.get_value(self.wen):
                index = BitVector(value_store.get_value(self.waddr)).as_int()
                state_store['mem'][index] = BitVector(value_store.get_value(self.wdata))

        state_store['prev_clk'] = cur_clk
        value_store.set_value(self.rdata, rdata)
    return sim_mem


@cache_definition
def DefineCoreirMem(depth, width):
    name = "coreir_mem{}x{}".format(depth,width)
    addr_width = max((depth-1).bit_length(), 1)
    IO = ["raddr", In(Bits(addr_width)),
          "rdata", Out(Bits(width)),
          "waddr", In(Bits(addr_width)),
          "wdata", In(Bits(width)),
          "clk", In(Clock),
          "wen", In(Bit) ]
    return DeclareCircuit(name, *IO, verilog_name="coreir_mem",
            coreir_name="mem", coreir_lib="coreir",
            simulate=gen_sim_mem(depth, width),
            coreir_genargs={"width": width, "depth": depth})
            # coreir_configargs={"init": "0"})

def DefineROM(height, width):
    """
    coreir doesn't have a ROM primitive yet
    """
    raise NotImplementedError()

def DefineRAM(height, width):
    addr_width = max(height.bit_length() - 1, 1)
    circ = DefineCircuit("RAM{}x{}".format(height, width),
        "RADDR", In(Bits(addr_width)),
        "RDATA", Out(Bits(width)),
        "RCLK",  In(Clock),
        "RE",    In(Bit),
        "WADDR", In(Bits(addr_width)),
        "WDATA", In(Bits(width)),
        "WCLK",  In(Clock),
        "WE",    In(Bit),
    )
    raise NotImplementedError("Coreir removed rclk/wclk")
    coreir_mem = DefineCoreirMem(height, width)()
    wire(circ.RADDR, coreir_mem.raddr)
    wire(circ.RDATA, coreir_mem.rdata)
    wire(circ.RCLK, coreir_mem.rclk)
    wire(circ.RE, coreir_mem.ren)
    wire(circ.WADDR, coreir_mem.waddr)
    wire(circ.WDATA, coreir_mem.wdata)
    wire(circ.WCLK, coreir_mem.wclk)
    wire(circ.WE, coreir_mem.wen)
    EndDefine()
    return circ

def DefineMemory(height, width, readonly=False):
    if readonly:
        return DefineROM(height, width)
    else:
        return DefineRAM(height, width)
