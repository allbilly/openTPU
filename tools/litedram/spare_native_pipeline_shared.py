"""Experimental pipelined two-port non-ECC adapter for the spare-lane CH0.

Each native user retains its own raw crossbar port. Read commands are queued
and may have multiple responses in flight; a credit reserves response storage
from user-command acceptance through user-data consumption. The crossbar's
read return cannot be stalled, so raw rdata.ready is always asserted.

Writes remain globally exclusive. A pending write blocks new read acceptance,
drains both read pipelines, then performs one full write or read/merge/write.
The raw write command and payload may be accepted independently. No other
native command can split a masked write's read/modify/write interval. Raw BIST
must remain idle during native traffic, as for the serialized reference.

The response output preserves the board bridge contract: one selected valid
per cycle, and its data broadcast on both user buses. Per-port response FIFOs
are internal. The original independent-output adapter is preserved for the
regression counterexample; existing frozen bitstreams are unchanged.
This implementation requires protocol, timing and physical qualification.
"""
from migen import Array, Cat, FSM, If, Module, Mux, NextState, NextValue, Signal
from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import AutoCSR, CSR, CSRStatus


class NativePortsPipelinedSharedNoECC(Module, AutoCSR):
    def __init__(self, users, raws, read_depth=32):
        assert len(users) == len(raws) == 2
        assert read_depth >= 2 and read_depth & (read_depth - 1) == 0
        assert all(p.data_width == 512 for p in users + raws)
        assert len({p.address_width for p in users + raws}) == 1
        self.enable = CSRStatus(1, reset=0)
        self.clear = CSR()
        self.sec_errors = CSRStatus(32)
        self.ded_errors = CSRStatus(32)

        fsm = FSM(reset_state="READS")
        self.submodules += fsm
        normal = fsm.ongoing("READS")
        write_requests = Array(p.cmd.valid & p.cmd.we for p in users)
        write_pending = Signal()
        self.comb += write_pending.eq(write_requests[0] | write_requests[1])
        owner, turn, chosen, sent = Signal(), Signal(), Signal(), Signal()
        self.comb += chosen.eq(Mux(write_requests[turn], turn, ~turn))
        address = Signal(users[0].address_width)
        payload, mask = Signal(512), Signal(64)
        outstanding = [Signal(max=read_depth + 1) for _ in users]
        self.read_outstanding = outstanding
        self.protocol_error = Signal()
        drained = Signal()
        self.comb += drained.eq((outstanding[0] == 0) & (outstanding[1] == 0))

        response_fifos = []
        for i, (user, raw) in enumerate(zip(users, raws)):
            commands = stream.SyncFIFO([("address", user.address_width)], 2, buffered=True)
            responses = stream.SyncFIFO([("data", 512)], read_depth, buffered=True)
            setattr(self.submodules, "read_commands" + str(i), commands)
            setattr(self.submodules, "read_responses" + str(i), responses)
            response_fifos.append(responses)
            accept_read = normal & ~write_pending & (outstanding[i] < read_depth)
            write_selected = normal & drained & write_pending & (chosen == i)
            exclusive = owner == i
            read_command = fsm.ongoing("RMW_READ_COMMAND") & exclusive
            write_command = fsm.ongoing("WRITE_COMMAND") & exclusive
            write_data = (fsm.ongoing("WRITE_COMMAND") & ~sent |
                          fsm.ongoing("WRITE_SEND")) & exclusive
            self.comb += [
                commands.sink.valid.eq(user.cmd.valid & ~user.cmd.we & accept_read),
                commands.sink.address.eq(user.cmd.addr),
                user.cmd.ready.eq(Mux(user.cmd.we, write_selected,
                                      accept_read & commands.sink.ready)),
                # Once accepted, a queued read stays valid even if another
                # user requests a write while the raw command is stalled.
                raw.cmd.valid.eq((normal & commands.source.valid) | read_command | write_command),
                raw.cmd.addr.eq(Mux(normal, commands.source.address, address)),
                raw.cmd.we.eq(write_command),
                raw.cmd.last.eq(1),
                commands.source.ready.eq(normal & raw.cmd.ready),
                raw.rdata.ready.eq(1),
                responses.sink.valid.eq(normal & raw.rdata.valid),
                responses.sink.data.eq(raw.rdata.data),
                user.wdata.ready.eq(fsm.ongoing("WRITE_DATA") & exclusive),
                raw.wdata.valid.eq(write_data),
                raw.wdata.data.eq(payload),
                raw.wdata.we.eq((1 << 64) - 1),
            ]
            issue = user.cmd.valid & user.cmd.ready & ~user.cmd.we
            consume = user.rdata.valid & user.rdata.ready
            self.sync += [
                If(issue & ~consume, outstanding[i].eq(outstanding[i] + 1))
                .Elif(consume & ~issue, outstanding[i].eq(outstanding[i] - 1)),
                If(normal & raw.rdata.valid &
                   ((outstanding[i] == 0) | ~responses.sink.ready),
                   self.protocol_error.eq(1)),
            ]

        # otpu_mem_ch consumes user 0's data for BOTH response tags and
        # accepts at most one return per cycle. Independent buffered outputs
        # violate that contract even with correct data in each private FIFO.
        # Arbitrate FIFO heads, then broadcast the selected payload. The
        # selected owner stays fixed under backpressure. Raw returns still
        # enter their own FIFOs without backpressure, using reserved credits.
        response_turn = Signal()
        response_owner = Signal()
        response_held = Signal()
        held_owner = Signal()
        response_valid = Array(f.source.valid for f in response_fifos)
        response_data = Array(f.source.data for f in response_fifos)
        response_ready = Array(u.rdata.ready for u in users)
        preferred = Mux(response_valid[response_turn], response_turn, ~response_turn)
        self.comb += response_owner.eq(Mux(response_held, held_owner, preferred))
        for i, (user, responses) in enumerate(zip(users, response_fifos)):
            self.comb += [
                user.rdata.valid.eq(response_valid[response_owner] & (response_owner == i)),
                user.rdata.data.eq(response_data[response_owner]),
                responses.source.ready.eq((response_owner == i) & user.rdata.ready),
            ]
        self.sync += If(response_valid[response_owner],
            If(response_ready[response_owner],
                response_held.eq(0), response_turn.eq(~response_owner)
            ).Else(response_held.eq(1), held_owner.eq(response_owner)))

        command_addresses = Array(p.cmd.addr for p in users)
        wd_valid = Array(p.wdata.valid for p in users)
        wd_payload = Array(p.wdata.data for p in users)
        wd_mask = Array(p.wdata.we for p in users)
        raw_command_ready = Array(p.cmd.ready for p in raws)
        raw_write_ready = Array(p.wdata.ready for p in raws)
        raw_read_valid = Array(p.rdata.valid for p in raws)
        raw_read_data = Array(p.rdata.data for p in raws)
        merged = Cat(*[Mux(mask[b], payload[8*b:8*b+8],
                           raw_read_data[owner][8*b:8*b+8]) for b in range(64)])

        fsm.act("READS", If(write_pending & drained,
            NextValue(owner, chosen), NextValue(turn, ~chosen), NextValue(sent, 0),
            NextValue(address, command_addresses[chosen]), NextState("WRITE_DATA")))
        fsm.act("WRITE_DATA", If(wd_valid[owner],
            NextValue(payload, wd_payload[owner]), NextValue(mask, wd_mask[owner]),
            If(wd_mask[owner] == 0, NextState("READS"))
            .Elif(wd_mask[owner] == (1 << 64) - 1, NextState("WRITE_COMMAND"))
            .Else(NextState("RMW_READ_COMMAND"))))
        fsm.act("RMW_READ_COMMAND", If(raw_command_ready[owner], NextState("RMW_READ_DATA")))
        fsm.act("RMW_READ_DATA", If(raw_read_valid[owner],
            NextValue(payload, merged), NextState("WRITE_COMMAND")))
        fsm.act("WRITE_COMMAND",
            If(raw_write_ready[owner], NextValue(sent, 1)),
            If(raw_command_ready[owner],
                If(sent | raw_write_ready[owner], NextState("READS"))
                .Else(NextState("WRITE_SEND"))))
        fsm.act("WRITE_SEND", If(raw_write_ready[owner], NextState("READS")))
