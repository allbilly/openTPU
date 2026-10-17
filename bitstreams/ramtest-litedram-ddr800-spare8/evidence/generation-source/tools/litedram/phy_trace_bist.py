"""Passive 256-cycle command/PHY trace, appended to the raw BIST CSR bank.

Each BIST start arms a fresh linear capture. No trace output drives traffic or
PHY controls. Read index selects a frozen BRAM row; allow two sys clocks after
changing it. Rows are packed least-significant field first per TRACE_FIELDS.
The PHY taps are digital serializer/alignment nodes, not pin measurements.
"""
from migen import Cat, If, Memory, Signal
from litex.soc.interconnect.csr import CSRStatus, CSRStorage
from raw_capture_bist import RawCaptureBIST

DEPTH = 256
TRACE_FIELDS = [
    ("cycle", 32), ("native_cmd_valid", 1), ("native_cmd_ready", 1),
    ("native_cmd_we", 1), ("native_cmd_addr", 25),
    ("native_wvalid", 1), ("native_wready", 1), ("native_wmask", 72),
    ("native_write_lane6", 64), ("native_rvalid", 1), ("native_rready", 1),
    ("native_read_lane6", 64), ("native_read_lane8", 64),
]
for phase in range(4):
    TRACE_FIELDS += [(f"p{phase}_{name}", width) for name, width in
        [("address", 15), ("bank", 3), ("cs_n", 1), ("ras_n", 1),
         ("cas_n", 1), ("we_n", 1), ("cke", 1), ("odt", 1),
         ("wrdata_en", 1), ("rddata_en", 1), ("rddata_valid", 1)]]
TRACE_FIELDS += [(name, 64) for name in
    ("dfi_write_lane6", "phy_write_aligned_lane6", "phy_read_pre_lane6",
     "phy_read_post_lane6", "dfi_read_lane6")]
WIDTH = sum(width for _, width in TRACE_FIELDS)
TRACE_CSRS = [("trace_index", 1, "rw"), ("trace_data", (WIDTH+31)//32, "ro"),
              ("trace_count", 1, "ro"), ("trace_done", 1, "ro"),
              ("trace_epoch", 1, "ro"), ("trace_format", 1, "ro")]


class PHYTraceBIST(RawCaptureBIST):
    def __init__(self, port, modules=9):
        super().__init__(port, modules)
        self.trace_index = CSRStorage(8, name="trace_index")
        self.trace_data = CSRStatus(WIDTH, name="trace_data")
        self.trace_count = CSRStatus(9, name="trace_count")
        self.trace_done = CSRStatus(1, name="trace_done")
        self.trace_epoch = CSRStatus(32, name="trace_epoch")
        self.trace_format = CSRStatus(32, reset=0x54524331, name="trace_format")
        self._trace_native = port

    def attach_phy(self, phy):
        port, dfi = self._trace_native, phy.dfi
        assert len(port.wdata.data) == 576 and len(dfi.phases) == 4
        assert len(phy.trace_read_pre) == len(phy.trace_read_post) == len(phy.trace_write_post) == 8

        def native_lane(data, lane):
            return Cat(*[data[72*n+8*lane:72*n+8*lane+8] for n in range(8)])

        def dfi_lane(field):
            return Cat(*[getattr(dfi.phases[n//2], field)[72*(n%2)+48:72*(n%2)+56]
                         for n in range(8)])

        def tapped_lane(signals):
            return Cat(*[signals[bit][beat] for beat in range(8) for bit in range(8)])

        cycle = Signal(32)
        fields = [cycle, port.cmd.valid, port.cmd.ready, port.cmd.we, port.cmd.addr,
                  port.wdata.valid, port.wdata.ready, port.wdata.we,
                  native_lane(port.wdata.data, 6), port.rdata.valid, port.rdata.ready,
                  native_lane(port.rdata.data, 6), native_lane(port.rdata.data, 8)]
        for phase in dfi.phases:
            fields += [getattr(phase, name) for name in
                ("address", "bank", "cs_n", "ras_n", "cas_n", "we_n", "cke", "odt",
                 "wrdata_en", "rddata_en", "rddata_valid")]
        fields += [dfi_lane("wrdata"), tapped_lane(phy.trace_write_post),
                   tapped_lane(phy.trace_read_pre), tapped_lane(phy.trace_read_post),
                   dfi_lane("rddata")]
        assert [len(field) for field in fields] == [width for _, width in TRACE_FIELDS], [
            (name, width, len(field)) for (name, width), field in zip(TRACE_FIELDS, fields)
            if width != len(field)]
        memory = Memory(WIDTH, DEPTH, name="lane6_trace")
        write = memory.get_port(write_capable=True)
        read = memory.get_port()
        self.specials += memory, write, read
        active = Signal()
        start = self.start.re & self.start.storage[0]
        self.comb += [write.adr.eq(self.trace_count.status[:8]),
                      write.dat_w.eq(Cat(*fields)), write.we.eq(active & ~start),
                      read.adr.eq(self.trace_index.storage),
                      self.trace_data.status.eq(read.dat_r)]
        self.sync += If(start,
            active.eq(1), cycle.eq(0), self.trace_count.status.eq(0),
            self.trace_done.status.eq(0), self.trace_epoch.status.eq(self.trace_epoch.status+1),
        ).Elif(active,
            cycle.eq(cycle+1), self.trace_count.status.eq(self.trace_count.status+1),
            If(self.trace_count.status == DEPTH-1,
                active.eq(0), self.trace_done.status.eq(1)))
