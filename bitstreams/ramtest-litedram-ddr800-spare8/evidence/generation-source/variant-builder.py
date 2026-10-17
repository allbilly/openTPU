#!/usr/bin/env python3
"""Freeze, generate and implement one experimental RAM diagnostic variant.

No hardware access. Existing release builders/profiles are unchanged. The
variant-specific build copy retains timing/CRC gates; independent variant
and physical reviews are required before this becomes a usable package.
"""
import argparse
from datetime import datetime, timezone
import difflib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from fedora_prepare_litedram import ROOT, ENV, BASE, FILES, sha, retain_reference_cpu, phy_config, csr_registers
from ramtest_variant_profile import profile


def replace(text, before, after, count=1):
    if text.count(before)!=count:
        raise ValueError('Variant source anchor changed: '+before[:100])
    return text.replace(before,after)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',choices=['ddr667','spare8'],required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--vivado',default=str(Path.home()/'vivado/2026.1/Vivado/bin/vivado'))
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    spare=args.variant=='spare8';hz=100e6 if spare else 250e6/3
    khz,mts,buildid=(100000,800,'c0172060') if spare else (83333,667,'c0172050')
    state=dict(status='PREPARING',variant=args.variant,build_id=buildid,
        hardware_accessed=False,flash_written=False,physical_qualification=False)
    def save():
        state['updated_utc']=datetime.now(timezone.utc).isoformat()
        temp=out/'manifest.json.tmp';temp.write_text(json.dumps(state,indent=2)+'\n');temp.replace(out/'manifest.json')
    def run(command,label):
        command=list(map(str,command));(out/(label+'.command.json')).write_text(json.dumps(command,indent=2)+'\n')
        with (out/(label+'.log')).open('w') as log:
            rc=subprocess.run(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
        state[label+'_exit']=rc;save()
        if rc:raise RuntimeError(label+' failed; inspect '+label+'.log')
    try:
        save();source=out/'source';lib=source/'tools/litedram';lib.mkdir(parents=True)
        for p in (ROOT/'tools/litedram').glob('*.py'):shutil.copy2(p,lib/p.name)
        shutil.copytree(ROOT/'tools/litedram/selfcal_fw',lib/'selfcal_fw',ignore=shutil.ignore_patterns('__pycache__'))
        (source/'opentpu/host').mkdir(parents=True)
        shutil.copy2(ROOT/'opentpu/host/ddrcal.py',source/'opentpu/host/ddrcal.py')
        shutil.copy2(Path(__file__),source/'variant-builder.py')
        originals={p:p.read_text() for p in [lib/'gen_core.py',lib/'ld_test.py',lib/'selfcal_fw/fw.py',lib/'selfcal_fw/main.c']}
        g=originals[lib/'gen_core.py']
        g=replace(g,'from wl7ddrphy import WL7DDRPHY',
            'from raw_capture_bist import RawCaptureBIST as BIST\nfrom wl7ddrphy import WL7DDRPHY')
        if spare:
            g=replace(g,'from ecc_ports import NativePortsECC',
                'from spare_native import NativePortsNoECC\nfrom litedram.common import PHYPadsReducer\nfrom ecc_ports import NativePortsECC')
            g=replace(g,'                p = ClockDomainsRenamer(wc.domains)(WL7DDRPHY(\n                    platform.request("ddram", ch), groups=groups[ch], sys_clk_freq=f,',
                '''                physical = platform.request("ddram", ch)
                selected = physical
                if ch == 0:
                    selected = PHYPadsReducer(physical, [0,1,2,3,4,5,8,7])
                    for bit in range(48,56):
                        self.specials += Instance("IOBUF", i_I=0, i_T=1, io_IO=physical.dq[bit])
                    self.specials += Instance("IOBUFDS", i_I=0, i_T=1,
                        io_IO=physical.dqs_p[6], io_IOB=physical.dqs_n[6])
                p = ClockDomainsRenamer(wc.domains)(WL7DDRPHY(
                    selected, groups=groups[ch], sys_clk_freq=f,''')
            g=replace(g,'raw.data_width == DW + 64','raw.data_width == (DW if ch == 0 else DW + 64)')
            g=replace(g,'NativePortsECC(users, raws)', '(NativePortsNoECC if ch == 0 else NativePortsECC)(users, raws)')
            g=replace(g,'BIST(core.crossbar.get_port(), modules=9)', 'BIST(core.crossbar.get_port(), modules=8 if ch == 0 else 9)')
            # Firmware remains the nine-lane implementation and is restricted
            # to CH1. CH0 uses a separately generated eight-lane host profile.
            g=replace(g,'ps = soc.ddrphy.settings','ps = soc.ddrphy1.settings')
            g=replace(g,'    info, init_py = sdram_init(soc, a.sys_mhz, a.phy, groups)',
                '''    info, init_py = sdram_init(soc, a.sys_mhz, a.phy, groups)
    ch0_info = dict(info, databits=64, dfi_databits=128, modules=8, channels=[0])
    ch0_init = get_sdram_phy_py_header(soc.ddrphy.settings, soc.sdram.controller.settings.timing)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sdram_init_ch0.py").write_text(ch0_init + "\\nphy = " + json.dumps(ch0_info, indent=1) + "\\n")''')
            fw=originals[lib/'selfcal_fw/fw.py']
            fw=replace(fw,"per('sdram_dfii_pi{}_wrdata', 5)","per('sdram_dfii_pi{}_wrdata', 4 if ch == 0 else 5)")
            fw=replace(fw,"per('sdram_dfii_pi{}_rddata', 5)","per('sdram_dfii_pi{}_rddata', 4 if ch == 0 else 5)")
            (lib/'selfcal_fw/fw.py').write_text(fw)
            (lib/'selfcal_fw/main.c').write_text(replace(originals[lib/'selfcal_fw/main.c'],'selfcal_run(cfg & 3,','selfcal_run(cfg & 2,'))
            # Eight-lane BIST has no ninth-byte parity-like random extension.
            ld=replace(originals[lib/'ld_test.py'],
                'rnd = Cat(rot[:64], rot[:gw - 64] ^ rot[64 - (gw - 64):64])',
                'rnd = rot[:64] if gw == 64 else Cat(rot[:64], rot[:gw - 64] ^ rot[64 - (gw - 64):64])')
            (lib/'ld_test.py').write_text(ld)
        else:
            # The phase search covers +/- half a DDR clock: 1.5 ns at DDR667.
            g=replace(g,'wc.constraints(hier=True)', 'wc.constraints(ns=1.5, hier=True)')
        (lib/'gen_core.py').write_text(g)
        for path,before in originals.items():
            after=path.read_text()
            if after!=before:
                (out/(path.name+'.patch')).write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+path.name,tofile='b/'+path.name)))
        toolchain=out/'toolchain';toolchain.mkdir()
        image='7a9b5cf5977e9e09126101c2c2c9b642b3517c3d7894668c36b1d7c550a573b7'
        for tool in ('gcc','objcopy','objdump'):
            prefix=['/usr/bin/podman','run','--rm','--network=none','--userns=keep-id','--security-opt','label=disable','--read-only','--tmpfs','/tmp:rw','-v',f'{ROOT}:{ROOT}:ro','-v',f'{out}:{out}:rw','--workdir']
            suffix=['--entrypoint',f'/opt/et/bin/riscv64-unknown-elf-{tool}',image]
            if tool=='gcc':suffix+=['-L'+str(ENV/'rv32-runtime')]
            p=toolchain/f'riscv64-elf-{tool}'
            p.write_text('#!/bin/sh\nexec '+shlex.join(prefix)+' "$PWD" '+shlex.join(suffix)+' "$@"\n');p.chmod(0o755)
        env=dict(os.environ,RV_CC=str(toolchain/'riscv64-elf-gcc'),PYTHONHASHSEED='0')
        state['frozen_sources']={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
        state['status']='GENERATION_RUNNING';save()
        cmd=[ENV/'venv/bin/python',lib/'gen_core.py','--sys-mhz',str(hz/1e6),'--phy','wl','--selfcal','--fw-id',buildid,'--out',out/'core']
        if spare:cmd+=['--groups0',','.join(['0']*8)]
        run(cmd,'generation')
        core=out/'core';cpu=retain_reference_cpu(core)
        shutil.copy2(core/'gateware/otpu_litedram_mem.init',core/'otpu_litedram_mem.init')
        phy=phy_config(core/'sdram_init.py')
        if not spare:
            original=csr_registers(ROOT/'opentpu/host/litedram/csr.csv');actual=csr_registers(core/'csr.csv')
            assert all(actual.get(k)==v for k,v in original.items()),'Existing DDR667 CSR moved'
        info=dict(status='EXPERIMENTAL_VARIANT_GENERATED_IMPLEMENTATION_PENDING',variant=args.variant,
            part='xc7k480tffg1156-2',parameters=dict(CORE_KHZ=khz,DDR_MTS=mts),sys_hz=hz,
            actual_ddr_mts=hz*8/1e6,phy=phy,physical_databits=[64,72] if spare else [72,72],
            physical_user_channels=[0,1],ecc_channels=[1] if spare else [0,1],
            automatic_calibration_channels=[1] if spare else [0,1],calibration_cpu=cpu,
            files={k:dict(name=n,sha256=sha(core/n),bytes=(core/n).stat().st_size) for k,n in FILES.items()})
        if spare:info.update(ch0_physical_lanes=[0,1,2,3,4,5,8,7],ch0_init_sha256=sha(core/'sdram_init_ch0.py'),
            partial_write_path='Serialized full-word read/merge/write; raw BIST must be idle during native traffic')
        for name in ('variant-profile.json','openxc7-profile.json'):(core/name).write_text(json.dumps(info,indent=2)+'\n')
        profile(core)
        # Freeze and adapt the established implementation driver. Its original
        # validators stay unchanged; this copy imports the strict variant gate.
        builder=(ROOT/'tools/fedora_build_ramtest_litedram.py').read_text();before=builder
        builder=replace(builder,'from fedora_prepare_litedram import profile, FILES',
            'sys.path.insert(0, '+repr(str(ROOT/'tools'))+')\nfrom ramtest_variant_profile import profile, FILES')
        builder=replace(builder,'ROOT = Path(__file__).resolve().parents[1]', 'ROOT = Path('+repr(str(ROOT))+')')
        if not spare:
            builder=replace(builder,'dict(CORE_KHZ=100000, DDR_MTS=800)',f'dict(CORE_KHZ={khz}, DDR_MTS={mts})')
            builder=replace(builder,'.DDR_MTS(800)',f'.DDR_MTS({mts})')
            builder=replace(builder,'ddr_mts=800, sys_hz=100000000',f'ddr_mts={mts}, sys_hz={hz!r}')
            builder=replace(builder,'PERIOD $core]-10.0','PERIOD $core]-12.0')
            # Update the hardware identity frequency, not just its manifest.
            builder=replace(builder,"shutil.copy2(BOARD / 'litedram_status.sv', snapshot / 'litedram_status.sv')",
                "(snapshot / 'litedram_status.sv').write_text((BOARD / 'litedram_status.sv').read_text().replace('<= 100000;', '<= 83333;'))")
        else:
            builder=replace(builder,'ISERDESE2 144 OSERDESE2 214 IDELAYE2 144',
                'ISERDESE2 136 OSERDESE2 205 IDELAYE2 136')
            builder=replace(builder,"ecc_path='Normal 512-bit native ECC user port A on each physical channel; port B idle'",
                "ecc_path='CH0 512-bit non-ECC with partial-write RMW; CH1 ECC; port B idle'")
        # Both profile files are frozen for independent review.
        builder=replace(builder,"list(FILES.values()) + ['openxc7-profile.json']",
            "list(FILES.values()) + ['openxc7-profile.json', 'variant-profile.json']" + (" + ['sdram_init_ch0.py']" if spare else ''))
        (source/'implementation-builder.py').write_text(builder)
        (out/'implementation-builder.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),builder.splitlines(True),fromfile='a/builder.py',tofile='b/builder.py')))
        state.update(status='IMPLEMENTATION_RUNNING',core_profile_sha256=sha(core/'variant-profile.json'),
            implementation_builder_sha256=sha(source/'implementation-builder.py'));save()
        run([sys.executable,source/'implementation-builder.py','--core',core,'--traffic-build',
            ROOT/'build/fedora-vivado/ram-only-mig-ddr800-address-20261016-v5','--build-id',buildid,
            '--capture-first-read','--capture-model-review',ROOT/'bitstreams/ramtest-litedram-ddr800-runtime-pattern/evidence/source/read-capture-model.json',
            '--runtime-pattern-reset-fix','--pattern-restart-model-review',ROOT/'bitstreams/ramtest-litedram-ddr800-runtime-pattern/evidence/source/pattern-restart-model.json',
            '--vivado',args.vivado,'--out',out/'implementation'],'implementation')
        for name,digest in state['frozen_sources'].items():assert sha(source/name)==digest,name
        state.update(status='EXPERIMENTAL_BITSTREAM_BUILT_INDEPENDENT_VARIANT_REVIEW_AND_PHYSICAL_PENDING',
            bitstream_sha256=sha(out/'implementation/ramtest.bit'))
    except Exception as error:
        state.update(status='FAIL',error=repr(error));raise
    finally:save()


if __name__=='__main__':main()
