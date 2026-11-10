#!/usr/bin/env python3
"""Build an isolated opt-in clock-feedback correction atop the verified DSP backend."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe,digest


TRACE=r'''
                // The full design's write-MMCM feedback passes through BUFG.
                // Resolve only a single nonconstant clock-buffer input; never
                // assume a source for an ambiguous mux or cyclic network.
                pool<IdString> feedback_seen;
                for (int depth = 0; fix_feedback && clkfb && clkfb->driver.cell != ci && depth < 16; ++depth) {
                    if (!feedback_seen.insert(clkfb->name).second) {
                        clkfb = nullptr;
                        break;
                    }
                    const CellInfo *buffer = clkfb->driver.cell;
                    if (!buffer || !buffer->type.in(id_BUFGCTRL, id_BUFHCE_BUFHCE, id_BUFIO_BUFIO, id_BUFMRCE)) {
                        clkfb = nullptr;
                        break;
                    }
                    const NetInfo *candidate = nullptr;
                    bool ambiguous = false;
                    for (IdString input : {id_I, id_I0, id_I1}) {
                        const NetInfo *net = buffer->getPort(input);
                        if (!net || net->constant_value != IdString())
                            continue;
                        if (candidate && candidate != net) {
                            ambiguous = true;
                            break;
                        }
                        candidate = net;
                    }
                    clkfb = ambiguous ? nullptr : candidate;
                }
'''

AUDIT=r'''
    if (ctx->args.options.count("clock-constraint-audit")) {
        std::string path = ctx->args.options["clock-constraint-audit"].as<std::string>();
        if (std::ifstream(path).good())
            log_error("Clock constraint audit output already exists.\n");
        std::ofstream stream(path);
        if (!stream)
            log_error("Cannot create clock constraint audit output.\n");
        stream << "net\tperiod_min_ps\tperiod_max_ps\thigh_min_ps\thigh_max_ps\tlow_min_ps\tlow_max_ps\n";
        for (const auto &entry : ctx->nets) {
            const auto *net = entry.second.get();
            if (!net->clkconstr)
                continue;
            const auto &clock = *net->clkconstr;
            stream << net->name.str(ctx) << '\t' << clock.period.minDelay() << '\t' << clock.period.maxDelay()
                   << '\t' << clock.high.minDelay() << '\t' << clock.high.maxDelay()
                   << '\t' << clock.low.minDelay() << '\t' << clock.low.maxDelay() << '\n';
        }
        stream.flush();
        if (!stream)
            log_error("Clock constraint audit write failed.\n");
    }
'''


def build(previous,out,workers):
    before=json.loads(previous.read_text())
    if describe(before['binary']['path'])!=before['binary']or describe(before['source_inventory']['path'])!=before['source_inventory']:
        raise ValueError('Verified DSP backend or source inventory changed')
    original=Path(before['source']);expected=json.loads(Path(before['source_inventory']['path']).read_text())
    out.mkdir(parents=True,exist_ok=False)
    info={'status':'RUNNING','created_utc':datetime.now(timezone.utc).isoformat(),'scope':'OPT_IN_BUFFERED_FEEDBACK_AND_FEEDBACK_PERIOD_ONLY_PHASE_AND_WHOLE_TIMING_PENDING',
          'previous':describe(previous),'previous_binary':before['binary'],'helper':describe(__file__),'workers':workers,
          'physical_hardware':'NOT_RUN','numerical_timing':'NOT_QUALIFIED'}
    def save(**fields):info.update(fields);(out/'manifest.json').write_text(json.dumps(info,indent=2)+'\n')
    def run(stage,argv):
        (out/(stage+'.command.json')).write_text(json.dumps(argv,indent=2)+'\n')
        with(out/(stage+'.log')).open('w')as log:r=subprocess.run(argv,cwd=out,stdout=log,stderr=subprocess.STDOUT)
        (out/(stage+'.exit')).write_text(str(r.returncode)+'\n');return stage,r.returncode
    try:
        save(stage='copy-and-patch');source=out/'source';shutil.copytree(original,source)
        if any(digest(source/n)!=sha for n,sha in expected.items()):raise ValueError('Copied source changed')
        target=source/'himbaechel/uarch/xilinx/pack_clocking.cc';text=target.read_text()
        anchor='void XilinxPacker::generate_constraints()\n{'
        if text.count(anchor)!=1:raise ValueError('Unexpected constraint function')
        text=text.replace(anchor,anchor+r'''
    const auto &options = ctx->args.options;
    std::string mode = options.count("clock-feedback-vivado") ? options["clock-feedback-vivado"].as<std::string>() : "off";
    if (mode != "on" && mode != "off")
        log_error("clock-feedback-vivado must be on or off.\n");
    bool fix_feedback = mode == "on";
    if (fix_feedback && ctx->args.device != "xc7k480tffg1156-2")
        log_error("Clock-feedback correction is qualified only for xc7k480tffg1156-2.\n");
''')
        anchor='                const NetInfo *clkfb = ci->getPort(id_CLKFBIN);'
        if text.count(anchor)!=1:raise ValueError('Unexpected feedback source')
        text=text.replace(anchor,anchor+TRACE)
        old='''                // CLKFBOUT (and CLKFBOUTB on the MMCM) run at the VCO rate.
                set_constraint(ci, ctx->id("CLKFBOUT"), simple_clk_contraint(vco_period));
                if (ci->type == id_MMCME2_ADV_MMCME2_ADV)
                    set_constraint(ci, ctx->id("CLKFBOUTB"), simple_clk_contraint(vco_period));'''
        new='''                // Vivado's feedback waveform includes the feedback counter,
                // not the VCO frequency. The off path preserves prior behavior.
                double feedback_period = vco_period;
                if (fix_feedback)
                    feedback_period *= float_or_default(ci,
                            ci->type == id_MMCME2_ADV_MMCME2_ADV ? id_CLKFBOUT_MULT_F : id_CLKFBOUT_MULT, 1);
                set_constraint(ci, ctx->id("CLKFBOUT"), simple_clk_contraint(feedback_period));
                if (ci->type == id_MMCME2_ADV_MMCME2_ADV)
                    set_constraint(ci, ctx->id("CLKFBOUTB"), simple_clk_contraint(feedback_period));'''
        if text.count(old)!=1:raise ValueError('Unexpected feedback-clock constraint')
        text=text.replace(old,new)
        anchor='\n}\nNEXTPNR_NAMESPACE_END'
        if text.count(anchor)!=1:raise ValueError('Unexpected clock source end')
        text=text.replace(anchor,'\n'+AUDIT+anchor)
        text='#include <fstream>\n'+text;target.write_text(text)
        cc=source/'himbaechel/uarch/xilinx/xilinx.cc';text=cc.read_text();anchor='    return specific;'
        if text.count(anchor)!=1:raise ValueError('Unexpected options declaration')
        text=text.replace(anchor,'''    specific.add_options()("clock-feedback-vivado", po::value<std::string>(), "experimental buffered-feedback constraint correction: on or off (default off)");
    specific.add_options()("clock-constraint-audit", po::value<std::string>(), "generated clock constraint audit output");
'''+anchor);cc.write_text(text)
        updated={str(p.relative_to(source)):digest(p)for p in source.rglob('*')if p.is_file()}
        delta=[n for n in updated if expected.get(n)!=updated[n]]
        if set(delta)!={'himbaechel/uarch/xilinx/pack_clocking.cc','himbaechel/uarch/xilinx/xilinx.cc'}:
            raise ValueError('Unexpected source delta')
        (out/'source.input.json').write_text(json.dumps(updated,indent=2)+'\n')
        objects=out/'input-objects';objects.mkdir();link=[];jobs=[];reused=[]
        templates={Path(j['source']).name:j['argv']for j in before['compile_plan']}
        for i,arg in enumerate(before['link_argv']):
            if arg.endswith(('.o','.a'))and Path(arg).is_file():
                dest=objects/(str(i).zfill(3)+'-'+Path(arg).name)
                name=next((n for n in ['pack_clocking.cc','xilinx.cc']if Path(arg).name.endswith(n+'.o')),None)
                if name:
                    argv=[v.replace(str(original),str(source))for v in templates[name]]
                    for flag,value in [('-MF',str(dest)+'.d'),('-o',str(dest)),('-c',str(source/'himbaechel/uarch/xilinx'/name))]:argv[argv.index(flag)+1]=value
                    jobs.append({'source':str(source/'himbaechel/uarch/xilinx'/name),'output':str(dest),'argv':argv})
                else:
                    shutil.copy2(arg,dest)
                    if digest(arg)!=digest(dest):raise ValueError('Copied object changed')
                    reused.append({'original':describe(arg),'copied':describe(dest)})
                link.append(str(dest))
            elif arg.startswith('-Wl,--dependency-file='):link.append('-Wl,--dependency-file='+str(out/'link.d'))
            else:link.append(arg)
        if len(jobs)!=2:raise ValueError('Expected two changed translation units')
        link[link.index('-o')+1]=str(out/'nextpnr-himbaechel')
        save(stage='compile',source=str(source),source_inventory=describe(out/'source.input.json'),source_delta=delta,
             compile_plan=jobs,reused_inputs=reused,link_argv=link,retained_corrections=before.get('retained_corrections',[]))
        with ThreadPoolExecutor(max_workers=workers)as pool:results=list(pool.map(lambda item:run('compile-'+str(item[0]),item[1]['argv']),enumerate(jobs)))
        save(compile_results=dict(results))
        if any(code for _,code in results):raise RuntimeError('Clock-feedback compilation failed')
        save(stage='link');_,code=run('link',link)
        if code:raise RuntimeError('Clock-feedback link failed')
        _,code=run('version',[str(out/'nextpnr-himbaechel'),'--version'])
        if code:raise RuntimeError('Clock-feedback backend startup failed')
        shutil.copy2(__file__,out/'helper.py')
        save(status='CLOCK_FEEDBACK_BACKEND_BUILD_PASS_NATIVE_CLOCK_CHECK_PENDING',binary=describe(out/'nextpnr-himbaechel'),
             completed_utc=datetime.now(timezone.utc).isoformat(),rebuilt_translation_units=[describe(j['output'])for j in jobs])
        print(info['status'],flush=True)
    except Exception as exc:save(status='FAIL',error=repr(exc));raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['previous','out']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--workers',type=int,default=8);args=parser.parse_args();build(args.previous.resolve(),args.out.resolve(),args.workers)


if __name__=='__main__':main()
