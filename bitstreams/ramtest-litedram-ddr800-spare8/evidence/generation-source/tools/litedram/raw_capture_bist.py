"""BIST with a passive, held copy of the first returned raw DDR word.

The inherited command/data generator is unchanged. Capture is observational:
no output feeds a native-port valid, ready, address, write data or mask signal.
CSR metadata identifies the start epoch and configured raw test. A single-word
read can be correlated with the inherited error mask without another transfer.
"""
from migen import If,Signal
from litex.soc.interconnect.csr import CSRStatus
from ld_test import BIST


class RawCaptureBIST(BIST):
    def __init__(self,port,modules=9):
        super().__init__(port,modules)
        width,aw=len(port.rdata.data),len(port.cmd.addr)
        self.raw_data=CSRStatus(width,name='raw_data')
        self.raw_valid=CSRStatus(1,name='raw_valid')
        self.raw_sequence=CSRStatus(32,name='raw_sequence')
        self.raw_base=CSRStatus(aw,name='raw_base')
        self.raw_mode=CSRStatus(2,name='raw_mode')
        self.raw_seed=CSRStatus(64,name='raw_seed')
        self.raw_returns=CSRStatus(aw+1,name='raw_returns')
        armed=Signal()
        start=self.start.re & self.start.storage[0]
        returned=port.rdata.valid & port.rdata.ready
        self.sync += If(start,
            self.raw_valid.status.eq(0),self.raw_data.status.eq(0),
            self.raw_sequence.status.eq(self.raw_sequence.status+1),
            self.raw_base.status.eq(self.base.storage),self.raw_mode.status.eq(self.mode.storage),
            self.raw_seed.status.eq(self.seed.storage),self.raw_returns.status.eq(0),
            armed.eq(self.mode.storage[0]),
        ).Elif(armed & ~self.done.status & returned,
            self.raw_returns.status.eq(self.raw_returns.status+1),
            If(~self.raw_valid.status,
                self.raw_data.status.eq(port.rdata.data),self.raw_valid.status.eq(1)),
        )
