#!/usr/bin/env python3
"""Build isolated, validated same-slice placement for mailbox synchronizers."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe, digest


PACK_CPP = r'''
void constrain_mailbox_synchronizers(Context *ctx)
{
    if (!ctx->args.options.count("mailbox-sync-contract")) {
        if (ctx->args.options.count("mailbox-sync-audit"))
            log_error("Mailbox synchronizer audit requires a contract.\n");
        return;
    }
    std::ifstream stream(ctx->args.options["mailbox-sync-contract"].as<std::string>());
    if (!stream)
        log_error("Cannot read mailbox synchronizer contract.\n");
    std::string input((std::istreambuf_iterator<char>(stream)), std::istreambuf_iterator<char>()), error;
    auto contract = json11::Json::parse(input, error);
    if (!error.empty() || !contract.is_object() || contract["schema"].number_value() != 1 ||
        contract["part"].string_value() != "xc7k480tffg1156-2" || ctx->args.device != "xc7k480tffg1156-2" ||
        !contract["synchronizers"].is_array() || contract["synchronizers"].array_items().empty())
        log_error("Malformed or incompatible mailbox synchronizer contract.\n");
    pool<IdString> used;
    for (const auto &chain : contract["synchronizers"].array_items()) {
        std::string name = chain["name"].string_value(), clock = chain["clock"].string_value();
        if (name.empty() || clock.empty() || chain["stages"].array_items().size() != 3 ||
            chain["placement_required"].string_value() != "ALL_THREE_PRIMARY_FFS_IN_ONE_SLICE" ||
            chain["timing_required"].string_value() != "NORMAL_RECEIVER_CLOCK_SETUP_HOLD_BETWEEN_STAGES")
            log_error("Invalid mailbox synchronizer chain declaration.\n");
        std::vector<CellInfo *> stages;
        for (const auto &declared : chain["stages"].array_items()) {
            auto found = ctx->cells.find(ctx->id(declared["cell"].string_value()));
            if (found == ctx->cells.end() || found->second->type != id_SLICE_FFX)
                log_error("Mailbox synchronizer stage is missing or not a packed FF.\n");
            auto *cell = found->second.get();
            auto *q = cell->getPort(id_Q), *d = cell->getPort(id_D), *ck = cell->getPort(id_CK);
            auto *ce = cell->getPort(id_CE), *sr = cell->getPort(id_SR);
            if (!q || q->name.str(ctx) != declared["q_net"].string_value() || !d || !ck || ck->name.str(ctx) != clock ||
                int_or_default(cell->params, id_IS_C_INVERTED, 0) != 0 || !cell->attrs.count(id_X_FFSYNC) ||
                !ce || ce->constant_value != id_VCC || !sr || sr->constant_value != id_GND)
                log_error("Mailbox synchronizer clock, edge or control set differs.\n");
            auto annotation = q->attrs.find(ctx->id("ASYNC_REG"));
            if (annotation == q->attrs.end() || !annotation->second.is_string || annotation->second.as_string() != "TRUE")
                log_error("Mailbox synchronizer ASYNC_REG annotation missing.\n");
            if (cell->cluster != ClusterId() || !cell->constr_children.empty() || cell->constr_abs_z ||
                cell->attrs.count(id_BEL) || cell->attrs.count(id_LOC) || !used.insert(cell->name).second)
                log_error("Mailbox synchronizer has conflicting placement or duplicate stage.\n");
            if (!stages.empty() && d != stages.back()->getPort(id_Q))
                log_error("Mailbox synchronizer stages are not directly connected.\n");
            stages.push_back(cell);
        }
        for (size_t i = 0; i < 2; ++i) {
            auto *net = stages[i]->getPort(id_Q);
            unsigned consumers = 0;
            for (const auto &user : net->users) {
                ++consumers;
                if (user.cell != stages[i+1] || user.port != id_D)
                    log_error("An early mailbox synchronizer stage feeds other logic.\n");
            }
            if (consumers != 1)
                log_error("An early mailbox synchronizer stage feeds other logic.\n");
        }
        auto *source = stages.front()->getPort(id_D)->driver.cell;
        if (!source || source->type != id_SLICE_FFX || !source->getPort(id_CK) ||
            source->getPort(id_CK) == stages.front()->getPort(id_CK))
            log_error("Mailbox synchronizer has no opposite-clock registered source.\n");
        auto *root = stages.front();
        root->cluster = root->name;
        root->attrs[ctx->id("X_MAILBOX_SYNC_ROOT")] = Property(1);
        for (size_t i = 0; i < stages.size(); ++i) {
            auto *cell = stages[i];
            cell->attrs[ctx->id("ASYNC_REG")] = std::string("TRUE");
            cell->attrs[ctx->id("X_MAILBOX_SYNC_CHAIN")] = name;
            if (i) {
                cell->cluster = root->name;
                cell->constr_x = cell->constr_y = 0;
                cell->constr_z = int(i) * 16;
                cell->constr_abs_z = false;
                root->constr_children.push_back(cell);
            }
        }
        log_info("Constrained mailbox synchronizer %s: 3 primary FFs in one slice; normal stage timing retained.\n", name.c_str());
    }
    log_info("Imported mailbox SYNCHRONIZER PLACEMENT ONLY; bundled-data timing enforcement remains separate.\n");
    if (ctx->args.options.count("mailbox-sync-audit")) {
        json11::Json::array actual;
        for (const auto &chain : contract["synchronizers"].array_items()) {
            json11::Json::array stages;
            for (const auto &declared : chain["stages"].array_items()) {
                auto *cell = ctx->cells.at(ctx->id(declared["cell"].string_value())).get();
                json11::Json::array children;
                for (const auto *child : cell->constr_children)
                    children.push_back(child->name.str(ctx));
                stages.push_back(json11::Json::object{
                    {"cell", cell->name.str(ctx)}, {"cluster", cell->cluster.str(ctx)},
                    {"x", cell->constr_x}, {"y", cell->constr_y}, {"z", cell->constr_z},
                    {"absolute_z", cell->constr_abs_z}, {"children", children},
                    {"ASYNC_REG", cell->attrs.at(ctx->id("ASYNC_REG")).as_string()}});
            }
            actual.push_back(json11::Json::object{{"name", chain["name"].string_value()}, {"stages", stages}});
        }
        std::string filename = ctx->args.options["mailbox-sync-audit"].as<std::string>();
        if (std::ifstream(filename).good())
            log_error("Mailbox synchronizer audit already exists.\n");
        std::ofstream output(filename);
        output << json11::Json(actual).dump() << '\n';
        output.close();
        if (!output)
            log_error("Cannot write mailbox synchronizer audit.\n");
    }
}
'''

PLACEMENT_CPP = r'''
    if (root_cell->type == id_SLICE_FFX && root_cell->attrs.count(ctx->id("X_MAILBOX_SYNC_ROOT"))) {
        placement.clear();
        if (root_bel == BelId() || !ctx->isValidBelForCellType(root_cell->type, root_bel))
            return false;
        Loc root = ctx->getBelLocation(root_bel);
        // FF z = slice*64 + slot*16 + BEL_FF. A/B roots leave room for C/D;
        // crossing z/64 would put a child in the other slice/control group.
        if ((root.z & 0xF) != BEL_FF || ((root.z & 63) >> 4) > 1)
            return false;
        if (!HimbaechelAPI::getClusterPlacement(cluster, root_bel, placement))
            return false;
        for (const auto &target : placement) {
            Loc loc = ctx->getBelLocation(target.second);
            if (loc.x != root.x || loc.y != root.y || loc.z / 64 != root.z / 64 ||
                (loc.z & 0xF) != BEL_FF || target.first->type != id_SLICE_FFX)
                return false;
        }
        return placement.size() == 3 && placement.front().second == root_bel;
    }
'''


def build(previous: Path, topology: Path, out: Path, workers: int):
    before = json.loads(previous.read_text())
    gate = json.loads(topology.read_text())
    if before['status'] != 'SOFTWARE_PHASE_BOUND_BUILD_PASS_NATIVE_VALIDATION_PENDING':
        raise ValueError('Expected completed software phase-bound backend')
    if gate['status'] != 'COMPLETE_PACKED_MAILBOX_PAYLOAD_AND_SYNCHRONIZER_TOPOLOGY_PASS_TIMING_PENDING':
        raise ValueError('Complete synchronizer topology has not passed')
    for field in ('binary', 'source_inventory'):
        if describe(before[field]['path']) != before[field]:
            raise ValueError('Previous ' + field + ' changed')
    original = Path(before['source'])
    expected = json.loads(Path(before['source_inventory']['path']).read_text())
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'helper': describe(__file__),
            'previous': describe(previous), 'topology_gate': describe(topology), 'workers': workers,
            'scope': 'SYNCHRONIZER_SAME_SLICE_PLACEMENT_NOT_BUNDLED_DATA_TIMING_OR_HARDWARE_PROOF',
            'hardware_accessed': False, 'live_full_route_changed': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def run(stage, argv):
        (out / (stage + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (stage + '.log')).open('w') as log:
            code = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
        (out / (stage + '.exit')).write_text(str(code) + '\n')
        return stage, code

    def replace(text, old, new):
        if text.count(old) != 1:
            raise ValueError('Unexpected source anchor: ' + old[:100])
        return text.replace(old, new)

    try:
        save(stage='copy-and-patch')
        source = out / 'source'
        shutil.copytree(original, source)
        if any(digest(source / name) != sha for name, sha in expected.items()):
            raise ValueError('Previous source changed')
        xilinx = source / 'himbaechel/uarch/xilinx'
        p = xilinx / 'pack.cc'
        text = replace(p.read_text(), 'NEXTPNR_NAMESPACE_BEGIN', 'NEXTPNR_NAMESPACE_BEGIN\n' + PACK_CPP)
        text = replace(text, '    initialize_dsp_timing();', '    constrain_mailbox_synchronizers(ctx);\n    initialize_dsp_timing();')
        p.write_text(text)
        p = xilinx / 'xilinx.cc'
        text = replace(p.read_text(), '    return specific;',
                       '    specific.add_options()("mailbox-sync-contract", po::value<std::string>(), "validated same-slice three-stage mailbox synchronizers");\n    specific.add_options()("mailbox-sync-audit", po::value<std::string>(), "actual packed synchronizer cluster-field audit");\n    return specific;')
        text = replace(text, '    CellInfo *root_cell = ctx->getClusterRootCell(cluster);',
                       '    CellInfo *root_cell = ctx->getClusterRootCell(cluster);\n' + PLACEMENT_CPP)
        p.write_text(text)
        shutil.copy2(Path(__file__).resolve().parents[1] / 'docs/openxc7_phy_timing_plan.md',
                     source / 'docs/xilinx-porting/12-mailbox-synchronizer-placement.md')
        updated = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
        (out / 'source.input.json').write_text(json.dumps(updated, indent=2) + '\n')
        objects = out / 'input-objects'
        objects.mkdir()
        link, jobs, reused = [], [], []
        template = before['compile_plan'][0]['argv']
        selected = {'pack.cc.o': 'himbaechel/uarch/xilinx/pack.cc', 'xilinx.cc.o': 'himbaechel/uarch/xilinx/xilinx.cc'}
        for i, arg in enumerate(before['link_argv']):
            if arg.endswith(('.o', '.a')) and Path(arg).is_file():
                target = objects / (str(i).zfill(3) + '-' + Path(arg).name)
                key = next((key for key in selected if Path(arg).name.endswith(key)), None)
                if key:
                    name = selected.pop(key)
                    argv = [v.replace(str(original), str(source)) for v in template]
                    for flag, value in (('-MF', str(target) + '.d'), ('-o', str(target)), ('-c', str(source / name))):
                        argv[argv.index(flag) + 1] = value
                    jobs.append({'source': str(source / name), 'output': str(target), 'argv': argv})
                else:
                    shutil.copy2(arg, target)
                    if digest(arg) != digest(target):
                        raise ValueError('Reused object changed')
                    reused.append({'original': describe(arg), 'copied': describe(target)})
                link.append(str(target))
            elif arg.startswith('-Wl,--dependency-file='):
                link.append('-Wl,--dependency-file=' + str(out / 'link.d'))
            else:
                link.append(arg)
        if selected or len(jobs) != 2:
            raise ValueError('Incomplete isolated rebuild')
        link[link.index('-o') + 1] = str(out / 'nextpnr-himbaechel')
        save(stage='compile', source=str(source), source_inventory=describe(out / 'source.input.json'),
             source_delta=sorted(name for name in updated if expected.get(name) != updated[name]),
             compile_plan=jobs, link_argv=link, reused_inputs=reused)
        print(f'COMPILING {len(jobs)} affected files with up to {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = dict(pool.map(lambda item: run('compile-' + str(item[0]), item[1]['argv']), enumerate(jobs)))
        save(compile_results=results)
        if any(results.values()):
            raise RuntimeError('Synchronizer placement compilation failed')
        for stage, argv in (('link', link), ('version', [str(out / 'nextpnr-himbaechel'), '--version'])):
            save(stage=stage)
            _, code = run(stage, argv)
            if code:
                raise RuntimeError(stage + ' failed')
        if any(digest(original / name) != sha for name, sha in expected.items()) or describe(before['binary']['path']) != before['binary']:
            raise ValueError('Previous backend changed during build')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='MAILBOX_SYNC_PLACEMENT_BUILD_PASS_NATIVE_VALIDATION_PENDING', binary=describe(out / 'nextpnr-himbaechel'),
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        shutil.copy2(__file__, out / 'helper.py')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'topology', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('Expected one to eight compiler workers')
    build(args.previous.resolve(), args.topology.resolve(), args.out.resolve(), args.workers)


if __name__ == '__main__':
    main()
