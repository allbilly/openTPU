#!/usr/bin/env python3
"""Generate an isolated DDR800 recovery core: four virtual ports on physical CH1.

Preserves both PHYs, CSR ABI, ECC and full compute dimensions. Virtual channel
c, beat m maps to physical CH1 beat (m << 1) | c. Each virtual channel has a
1 GiB limit; usable logical capacity is 2 GiB. Never opens hardware or flash.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from fedora_prepare_litedram import ENV, qualify, profile, FILES

PORT_BLOCK = '''            # Recovery: unused physical CH0 keeps its ECC CSR ABI; all four
            # exposed user ports use physical CH1's crossbar and shared decoder.
            users, raws = [], []
            if ch == 0:
                for u in ("", "b"):
                    raw = core.crossbar.get_port()
                    user = LiteDRAMNativePort("both", AW, DW)
                    users.append(user)
                    raws.append(raw)
                    self.comb += [user.cmd.valid.eq(0), user.cmd.we.eq(0),
                                  user.cmd.addr.eq(0), user.cmd.last.eq(1),
                                  user.wdata.valid.eq(0), user.wdata.data.eq(0),
                                  user.wdata.we.eq(0), user.rdata.ready.eq(1)]
            else:
                for virtual in (0, 1):
                    for u in ("", "b"):
                        raw = core.crossbar.get_port()
                        assert raw.address_width == AW and raw.data_width == DW + 64
                        user = LiteDRAMNativePort("both", AW, DW)
                        users.append(user)
                        raws.append(raw)
                        upads = platform.request(f"c{virtual}{u}")
                        self.comb += [
                            user.cmd.valid.eq(upads.cmd_valid),
                            upads.cmd_ready.eq(user.cmd.ready),
                            user.cmd.we.eq(upads.cmd_we),
                            # 24 virtual beat bits + channel LSB = 25 physical bits.
                            # Host/compiled program must obey the 2 GiB capacity.
                            user.cmd.addr.eq(Cat(Constant(virtual, 1), upads.cmd_addr[:24])),
                            user.cmd.last.eq(1),
                            user.wdata.valid.eq(upads.wdata_valid),
                            upads.wdata_ready.eq(user.wdata.ready),
                            user.wdata.data.eq(upads.wdata_data),
                            user.wdata.we.eq(upads.wdata_we),
                            upads.rdata_valid.eq(user.rdata.valid),
                            user.rdata.ready.eq(upads.rdata_ready),
                            upads.rdata_data.eq(user.rdata.data),
                        ]
                        if u == "":
                            if virtual == 0:
                                ready0 = upads.ready
                            else:
                                ready1 = upads.ready
            setattr(self, "ecc" + sfx, NativePortsECC(users, raws))
            cal = Cal()
            setattr(self, "cal" + sfx, cal)
            if ch == 1:
                # These are virtual ready flags. cal_ready CSR still reports
                # the real physical CH0 separately and must not be called a pass.
                self.comb += [ready0.eq(cal.ready.storage), ready1.eq(cal.ready.storage)]
            if bist:
                setattr(self, "bist" + sfx, BIST(core.crossbar.get_port(), modules=9))
'''


def describe(path):
    p=Path(path)
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):
            h.update(block)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--python',type=Path,default=ENV/'venv/bin/python',
                    help='Python in the pinned Migen/LiteX/LiteDRAM environment')
    ap.add_argument('--rv-cc',type=Path,default=ENV/'toolchain/riscv64-elf-gcc',
                    help='RV32I/ILP32-capable GCC; its objcopy and objdump must be beside it')
    args=ap.parse_args()
    out=args.out.resolve()
    if out.exists():
        ap.error('Choose a fresh output directory')
    out.mkdir(parents=True)
    src=out/'generator'
    shutil.copytree(ROOT/'tools/litedram',src,
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    gen=src/'gen_core.py'
    text=gen.read_text()
    start=text.index('            # the user ports (the even banks\'')
    end=text.index('\n        # CSRs:',start)
    gen.write_text(text[:start]+PORT_BLOCK+text[end:])
    # The firmware helper resolves ddrcal relative to the repository in its
    # normal location. An isolated generator must carry that exact parser.
    firmware=src/'selfcal_fw/fw.py'
    text=firmware.read_text()
    original='HERE.parents[2] / "opentpu" / "host" / "ddrcal.py"'
    if text.count(original)!=1:
        raise ValueError('Unexpected firmware parser import')
    firmware.write_text(text.replace(original,'HERE / "ddrcal.py"'))
    shutil.copy2(ROOT/'opentpu/host/ddrcal.py',src/'selfcal_fw/ddrcal.py')
    cpu=src/'calcpu.py'
    text=cpu.read_text()
    old='CSRField("channels", size=2, reset=0b11,'
    if text.count(old)!=1:
        raise ValueError('Unexpected calibration CPU configuration')
    cpu.write_text(text.replace(old,'CSRField("channels", size=2, reset=0b10,'))
    # Exercise the actual shared decoder/encoders against four stock frontends.
    test=src/'ecc_ports_check.py'
    text=test.read_text()
    text=text.replace('range(2)','range(4)').replace('pend = [[], []]',
                      'pend = [[], [], [], []]').replace(
                      'rnd.choice([None, None, 0, 1])','rnd.choice([None, None, 0, 1, 2, 3])')
    test.write_text(text)
    record=dict(status='PREPARED',started_utc=datetime.now(timezone.utc).isoformat(),
                hardware_accessed=False,flash_written=False,
                physical_user_channels=[1],virtual_channels=2,
                virtual_channel_bytes=1<<30,usable_logical_bytes=1<<31,
                mapping='physical CH1 beat = (virtual beat << 1) | virtual channel',
                capacity_limit='Host and compiled programs must reject logical addresses >= 2 GiB; upper virtual beat bit is not storage.',
                calibration_mask=2,compute='Unchanged full MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2, 100 MHz',
                generator_sources=[describe(p) for p in sorted(src.rglob('*')) if p.is_file()])
    def save():
        p=out/'manifest.json.tmp';p.write_text(json.dumps(record,indent=2)+'\n');p.replace(out/'manifest.json')
    def run(name,cmd,env=None):
        record['status']=name.upper()+'_RUNNING';save()
        (out/(name+'.command.json')).write_text(json.dumps(cmd,indent=2)+'\n')
        with (out/(name+'.log')).open('w') as log:
            p=subprocess.Popen(cmd,cwd=src,env=env,stdout=log,stderr=subprocess.STDOUT)
            record['child_pid']=p.pid;save();code=p.wait()
        record.pop('child_pid',None);record[name+'_exit']=code
        (out/(name+'.exit')).write_text(str(code)+'\n');save()
        if code:
            raise RuntimeError(name+' failed; see '+str(out/(name+'.log')))
    try:
        # Resolving a venv's Python symlink selects the system interpreter and
        # loses its pinned packages. Preserve both executable paths as supplied.
        python=str(args.python.expanduser().absolute())
        run('four-port-ecc',[python,str(test),'--cycles','1500','--seed','1'])
        core=out/'core'
        env=dict(os.environ,RV_CC=str(args.rv_cc.expanduser().absolute()),PYTHONHASHSEED='0')
        run('generate',[python,str(gen),'--sys-mhz','100','--phy','wl','--selfcal',
                        '--fw-id','c1010800','--out',str(core)],env)
        qualify(core)
        checked=profile(core)
        m=core/'openxc7-profile.json';p=json.loads(m.read_text())
        p.update(physical_user_channels=[1],virtual_channel_bytes=1<<30,
                 usable_logical_bytes=1<<31,user_address_mapping=record['mapping'],
                 calibration_mask=2,
                 note='CH1-only recovery: both physical PHY/CSR blocks remain; CH0 has no user traffic. Four virtual user ports share physical CH1 ECC/crossbar. Virtual ready flags report CH1 calibration. No physical CH0 pass is implied.')
        m.write_text(json.dumps(p,indent=2)+'\n')
        record.update(status='CH1_RECOVERY_CORE_AND_FOUR_PORT_ECC_PASS_IMPLEMENTATION_PENDING',
                      core=str(core),profile=describe(m),
                      outputs={k:describe(core/n) for k,n in FILES.items()})
        return 0
    except Exception as error:
        record.update(status='FAIL',error=repr(error));print(record['error'],flush=True)
        return 1
    finally:
        record['finished_utc']=datetime.now(timezone.utc).isoformat();save()


if __name__=='__main__':
    raise SystemExit(main())
