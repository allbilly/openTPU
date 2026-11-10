#!/usr/bin/env python3
"""Bounded DMA probes or full payload readback through the spare OpenTPU image.

Requires the exact image's successful calibration receipt. No programming,
recalibration, error-counter clearing or automatic recovery is performed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import numpy as np
from opentpu.host import regs as R
from opentpu.host.board import Board
from opentpu.host.dual_pcie import CH_BYTES, require, digest
from opentpu.host.spare_pcie import SparePcieProfile, SpareChestnutTransport, SpareXdmaTransport
from spare_pcie_runtime import calibration_snapshot, check_calibration_receipt


def pattern(ch,base,count):
    require(count%8==0 and base%8==0,'Pattern requires aligned uint64 words')
    # Absolute word addresses make a shifted or aliased payload observable.
    words=np.arange(base//8,base//8+count//8,dtype=np.uint64)
    with np.errstate(over='ignore'):
        words=(words^np.uint64((ch+1)*0x13579bdf2468ace1))*np.uint64(0x9e3779b97f4a7c15)
        words^=words>>np.uint64(29)
    return words.astype('<u8').view(np.uint8)


def small_dma(t,record):
    offsets=(0,4096,1<<30,CH_BYTES-4096);resident={}
    # Both channels are written before either is checked, exposing cross aliases.
    for ch in (0,1):
        for off in offsets:
            data=pattern(ch,off,4096);t.mem_write(ch,off,data);resident[ch,off]=data.copy()
    for (ch,off),expected in resident.items():
        actual=t.mem_read(ch,off,len(expected));ok=bool(np.array_equal(actual,expected))
        record(dict(kind='physical-channel-sentinel',channel=ch,offset=off,bytes=len(expected),exact_match=ok))
        require(ok,'DMA sentinel mismatch; preserve state')
    # These partial host calls are merged by the transport into full DDR beats.
    # They verify host transfer semantics, not the hardware native masked path.
    for (ch,off),expected in resident.items():
        for rel,values in ((1,[0x19]),(63,[0x31,0xa7]),(4093,[0x55,0x12,0xe9])):
            update=np.asarray(values,np.uint8);t.mem_write(ch,off+rel,update)
            expected[rel:rel+len(update)]=update
        actual=t.mem_read(ch,off,len(expected));ok=bool(np.array_equal(actual,expected))
        record(dict(kind='host-partial-write-preservation',channel=ch,offset=off,bytes=len(expected),exact_match=ok))
        require(ok,'Host partial-write preservation mismatch')


def logical_boundaries(board,record):
    addresses=(0,0x7fffff80,0x80000000,0xffffff80);resident={}
    for address in addresses:
        data=pattern(0,address,128);board.write(address,data);resident[address]=data
    for address,expected in resident.items():
        actual=board.read(address,len(expected));ok=bool(np.array_equal(actual,expected))
        record(dict(kind='logical-interleave-boundary',address=address,bytes=len(expected),exact_match=ok))
        require(ok,'Logical boundary mismatch')


def native_masked(board,record):
    """QST emits byte-masked writes; compare changed and preserved bytes."""
    from opentpu import isa as I
    from opentpu.isasim import Machine
    from opentpu.host.board import device_config
    data,out,scale,program_at=0x1000,0x8000,0x9000,0x20000
    cfg=device_config(board.info(),DRAM_BYTES=1<<20)
    image=np.zeros(1<<20,np.uint8)
    image[data:data+512]=np.linspace(-3,3,128,dtype=np.float32).view(np.uint8)
    image[out:out+256]=np.arange(256,dtype=np.uint8)^0x6d
    image[scale:scale+128]=np.arange(128,dtype=np.uint8)^0x31
    program=[I.ld(data,0,128),I.qst(0,out,scale,1,1,128,256,2),I.halt()]
    expected=Machine(cfg,[program],[image.copy()]).run().slices[0]
    for address,count in ((data,512),(out,256),(scale,128),(program_at,4096)):
        board.write(address,image[address:address+count])
    board.load_program(program_at,np.asarray(I.assemble(program),np.uint32))
    stats=board.run(timeout=15)
    require(stats['instructions'][0]==expected.icount,'Native masked-write instruction count differs')
    for address,count in ((out,256),(scale,128)):
        actual=board.read(address,count);want=expected.dram[address:address+count]
        ok=bool(np.array_equal(actual,want))
        record(dict(kind='native-QST-byte-mask',address=address,bytes=count,exact_match=ok,
            expected_sha256=hashlib.sha256(want.tobytes()).hexdigest(),
            actual_sha256=hashlib.sha256(actual.tobytes()).hexdigest(),instructions=stats['instructions'][0]))
        require(ok,'Native byte-mask payload or preserved bytes differ')


def full_payload(t,record,chunk=1<<20):
    require(chunk%4096==0 and CH_BYTES%chunk==0,'Invalid full-range chunk')
    for write in (True,False):
        for ch in (0,1):
            bases=range(0,CH_BYTES,chunk) if write else reversed(range(0,CH_BYTES,chunk))
            for base in bases:
                data=pattern(ch,base,chunk)
                if write:t.mem_write(ch,base,data);actual=None;ok=True
                else:actual=t.mem_read(ch,base,chunk);ok=bool(np.array_equal(actual,data))
                record(dict(kind='full-native-dma-write' if write else 'full-native-dma-read',
                    channel=ch,offset=base,bytes=chunk,exact_match=ok,
                    expected_sha256=hashlib.sha256(data.tobytes()).hexdigest(),
                    actual_sha256=hashlib.sha256(actual.tobytes()).hexdigest() if actual is not None else None))
                require(ok,'Full payload mismatch; preserve state')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('package','calibration-receipt','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--transport',choices=('chestnut','xdma'),default='chestnut');p.add_argument('--dev',default='/dev/xdma0')
    p.add_argument('--stage',choices=('small','masked','full'),default='small');a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);t=board=None
    state=dict(status='CHECKING',hardware_accessed=False,programming_performed=False,flash_written=False,
        calibration_requested=False,stage=a.stage,operations=0,bytes_written={'0':0,'1':0},bytes_read={'0':0,'1':0},
        memory_initialized=False,source_sha256=digest(Path(__file__)))
    def save():
        state['utc']=datetime.now(timezone.utc).isoformat();p=a.out/'manifest.json.tmp';p.write_text(json.dumps(state,indent=2)+'\n');p.replace(a.out/'manifest.json')
    try:
        save();profile=SparePcieProfile(a.package)
        state.update(bitstream_sha256=profile.bitstream_sha256,package_manifest_sha256=profile.manifest_sha256)
        state.update(hardware_access_attempted=True,hardware_accessed=None);save()
        t=SpareChestnutTransport(profile) if a.transport=='chestnut' else SpareXdmaTransport(profile,a.dev)
        state['hardware_accessed']=True;state['calibration_binding']=check_calibration_receipt(a.calibration_receipt,profile,t)
        status=t.reg_read(R.R_STATUS);require(not status&(R.ST_RUN|R.ST_LOADING|R.ST_ERROR|R.ST_AXI_ERR) and status&R.ST_WR_IDLE,'Compute must be idle')
        board=Board(t,check=True,calibrate=False);state['identity']=board.info();state['ecc_before']=t.ecc_state()
        state['calibration_before']=calibration_snapshot(t);t.reg_write(R.R_SCRATCH,0)
        state['status']='SPARE_'+a.stage.upper()+'_DMA_RUNNING';save();started=time.monotonic()
        with (a.out/'operations.jsonl').open('w',buffering=1) as log:
            def record(row):
                row.update(ordinal=state['operations'],elapsed_s=time.monotonic()-started)
                log.write(json.dumps(row)+'\n');state['operations']+=1
                if row['kind'].startswith('full-native-dma'):
                    key='bytes_written' if row['kind'].endswith('write') else 'bytes_read'
                    state[key][str(row['channel'])]+=row['bytes']
                if not row['exact_match']:state['failure']=row
                save()
            if a.stage=='small':small_dma(t,record);logical_boundaries(board,record)
            elif a.stage=='masked':native_masked(board,record)
            else:full_payload(t,record)
        if a.stage=='full':
            require(state['bytes_written']==state['bytes_read']=={'0':CH_BYTES,'1':CH_BYTES},'Incomplete full DMA coverage')
        require(state['operations']=={'small':20,'masked':2,'full':4*(CH_BYTES//(1<<20))}[a.stage],'Incomplete operation schedule')
        t.guard();state['ecc_after']=t.ecc_state();state['calibration_after']=calibration_snapshot(t)
        require(state['calibration_before']==state['calibration_after'],'Calibration changed during DMA test')
        state['identity_after']=board.info();state['operations_sha256']=digest(a.out/'operations.jsonl')
        state.update(status='PASS_SPARE_'+a.stage.upper()+'_DMA_RECORDED_SYSTEM_QUALIFICATION_PENDING',
            scope='Small: host DMA/interleave and software-merged partial calls; masked: native QST byte masks; full: all native DMA payload bytes. Concurrent compute remains separate.',elapsed_s=time.monotonic()-started)
    except Exception as e:state.update(status='FAIL',error=repr(e));raise
    finally:
        try:
            try:
                if board is not None:board.close()
            finally:
                if t is not None:t.close()
        except Exception as e:state.update(status='FAIL',close_error=repr(e));raise
        finally:save()


if __name__=='__main__':main()
