"""Serialized non-ECC native adapter for the experimental eight-lane CH0.

Every physical write supplies all 64 bytes; masked writes read/merge/write.
Both user ports share one arbiter so their partial writes cannot interleave.
The raw BIST is a separate client and must be idle during native traffic.
This is experimental logic requiring protocol and physical qualification.
"""
from migen import Array, Cat, FSM, If, Module, Mux, NextState, NextValue, Signal
from litex.soc.interconnect.csr import AutoCSR, CSR, CSRStatus


class NativePortsNoECC(Module, AutoCSR):
    def __init__(self, users, raws):
        assert len(users) == len(raws) == 2
        assert all(p.data_width == 512 for p in users+raws)
        self.enable = CSRStatus(1, reset=0)
        self.clear = CSR()
        self.sec_errors = CSRStatus(32)
        self.ded_errors = CSRStatus(32)
        raw = raws[0]
        self.comb += [raws[1].cmd.valid.eq(0), raws[1].wdata.valid.eq(0),
                      raws[1].rdata.ready.eq(1)]
        owner, turn, sent = Signal(), Signal(), Signal()
        address, write, payload, mask, result = Signal(25), Signal(), Signal(512), Signal(64), Signal(512)
        request = Array(p.cmd.valid for p in users)
        chosen = Signal()
        self.comb += chosen.eq(Mux(request[turn], turn, ~turn))
        cmd_addr = Array(p.cmd.addr for p in users)
        cmd_we = Array(p.cmd.we for p in users)
        wd_valid = Array(p.wdata.valid for p in users)
        wd_data = Array(p.wdata.data for p in users)
        wd_mask = Array(p.wdata.we for p in users)
        rd_ready = Array(p.rdata.ready for p in users)
        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
        for i, user in enumerate(users):
            self.comb += [user.cmd.ready.eq(fsm.ongoing("IDLE") & (chosen == i)),
                          user.wdata.ready.eq(fsm.ongoing("WRITE_DATA") & (owner == i)),
                          user.rdata.valid.eq(fsm.ongoing("RESPONSE") & (owner == i)),
                          user.rdata.data.eq(result)]
        self.comb += [raw.cmd.addr.eq(address), raw.wdata.data.eq(payload),
                      raw.wdata.we.eq((1 << 64)-1)]
        fsm.act("IDLE", If(request[chosen],
            NextValue(owner, chosen), NextValue(turn, ~chosen), NextValue(sent, 0),
            NextValue(address, cmd_addr[chosen]), NextValue(write, cmd_we[chosen]),
            If(cmd_we[chosen], NextState("WRITE_DATA")).Else(NextState("READ_COMMAND"))))
        fsm.act("WRITE_DATA", If(wd_valid[owner],
            NextValue(payload, wd_data[owner]), NextValue(mask, wd_mask[owner]),
            If(wd_mask[owner] == 0, NextState("IDLE"))
            .Elif(wd_mask[owner] == (1 << 64)-1, NextState("WRITE_COMMAND"))
            .Else(NextState("READ_COMMAND"))))
        fsm.act("READ_COMMAND", raw.cmd.valid.eq(1), raw.cmd.we.eq(0),
                If(raw.cmd.ready, NextState("READ_DATA")))
        merged = Cat(*[Mux(mask[i], payload[8*i:8*i+8], raw.rdata.data[8*i:8*i+8])
                       for i in range(64)])
        fsm.act("READ_DATA", raw.rdata.ready.eq(1), If(raw.rdata.valid,
            If(write, NextValue(payload, merged), NextState("WRITE_COMMAND"))
            .Else(NextValue(result, raw.rdata.data), NextState("RESPONSE"))))
        fsm.act("RESPONSE", If(rd_ready[owner], NextState("IDLE")))
        # Keep data valid before/with the command, and independently remember
        # command acceptance. The crossbar requests write data afterward.
        fsm.act("WRITE_COMMAND", raw.cmd.valid.eq(1), raw.cmd.we.eq(1),
                raw.wdata.valid.eq(~sent), If(raw.wdata.ready, NextValue(sent, 1)),
                If(raw.cmd.ready,
                    If(sent | raw.wdata.ready, NextState("IDLE")).Else(NextState("WRITE_SEND"))))
        fsm.act("WRITE_SEND", raw.wdata.valid.eq(1), If(raw.wdata.ready, NextState("IDLE")))
