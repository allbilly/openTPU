"""Spare-image calibration binding and bounded raw range operations.

Called only with an already opened, identity-checked transport. No programming,
calibration, ECC clearing, or automatic error recovery.
"""
import json
from pathlib import Path
import time

from opentpu.host import selfcal, regs as R
from opentpu.host.dual_pcie import require, digest
from opentpu.host.spare_c0172300 import REVIEWED_MANIFEST_SHA256
from spare_range_program import schedule, validate_result


def calibration_snapshot(transport):
    return dict(mailbox=selfcal.mailbox(transport.csr),
                phase={str(ch):c.r('phase_dqs_steps') for ch,c in transport.channels.items()},
                ready={str(ch):c.r('cal_ready') for ch,c in transport.channels.items()})


def check_calibration_receipt(path, profile, transport):
    receipt=json.loads(Path(path).read_text())
    require(receipt['status']=='SPARE_PCIE_CH0_CALIBRATION_RECORDED_MEMORY_UNQUALIFIED',
            'A successful full-image CH0 calibration receipt is required')
    binding=receipt['binding']
    require(binding['required_build_id']=='c0172300' and
            binding['required_bitstream_sha256']==profile.bitstream_sha256 and
            binding['full_package_manifest_sha256']==(REVIEWED_MANIFEST_SHA256 if profile.runtime_only
                                                      else profile.manifest_sha256),
            'Calibration receipt belongs to another package')
    if profile.runtime_only:
        require(binding.get('runtime_manifest_sha256')==profile.manifest_sha256,
                'Calibration receipt belongs to another runtime export')
    require(binding['firmware_id']=='c0172068' and
            binding['firmware_sha256']==digest(profile.package/'calibration/selfcal.bin'),
            'Calibration firmware differs')
    require(receipt['hardware_accessed'] and receipt['firmware_uploaded'] and
            receipt['calibration_requested'] and receipt['firmware_words_verified']==4096,
            'Calibration upload/execution evidence incomplete')
    require(not receipt['flash_written'] and not receipt['programming_performed'], 'Unexpected calibration actions')
    require(receipt['startup']['done'] and receipt['startup']['channels']['1'][0]=='ok' and
            receipt['calibration']['done'] and receipt['calibration']['channels']['0'][0]=='ok' and
            receipt['calibration']['channels']['1'][0]=='idle', 'Calibration states differ')
    for name, value in binding['matched_core_files'].items():
        require(Path(name).name==name and profile.core_file_digest(name)==value, 'Calibration core changed')
    require(set(binding['matched_core_files'])=={'otpu_litedram.v','csr.csv','sdram_init.py',
                                               'sdram_init_ch0.py','otpu_litedram_mem.init'},
            'Incomplete calibration core binding')
    actual=calibration_snapshot(transport)
    require(actual['mailbox']==receipt['mailbox'] and actual['mailbox'][:2]==[selfcal.MB_MAGIC_V,0xc0172068],
            'Live calibration mailbox changed')
    require(actual['phase']==receipt['phase_after'] and actual['ready']=={'0':1,'1':1},
            'Live phase/readiness differs from calibration receipt')
    transport.guard()
    return dict(receipt_sha256=digest(Path(path)), snapshot=actual)


def raw_range(transport, record, gap_seconds=.2):
    """Two complementary full-range passes with serialized 4 MiB chunks."""
    require(gap_seconds>=.2, 'Require at least 200 ms between chunks')
    status=transport.reg_read(R.R_STATUS)
    require(not status&(R.ST_RUN|R.ST_LOADING) and status&R.ST_WR_IDLE, 'Compute must be idle')
    transport.guard()
    transport.reg_write(R.R_SCRATCH,0)
    operations=schedule()
    counts={'writes':0,'reads':0,'bytes_written':{'0':0,'1':0},'bytes_read':{'0':0,'1':0}}
    for ordinal, op in enumerate(operations):
        transport.guard()
        channel=transport.channels[op['channel']];modules=8 if op['channel']==0 else 9
        epoch=channel.r('bist_raw_sequence')
        for name,value in [('base',op['base']//64),('length',op['length']),('seed',op['seed']),
                           ('mode',2 if op['write'] else 3),('start',1)]:
            channel.w('bist_'+name,value)
        deadline=time.monotonic()+10
        while not channel.r('bist_done'):
            if time.monotonic()>deadline:
                raise TimeoutError('Raw range chunk did not finish')
            time.sleep(.01)
        result=dict(beats=channel.r('bist_beats'),ticks=channel.r('bist_ticks'))
        capture=dict(sequence=channel.r('bist_raw_sequence'),valid=channel.r('bist_raw_valid'),
                     returns=channel.r('bist_raw_returns'))
        if not op['write']:
            result.update(errors=channel.r('bist_errors'),dq_mask=channel.r('bist_lane_bits'),
                          lane_errors=[channel.r(f'bist_lane{i}_errors') for i in range(modules)])
            capture.update(base=channel.r('bist_raw_base'),mode=channel.r('bist_raw_mode'),seed=channel.r('bist_raw_seed'),
                           actual=channel.r('bist_raw_data').to_bytes(modules*8,'little').hex())
        # Save raw evidence even if metadata validation itself fails.
        row=dict(ordinal=ordinal,operation=op,result=result,capture=capture,previous_epoch=epoch)
        record(row)
        decoded=validate_result(op,result,capture,epoch)
        require(decoded['errors']==0, f'Raw range error at chunk {ordinal}; preserve state')
        counts['writes' if op['write'] else 'reads']+=1
        counts['bytes_written' if op['write'] else 'bytes_read'][str(op['channel'])]+=64*op['length']
        time.sleep(gap_seconds)
    transport.guard()
    return counts
