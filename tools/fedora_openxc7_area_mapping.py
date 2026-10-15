#!/usr/bin/env python3
"""Area-oriented cut mapping of the unchanged full DDR800 pre-LUT checkpoint."""

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths
from collections import Counter
from datetime import datetime,timezone
import argparse,importlib.util,json,os
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from fedora_openxc7 import describe,digest
from fedora_openxc7_pcie_pipeline import FULL,recorded,unchanged
from fedora_check_jtag_image import synthesis_witness
PREPARER=Path(expand_paths('@YPCB@/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/full-abc-remap.py'))
PREPARER_SHA='279f93d05a09fbadf761eb78cc9801a82d8525b82903d726f78457ead988bd62'
TOP='otpu_fpga_top_openxc7_jtag'
SCRIPT='strash; dretime; if -a -F 2 -A 4'
def now():return datetime.now(timezone.utc).isoformat()
def write(p,d):
 q=p.with_suffix(p.suffix+'.area-tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(p)
def load_top(p):
 t=json.loads(p.read_text())['modules'][TOP]
 assert int(t.get('attributes',{}).get('blackbox','0'),2)==0
 assert not any(c['type'].startswith(('otpu_','VexRiscv')) for c in t['cells'].values())
 return t
def hard(t):
 kinds={'DSP48E1','RAMB18E1','RAMB36E1','BSCANE2','ISERDESE2','OSERDESE2','IDELAYE2','IDELAYCTRL','MMCME2_ADV','PLLE2_ADV','BUFG'}
 return {n:dict(type=c['type'],parameters=c.get('parameters',{})) for n,c in t['cells'].items() if c['type'] in kinds}
def clock_binding(t):
 scan=[(n,c) for n,c in t['cells'].items() if c['type']=='BSCANE2'];assert len(scan)==1
 name,c=scan[0];bit=c['connections']['TCK'];assert len(bit)==1
 buffers=[(n,c) for n,c in t['cells'].items() if c['type']=='BUFG' and c['connections']['I']==bit];assert len(buffers)==1
 name,buf=buffers[0];out=buf['connections']['O'];assert len(out)==1
 sinks=[]
 for n,c in t['cells'].items():
  for port,bits in c['connections'].items():
   if out[0] in bits and c['port_directions'][port]=='input':sinks.append(dict(cell=n,port=port,type=c['type'],parameters=c.get('parameters',{}),attributes=c.get('attributes',{}),bit_positions=[i for i,v in enumerate(bits) if v==out[0]]))
 sinks.sort(key=lambda v:(v['cell'],v['port']))
 assert len(sinks)==1748 and all(v['type'] in ('FDRE','FDSE') and v['port']=='C' for v in sinks)
 return dict(cell=name,properties=dict(type=buf['type'],parameters=buf.get('parameters',{}),attributes=buf.get('attributes',{})),input_driver=dict(cell=scan[0][0],port='TCK',type='BSCANE2',parameters=scan[0][1]['parameters']),output_sinks=sinks)
def run(out):
 assert digest(PREPARER)==PREPARER_SHA
 spec=importlib.util.spec_from_file_location('frozen_full_preparer',PREPARER);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 m=mod.prepare(out);p=out/'manifest.json';script=out/'synth.ys';lines=script.read_text().splitlines();hits=[i for i,s in enumerate(lines) if s.startswith('abc -exe ')];assert len(hits)==1
 index=hits[0];line=lines[index];assert ' -luts 2:2,3,6:5,10,20' in line
 lines[index]=line.replace(' -luts ', ' -script +strash,dretime,if,-a,-F,2,-A,4 -luts ',1);script.write_text('\n'.join(lines)+'\n')
 m['remap_inputs'][str(script)]=digest(script);m['remap_inputs'][str(Path(__file__).resolve())]=digest(__file__);m.update(status='RUNNING',stage='full-area-lut-mapping',logic_mapping='ABC_AREA_CUT_MAPPING',area_script=SCRIPT,helper_sha256=digest(__file__),remap_driver=describe(__file__),original_preparer=describe(PREPARER),controller_pid=os.getpid(),started_utc=now());m['artifacts']['synth.ys']=describe(script);write(p,m);unchanged(m['remap_inputs'])
 try:
  command=[m['tools']['yosys']['path'],'-Q','-T','-s',str(script)];write(out/'synth.command.json',command)
  env=dict(os.environ,OTPU_THREADS='all',LD_PRELOAD=m['tools']['cxx']['path'])
  with (out/'synth.log').open('w') as log:
   child=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT);stat=Path(f'/proc/{child.pid}/stat').read_text().split(') ',1)[1].split();m['yosys_process']=dict(pid=child.pid,start_ticks=int(stat[19]),argv=command);write(p,m);print('START full-area-mapping',child.pid,flush=True);code=child.wait()
  (out/'synth.exit').write_text(str(code)+'\n');m['native_yosys_exit']=code
  for n in ['synth.command.json','synth.log','synth.exit']:m['artifacts'][n]=describe(out/n)
  assert code==0,'Native Yosys exited '+str(code)
  unchanged(m['remap_inputs']);m['artifacts']['synth.json']=describe(out/'synth.json');m.update(stage='full-boundary-and-clock-comparison');write(p,m)
  baseline=load_top(mod.BASE/'synth.json');candidate=load_top(out/'synth.json')
  ports=lambda t:{n:dict(direction=v['direction'],width=len(v['bits'])) for n,v in t['ports'].items()}
  assert ports(baseline)==ports(candidate),'Board port scope changed'
  a,b=hard(baseline),hard(candidate);common=set(a)&set(b);assert all(a[n]==b[n] for n in common),'Named hardware properties changed'
  binding_a,binding_b=clock_binding(baseline),clock_binding(candidate);assert {k:v for k,v in binding_a.items() if k!='cell'}=={k:v for k,v in binding_b.items() if k!='cell'},'Actual BSCAN clock bindings changed'
  only_a=set(a)-set(b);only_b=set(b)-set(a)
  if binding_a['cell']!=binding_b['cell']:assert only_a=={binding_a['cell']} and only_b=={binding_b['cell']},'Hardware identity differences exceed the proven BUFG rename'
  else:assert not only_a and not only_b
  ca=Counter(c['type'] for c in baseline['cells'].values());cb=Counter(c['type'] for c in candidate['cells'].values())
  report=dict(status='FULL_AREA_MAPPING_BOUNDARY_HARDWARE_AND_CLOCK_BINDINGS_PASS_IMPLEMENTATION_NOT_RUN',parameters=FULL,baseline_counts=dict(ca),candidate_counts=dict(cb),baseline_raw_luts=sum(ca['LUT'+str(i)] for i in range(1,7)),candidate_raw_luts=sum(cb['LUT'+str(i)] for i in range(1,7)),board_ports_identical=True,hard_identity_bijection={binding_b['cell']:binding_a['cell']},clock_sink_count=len(binding_b['output_sinks']),baseline_clock_binding=binding_a,candidate_clock_binding=binding_b,source_or_dimensions_changed=False,numerical_timing='NOT_QUALIFIED',physical_hardware='NOT_RUN')
  write(out/'mapping-comparison.json',report);m['artifacts']['mapping-comparison.json']=describe(out/'mapping-comparison.json');m.update(status='SYNTHESIS_PASS_IMPLEMENTATION_NOT_RUN',stage='full-area-mapping-compared',finished_utc=now(),physical_hardware='NOT_RUN',bitstream='NOT_BUILT');write(p,m)
  witness=dict(configuration=FULL,synthesis_directory=str(out),adopted_synthesis_manifest=describe(p),mapped_checkpoint=m['artifacts']['synth.json']);counts=synthesis_witness(witness);unchanged(m['remap_inputs'])
  result=dict(status='FULL_AREA_MAPPING_PASS_IMPLEMENTATION_NOT_RUN',finished_utc=now(),manifest=describe(p),comparison=describe(out/'mapping-comparison.json'),mapped_checkpoint=witness['mapped_checkpoint'],parameters=FULL,mapped_counts=dict(counts),physical_hardware='NOT_RUN',timing='NOT_QUALIFIED');write(out/'area-mapping-result.json',result);print(result['status'],'raw_luts',report['candidate_raw_luts'],flush=True)
 except Exception as e:
  m.update(status='FULL_AREA_MAPPING_FAILED',error=repr(e),finished_utc=now());write(p,m);raise
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();run(args.out.resolve())
