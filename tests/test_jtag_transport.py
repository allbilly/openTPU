"""Host packet/range/ECC behavior; no physical-hardware claims."""
import numpy as np
import pytest

from opentpu.host.jtag import JtagCommandError, JtagTransport, MAGIC, IDCODE


class Mailbox:
    def __init__(self):
        self.ir=0
        self.response=MAGIC << 536
        self.memory={}
        self.registers={}
        self.commands=[]
        self.closed=False
        self.error=0
        self.stale=False

    def reset(self):
        pass

    def close(self):
        self.closed=True

    def scan(self,frame,bits=640,ir=False):
        if ir:
            self.ir=frame
            return 0
        if self.ir==9:
            return IDCODE
        if not frame:
            return self.response
        assert frame >> 572 == MAGIC
        op=(frame >> 548) & 255
        addr=(frame >> 512) & 0xffffffff
        seq=(frame >> 556) & 65535
        data=frame & ((1 << 512)-1)
        self.commands.append((op,addr,data))
        result=0
        if op==1:
            result=self.registers.get(addr,0)
        elif op==2:
            self.registers[addr]=data
        elif op==3:
            result=self.memory.get(addr,int.from_bytes(bytes(range(64)),'little'))
        elif op==4:
            assert addr % 64==0
            self.memory[addr]=data
        if not self.stale:
            self.response=MAGIC << 536 | seq << 520 | self.error << 512 | result
        return 0


def test_register_windows_and_64bit_channel_boundaries():
    m=Mailbox(); t=JtagTransport(link=m)
    t.reg_write(0x10044,0x12345678)
    assert t.reg_read(0x10044)==0x12345678
    payload=np.arange(128,dtype=np.uint8)
    t.mem_write(1,(1 << 31)-128,payload)
    np.testing.assert_array_equal(t.mem_read(1,(1 << 31)-128,128),payload)
    assert {a for op,a,_ in m.commands if op==4}=={0xffffff80,0xffffffc0}
    t.close(); assert m.closed


def test_unaligned_updates_preserve_both_edge_beats():
    m=Mailbox(); t=JtagTransport(link=m)
    t.mem_write(0,60,np.arange(12,dtype=np.uint8)+100)
    expected=np.tile(np.arange(64,dtype=np.uint8),2)
    expected[60:72]=np.arange(12,dtype=np.uint8)+100
    np.testing.assert_array_equal(t.mem_read(0,0,128),expected)
    assert all(a % 64==0 for op,a,_ in m.commands if op in (3,4))


def test_out_buffer_and_invalid_ranges_submit_no_commands():
    m=Mailbox(); t=JtagTransport(link=m)
    buf=np.empty(9,np.uint8)
    assert t.mem_read(0,3,9,buf) is buf
    np.testing.assert_array_equal(buf,np.arange(3,12,dtype=np.uint8))
    n=len(m.commands)
    for fn in [lambda:t.mem_read(2,0,1),lambda:t.mem_read(1,(1 << 31)-1,2),
               lambda:t.reg_read(0x30000),lambda:t.reg_write(3,1),
               lambda:t.mem_read(0,0,10,np.empty(9,np.uint8))]:
        with pytest.raises(ValueError): fn()
    assert len(m.commands)==n


@pytest.mark.parametrize('error,stale',[(2,False),(0,True)])
def test_error_or_stale_sequence_poison_connection(error,stale):
    m=Mailbox(); t=JtagTransport(link=m,timeout=0)
    m.error=error; m.stale=stale
    with pytest.raises((IOError,TimeoutError)) as caught: t.reg_read(0)
    if error:
        assert isinstance(caught.value,JtagCommandError)
        assert (caught.value.opcode,caught.value.address,caught.value.status)==(1,0,error)
    n=len(m.commands)
    with pytest.raises(IOError): t.reg_write(0,1)
    assert len(m.commands)==n


def test_board_scrub_marks_initialized_only_after_full_bist_success(monkeypatch):
    from opentpu.host.board import Board
    from opentpu.host import regs as R
    m=Mailbox(); t=JtagTransport(link=m)
    b=Board(t,check=False,lock=False)
    calls=[]
    def failed():
        raise IOError('channel 1 failed')
    monkeypatch.setattr(t,'scrub',failed)
    with pytest.raises(IOError): b.scrub()
    assert m.registers.get(R.R_SCRATCH,0)!=R.DRAM_INIT
    monkeypatch.setattr(t,'scrub',lambda:calls.append('4 GiB checked'))
    assert b.scrub() is True
    assert m.registers[R.R_SCRATCH]==R.DRAM_INIT
    assert b.scrub() is False
    assert calls==['4 GiB checked']


