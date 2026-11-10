#!/usr/bin/env python3
"""Build a CH0-only eight-lane firmware override for the reviewed spare image.

Creates isolated sources and a bounded (one word per phase) traffic check.
Does not access hardware. The firmware requires model review before upload.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
from fedora_prepare_litedram import ROOT, sha


def replace_once(text, old, new):
    assert text.count(old)==1,old
    return text.replace(old,new)


def load_module(path):
    spec=importlib.util.spec_from_file_location('spare_calibration_fw',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('package','out','rv-cc'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();package=a.package.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    bundle=json.loads((package/'bundle.json').read_text())
    assert bundle['variant']=='spare8' and bundle['build_id']=='c0172060'
    for line in (package/'SHA256SUMS').read_text().splitlines():
        checksum,name=line.split(None,1);path=(package/name.strip()).resolve()
        assert path.is_relative_to(package) and sha(path)==checksum
    source=out/'source';lib=source/'tools/litedram/selfcal_fw'
    shutil.copytree(package/'evidence/generation-source/tools/litedram/selfcal_fw',lib)
    host=source/'opentpu/host';host.mkdir(parents=True)
    shutil.copy2(package/'evidence/generation-source/opentpu/host/ddrcal.py',host/'ddrcal.py')
    config=out/'core';config.mkdir()
    shutil.copy2(package/'core/csr.csv',config/'csr.csv')
    shutil.copy2(package/'core/sdram_init_ch0.py',config/'sdram_init.py')
    f=lib/'fw.py';s=f.read_text()
    s=replace_once(s,'(4, 72, 9, 32, 8)','(4, 64, 8, 32, 8)')
    s=replace_once(s,'"the firmware is written for 4 phases, 72 bits (9 lanes), 32 taps, 8 bitslips"','"CH0 spare firmware requires 4 phases, 64 bits, 8 lanes"')
    s=replace_once(s,'chans = [ch for ch in (0, 1) if ddrcal.Chan(_Regs(regs), ch).name("ddrphy_dly_sel") in regs]','chans = [0]\n    assert phy["channels"] == [0] and "ddrphy_dly_sel" in regs')
    s=replace_once(s,'"#define PAT_WORDS 5"','"#define PAT_WORDS 4"')
    s=replace_once(s,'"#define BIST_MIB 64"','"#define BIST_BEATS 1"')
    s=replace_once(s,'32 * (4 - i)','32 * (3 - i)')
    s=replace_once(s,'for i in range(5)','for i in range(4)')
    s=replace_once(s,"per('sdram_dfii_pi{}_wrdata', 4 if ch == 0 else 5)","per('sdram_dfii_pi{}_wrdata', 4)")
    s=replace_once(s,"per('sdram_dfii_pi{}_rddata', 4 if ch == 0 else 5)","per('sdram_dfii_pi{}_rddata', 4)")
    f.write_text(s)
    f=lib/'cal.c';s=f.read_text()
    s=replace_once(s,'NM != 9','NM != 8')
    start=s.index('        /* bit b counts for DQ bit b % 72:')
    stop=s.index('\n    }\n}',start)
    s=s[:start]+'''        /* 128 DFI bits: combine the two transfers of 64 DQ bits. */
        err->w[0] |= x[0] | x[2];
        err->w[1] |= x[1] | x[3];
'''.rstrip()+s[stop:]
    s=replace_once(s,'BIST_MIB * (1u << 20) / 64','BIST_BEATS');f.write_text(s)
    f=lib/'main.c';s=f.read_text();assert 'selfcal_run(cfg & 2,' in s
    f.write_text(replace_once(s,'selfcal_run(cfg & 2,','selfcal_run(cfg & 1,'))
    fw=load_module(lib/'fw.py');fw.target(config,out/'target',fw_id=0xc0172068,cc=str(a.rv_cc.resolve()))
    fw.host(config,out/'host')
    assert (out/'target/selfcal.bin').stat().st_size<=16384
    manifest=dict(status='SPARE_CH0_FIRMWARE_BUILT_MODEL_REVIEW_PENDING',hardware_accessed=False,
        package_bitstream_sha256=bundle['bitstream_sha256'],package_manifest_sha256=sha(package/'manifest.json'),
        firmware_id='c0172068',channel_mask=1,modules=8,databits=64,dfi_words=4,bist_words_per_phase=1,
        csr_sha256=sha(config/'csr.csv'),config_sha256=sha(config/'sdram_init.py'),
        binary_sha256=sha(out/'target/selfcal.bin'),binary_bytes=(out/'target/selfcal.bin').stat().st_size,
        sources={str(f.relative_to(out)):sha(f) for f in source.rglob('*') if f.is_file() and '__pycache__' not in str(f)},
        builder_sha256=sha(Path(__file__)),limitation='CH0 only; a one-word phase check is not memory qualification')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))


if __name__=='__main__':main()
