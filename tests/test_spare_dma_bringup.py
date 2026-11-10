"""Boundary, masked-byte preservation and complete payload comparison checks."""
import numpy as np
import pytest
import json
import sys
from types import SimpleNamespace

from tools import run_spare_pcie_dma as H


class Memory:
    def __init__(self,alias=False,fault=False):self.mem={};self.alias=alias;self.fault=fault
    def key(self,ch,off):return (0 if self.alias else ch,off)
    def mem_write(self,ch,off,data):
        if (off%4096 or len(data)!=4096) and len(data)<4096:
            base=off//4096*4096;self.mem[self.key(ch,base)][off-base:off-base+len(data)]=data
        else:self.mem[self.key(ch,off)]=data.copy()
    def mem_read(self,ch,off,count):
        result=self.mem[self.key(ch,off)].copy()
        if self.fault:result[-1]^=1
        return result


@pytest.mark.parametrize('kind',['clean','alias','payload'])
def test_small_dma_detects_channel_alias_and_bad_payload(kind):
    mem=Memory(alias=kind=='alias',fault=kind=='payload');rows=[]
    if kind=='clean':
        H.small_dma(mem,rows.append)
        assert len(rows)==16 and all(r['exact_match'] for r in rows)
        assert {r['channel'] for r in rows}=={0,1}
        assert max(r['offset']+r['bytes'] for r in rows)==1<<31
    else:
        with pytest.raises(ValueError):H.small_dma(mem,rows.append)
        assert rows[-1]['exact_match'] is False


def test_full_payload_writes_all_then_compares_every_byte(monkeypatch):
    monkeypatch.setattr(H,'CH_BYTES',4*4096);mem=Memory();rows=[]
    H.full_payload(mem,rows.append,chunk=4096)
    assert len(rows)==16 and all(r['kind'].endswith('write') for r in rows[:8])
    assert [r['offset'] for r in rows[8:12]]==[12288,8192,4096,0]
    assert all(r['expected_sha256']==r['actual_sha256'] for r in rows[8:])
    mem.fault=True;rows=[]
    with pytest.raises(ValueError):H.full_payload(mem,rows.append,chunk=4096)
    assert len(rows)==9 and not rows[-1]['exact_match']


@pytest.mark.parametrize('fault',[False,True])
def test_native_masked_reference_and_preserved_bytes(fault):
    from opentpu import isa as I
    from opentpu.host.board import device_config
    from opentpu.isasim import Machine
    class Board:
        def __init__(self):self.dram=np.zeros(1<<20,np.uint8)
        def info(self):return dict(D=128,MCOLS=4,LANES=8,act_rows=4,caps={})
        def write(self,off,data):self.dram[off:off+len(data)]=data
        def load_program(self,off,words):self.prog=[I.Instr.decode(words[i:i+8]) for i in range(0,len(words),8)]
        def run(self,timeout):
            result=Machine(device_config(self.info(),DRAM_BYTES=1<<20),[self.prog],[self.dram]).run().slices[0]
            self.dram=result.dram
            if fault:self.dram[0x8001]^=1
            return dict(instructions=[result.icount])
        def read(self,off,count):return self.dram[off:off+count].copy()
    board=Board();rows=[]
    if fault:
        with pytest.raises(ValueError):H.native_masked(board,rows.append)
        assert not rows[-1]['exact_match']
    else:
        H.native_masked(board,rows.append)
        assert len(rows)==2 and all(r['exact_match'] for r in rows)
        assert np.array_equal(board.dram[0x8001:0x8100:2],(np.arange(256,dtype=np.uint8)^0x6d)[1::2])
        assert np.array_equal(board.dram[0x9004:0x9080],(np.arange(128,dtype=np.uint8)^0x31)[4:])


@pytest.mark.parametrize('cleanup_fail',[False,True])
def test_complete_small_run_and_transport_close_after_board_failure(tmp_path,monkeypatch,cleanup_fail):
    mem=Memory();mem.closed=False
    mem.reg_read=lambda off:H.R.ST_WR_IDLE
    mem.reg_write=lambda *a:None
    mem.guard=lambda:None
    mem.ecc_state=lambda:{}
    mem.close=lambda:setattr(mem,'closed',True)
    class Board:
        def __init__(self,*a,**kw):self.values={}
        def info(self):return dict(temp_c=49.)
        def write(self,off,data):self.values[off]=data.copy()
        def read(self,off,count):return self.values[off]
        def close(self):
            if cleanup_fail:raise RuntimeError('emulated board cleanup failure')
    monkeypatch.setattr(H,'Board',Board)
    monkeypatch.setattr(H,'SparePcieProfile',lambda *a:SimpleNamespace(bitstream_sha256='fixture',manifest_sha256='fixture'))
    monkeypatch.setattr(H,'SpareChestnutTransport',lambda *a:mem)
    monkeypatch.setattr(H,'check_calibration_receipt',lambda *a:{})
    monkeypatch.setattr(H,'calibration_snapshot',lambda *a:{})
    out=tmp_path/'out';monkeypatch.setattr(sys,'argv',['dma','--package',str(tmp_path),
        '--calibration-receipt',str(tmp_path/'calibration.json'),'--out',str(out)])
    if cleanup_fail:
        with pytest.raises(RuntimeError):H.main()
    else:H.main()
    result=json.loads((out/'manifest.json').read_text())
    assert result['operations']==20 and mem.closed
    assert (result['status']=='FAIL')==cleanup_fail