def test_reconnect_waits_for_fresh_response_across_sequence_wrap():
    class DelayedMailbox(Mailbox):
        def __init__(self):
            super().__init__()
            self.response=MAGIC << 536 | 65535 << 520 | 0xdeadbeef
            self.pending=None
            self.polls=0

        def scan(self,frame,bits=640,ir=False):
            if ir or self.ir==9:
                return super().scan(frame,bits,ir)
            if frame:
                old=self.response
                super().scan(frame,bits,ir)
                self.pending=self.response
                self.response=old
            elif self.pending is not None:
                self.polls+=1
                if self.polls==2:
                    self.response=self.pending
            return self.response

    m=DelayedMailbox();m.registers[0x20]=0x12345678
    t=JtagTransport(link=m)
    assert t.reg_read(0x20)==0x12345678
    assert m.polls==2
    assert t._seq==1
    t.close()


def test_wrong_calibration_profile_stops_before_writes():
    from opentpu.host import memcal, regs as R
    m=Mailbox(); t=JtagTransport(link=m)
    m.registers.update({R.R_REGMAP:3, R.R_CAPS:R.CAP_HOSTCAL | R.CAP_DDR,
                        R.R_DDR_MTS:800, R.R_STATUS:0})
    with pytest.raises(memcal.ddrcal.CalError,match='profile is DDR3-1066'):
        memcal.ensure(t,force=True)
    assert all(op==1 for op,_,_ in m.commands)
    t.close()


def test_matching_generated_calibration_profile_is_selected(tmp_path):
    from opentpu.host import memcal, regs as R
    (tmp_path/'sdram_init.py').write_text('phy = {"sys_hz": 100000000.0}\n')
    (tmp_path/'csr.csv').write_text('csr_register,cal_ready,0x2000,1,rw\n')
    m=Mailbox(); t=JtagTransport(link=m,calibration_data=tmp_path)
    m.registers.update({R.R_CAPS:R.CAP_HOSTCAL | R.CAP_DDR, R.R_DDR_MTS:800})
    c=memcal.csr(t)
    assert c.regs['cal_ready']==(0x2000,1)
    c.w('cal_ready',1)
    assert m.registers[R.R_MEMCAL+0x2000]==1
    t.close()


class XadcMailbox(Mailbox):
    """UG480's pipelined XADC DRP alongside the retained USER2 mailbox."""
    def __init__(self, raw=0xa000):
        super().__init__()
        self.raw = raw
        self.idle = 0
        self.pending_read = False
        self.adc_ops = []
        self.fail_adc = False

    def shift(self, bits, tms, tdi):
        assert self.ir == 0x37 and tms == 0 and tdi == 0
        self.idle += bits
        return 0

    def scan(self, frame, bits=640, ir=False):
        if not ir and self.ir == 0x37:
            assert bits == 32
            if self.fail_adc:
                raise IOError('DRP link failure')
            self.adc_ops.append(frame)
            if frame == 0x04000000:
                self.pending_read = True
                self.idle = 0
                return 0xdead  # prior pipeline value
            assert frame == 0 and self.pending_read and self.idle >= 10
            self.pending_read = False
            return 0xabcd0000 | self.raw
        return super().scan(frame, bits, ir)


def test_xadc_pipeline_restores_user2_and_retains_mailbox_sequence():
    from opentpu.host.board import Board
    from opentpu.host import regs as R
    m = XadcMailbox()
    m.response = MAGIC << 536 | 42 << 520
    m.registers.update({R.R_REGMAP: 3, R.R_VERSION: 128 << 16 | 4 << 8 | 8,
                        R.R_CAPS: R.CAP_DDR, R.R_DDR_MTS: 800})
    t = JtagTransport(link=m)
    assert t.read_die_temperature() == 41.83
    assert m.adc_ops == [0x04000000, 0] and m.idle >= 10
    assert m.ir == 3 and t._seq == 42 and not m.commands
    t.reg_write(0x20, 0x12345678)
    assert t._seq == 43 and t.reg_read(0x20) == 0x12345678
    # The board API reports the real sideband sensor even when fabric CAPS
    # correctly says there is no temperature register.
    info = Board(t, check=False, lock=False).info()
    assert info['temp_c'] == 41.83 and info['caps']['temp'] is False
    t.close()


@pytest.mark.parametrize('raw', [0, 0xffff])
def test_unavailable_xadc_sample_is_none_and_restores_user2(raw):
    m = XadcMailbox(raw)
    t = JtagTransport(link=m)
    assert t.read_die_temperature() is None
    assert m.ir == 3 and not t._failed
    t.reg_write(0x20, 1)
    assert t.reg_read(0x20) == 1
    t.close()


def test_xadc_io_failure_restores_user2_and_poisons_link():
    m = XadcMailbox()
    t = JtagTransport(link=m)
    m.fail_adc = True
    with pytest.raises(IOError, match='DRP link failure'):
        t.read_die_temperature()
    assert m.ir == 3 and t._failed and not m.commands
    with pytest.raises(IOError, match='needs recovery'):
        t.reg_write(0x20, 1)
    assert not m.commands
    t.close()
