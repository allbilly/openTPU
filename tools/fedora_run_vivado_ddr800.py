#!/usr/bin/env python3
"""Load the full DDR800 Vivado reference, then test matmul and real LFM2.

All loading is volatile SRAM. No PCIe endpoint or permanent flash is implied.
"""
import argparse
from collections import deque
import contextlib
import dataclasses
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fedora_run_vivado_native_jtag import NativeLink, TCL, VIVADO
from fedora_vivado_ddr800_qualify import qualify, CORE, IMAGE, describe, require


def matmul_check(board):
    import numpy as np
    from opentpu import isa as I
    from opentpu.isasim import Machine
    from opentpu.host.board import device_config
    from opentpu.host.checks import demo_image, DATA, W8, SC, OUT, PROG_AT

    cfg = device_config(board.info(), DRAM_BYTES=1 << 23)
    image = demo_image()
    program = [I.ld(DATA, 0, 512), I.qact(0, 2, 0, 2, 256),
               I.mm(W8, SC, 1024, 16, 2, 256, 16, 2, 0, 8),
               I.st(OUT, 1024, 32), I.halt()]
    dram = np.zeros(1 << 23, np.uint8)
    dram[:len(image)] = image
    expected = Machine(cfg, [program], [dram]).run().slices[0]
    # Only defined operands are transferred. Full DDR was initialized and tested.
    for start, length in [(DATA, 512*4), (W8, 16*256), (SC, 64*4)]:
        board.write(start, image[start:start+length])
        got = board.read(start, length)
        require(np.array_equal(got, image[start:start+length]),
                f'Matmul operand transfer failed at {start:#x}')
    board.load_program(PROG_AT, np.asarray(I.assemble(program), np.uint32))
    stats = board.run(timeout=10)
    actual = board.read(OUT, 32*4)
    want = expected.dram[OUT:OUT+32*4]
    result = dict(physical=True, operation='MM int8 weights with QACT',
                  output_shape=[2, 16], reduction=256, bytes_compared=128,
                  expected_instructions=expected.icount,
                  actual_instructions=stats['instructions'][0], cycles=stats['cycles'],
                  exact_match=bool(np.array_equal(actual, want)),
                  actual_words=actual.view('<u4').tolist(),
                  expected_words=want.view('<u4').tolist())
    return result


def main():
    import numpy as np
    from opentpu.host import jtag, memcal, ddrcal, regs as R, selftest
    from opentpu.host.board import Board

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--loaded-receipt', type=Path,
                    help='Reuse the verified DDR800 SRAM load, retaining all memory/compute gates')
    ap.add_argument('--recalibrate', action='store_true',
                    help='Run matching host PHY calibration again at the current board temperature')
    ap.add_argument('--recalibrate-cpu', action='store_true',
                    help='Restart the matching on-board calibration CPU at the current temperature')
    ap.add_argument('--wait-usb', type=int, default=0,
                    help='Wait this many seconds for two stable USB detections before accessing JTAG')
    ap.add_argument('--model-first', action='store_true',
                    help='Run physical LFM2 directly after memory and matmul; defer extended selftests')
    ap.add_argument('--model', default='lfm2', help='LFM2 checkpoint name or directory')
    args = ap.parse_args()
    if args.wait_usb < 0:
        ap.error('--wait-usb must be nonnegative')
    if args.recalibrate and args.recalibrate_cpu:
        ap.error('Choose host calibration or on-board CPU calibration')
    out = args.out.resolve()
    require(not out.exists(), 'Choose a new receipt directory')
    out.mkdir(parents=True)
    receipt = dict(status='OFFLINE_PREFLIGHT_RUNNING', physical=True, flash_written=False,
                   hardware_accessed=False, recalibrate=args.recalibrate,
                   recalibrate_cpu=args.recalibrate_cpu,
                   model=args.model, model_first=args.model_first,
                   programming='NOT_RUN', transport='Vivado native JTAG', full_compute=True,
                   pci_endpoint=False, started_utc=datetime.now(timezone.utc).isoformat(),
                   memory_passes=[], model_checks=[])
    hw = bridge = board = None
    opened = []

    def save():
        temporary = out/'manifest.json.tmp'
        temporary.write_text(json.dumps(receipt, indent=2)+'\n')
        temporary.replace(out/'manifest.json')

    class TracedTransport(jtag.JtagTransport):
        def __init__(self):
            self.history = deque(maxlen=64)
            self.model_checks = []
            self.io_stats = dict(read_beats=0, write_beats=0)
            self.begin = self.reported = time.monotonic()
            super().__init__('localhost', 3741, link=NativeLink(), calibration_data=CORE)

        def _command(self, opcode, addr, data=0, strobes=15):
            event = dict(opcode=opcode, address=hex(addr), strobes=strobes,
                         started_utc=datetime.now(timezone.utc).isoformat())
            self.history.append(event)
            try:
                value = super()._command(opcode, addr, data, strobes)
                event.update(status='COMPLETE', sequence=self._seq)
                if opcode in (3, 4):
                    self.io_stats['read_beats' if opcode==3 else 'write_beats'] += 1
                    now = time.monotonic()
                    if now-self.reported >= 10:
                        print('JTAG_IO_PROGRESS '+json.dumps(dict(**self.io_stats,
                              seconds=now-self.begin, bytes_per_beat=64)), flush=True)
                        self.reported = now
                return value
            except BaseException as error:
                event.update(status='FAIL', error=repr(error), sequence=self._seq)
                (out/'last-jtag-transactions.json').write_text(json.dumps(list(self.history),indent=2)+'\n')
                raise

        def record_model_check(self, result):
            result = dict(result, physical=True)
            self.model_checks.append(result)
            receipt['model_checks'] = [row for transport in opened for row in transport.model_checks]
            save()
            print('PHYSICAL_MODEL_COMPARISON '+json.dumps(result), flush=True)

    def factory(*unused):
        t = TracedTransport()
        opened.append(t)
        return t

    try:
        save()
        from importlib.metadata import version
        from opentpu.llm import model_dir
        model_path = model_dir(args.model).resolve()
        require(json.loads((model_path/'config.json').read_text()).get('model_type')
                in ('lfm2','lfm2_moe'), 'This inference run requires an LFM2 checkpoint')
        receipt['python_runtime'] = dict(executable=sys.executable, prefix=sys.prefix,
            packages={name:version(name) for name in ('numpy','torch','transformers','safetensors')})
        receipt['model_inputs'] = [describe(model_path/name) for name in
            ('config.json','tokenizer.json','tokenizer_config.json','model.safetensors')]
        preflight = qualify()
        (out/'offline-preflight.json').write_text(json.dumps(preflight,indent=2)+'\n')
        qualification = json.loads((ROOT/'build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/manifest.json').read_text())
        checker = next(item for item in qualification['inputs']
                       if Path(item['path']).name == 'check-crc')
        require(describe(checker['path']) == checker, 'Qualified CRC checker changed')
        checked = subprocess.run([checker['path'],preflight['bitstream']['path']],
                                 capture_output=True,text=True,check=True)
        crc = json.loads(checked.stdout)
        require(crc['status']=='ALL_PRESENT_CRC_CHECKPOINTS_MATCH' and
                crc['crc_checkpoints']==2, 'Vivado CRC checkpoint check failed')
        (out/'crc.json').write_text(json.dumps(crc,indent=2)+'\n')
        receipt['offline_preflight'] = preflight['status']
        receipt['profile'] = preflight['profile']
        receipt['inputs'] = [describe(p) for p in
                [Path(__file__), ROOT/'tools/fedora_run_vivado_native_jtag.py',
                 ROOT/'tools/fedora_vivado_ddr800_qualify.py',
                 ROOT/'opentpu/host/jtag.py', CORE/'csr.csv', CORE/'sdram_init.py']]
        for owner in ('hw_server','openFPGALoader','xsdb','fxload'):
            require(subprocess.run(['pgrep','-x',owner],stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL).returncode!=0, 'Active cable owner: '+owner)
        deadline = time.monotonic()+args.wait_usb
        previous = None
        while True:
            usb = subprocess.run(['lsusb'],capture_output=True,text=True,check=True).stdout
            cables = [line for line in usb.splitlines() if 'ID 03fd:' in line]
            require(len(cables)<=1, 'Multiple cables detected; target is ambiguous')
            receipt.update(status='WAITING_FOR_STABLE_USB', usb_at_check=usb,
                           usb_checked_utc=datetime.now(timezone.utc).isoformat())
            save()
            if len(cables)==1 and (not args.wait_usb or cables==previous):
                break
            if time.monotonic()>=deadline:
                receipt.update(status='NOT_RUN_USB_TIMEOUT',
                               error='No stable single cable detected before the deadline')
                return 2
            previous = cables
            time.sleep(min(5, max(0, deadline-time.monotonic())))
        # A cable can arrive while another owner starts. Recheck after waiting.
        for owner in ('hw_server','openFPGALoader','xsdb','fxload'):
            require(subprocess.run(['pgrep','-x',owner],stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL).returncode!=0, 'Active cable owner: '+owner)
        for port in (3122,3741):
            with socket.socket() as probe:
                require(probe.connect_ex(('127.0.0.1',port))!=0, 'Port already owned: '+str(port))
        receipt['usb_at_start'] = usb
        (out/'bridge.tcl').write_text(TCL)
        with (out/'hw-server.log').open('w') as log:
            hw = subprocess.Popen([str(VIVADO/'hw_server'),'-s','tcp::3122'],
                                  stdout=log,stderr=subprocess.STDOUT)
        env = dict(os.environ, OTPU_NATIVE_READY=str(out/'native-ready.txt'),
                   OTPU_NATIVE_BIT=preflight['bitstream']['path'],
                   OTPU_NATIVE_PROGRAM_STATUS=str(out/'native-program-status.txt'))
        if args.loaded_receipt:
            parent = json.loads(args.loaded_receipt.read_text())
            require(parent['programming']=='PASS_NATIVE_SRAM_INIT_DONE_AND_EXPECTED_MAILBOX'
                    and parent['profile']==preflight['profile'], 'Verified full DDR800 parent load required')
            receipt['loaded_receipt']=describe(args.loaded_receipt)
            env.pop('OTPU_NATIVE_BIT')
            env.pop('OTPU_NATIVE_PROGRAM_STATUS')
        with (out/'vivado.log').open('w') as log:
            bridge = subprocess.Popen([str(VIVADO/'vivado'),'-mode','batch','-nojournal',
                    '-nolog','-source',str(out/'bridge.tcl')],cwd=out,env=env,
                    stdout=log,stderr=subprocess.STDOUT)
        receipt.update(status='NATIVE_SRAM_PROGRAMMING_RUNNING',
                       hardware_accessed=True,
                       hw_server_pid=hw.pid,vivado_pid=bridge.pid)
        save()
        deadline = time.monotonic()+300
        while not (out/'native-ready.txt').exists():
            require(hw.poll() is None and bridge.poll() is None, 'Native programming failed')
            require(time.monotonic()<deadline, 'Native programming timeout')
            time.sleep(.5)
        if args.loaded_receipt:
            receipt['programming'] = 'VERIFIED_PARENT_SRAM_LOAD_REUSED_CURRENT_IDENTITY_REQUIRED'
        else:
            require((out/'native-program-status.txt').read_text().strip()=='INIT=1 DONE=1',
                    'Native SRAM INIT/DONE gate failed')
            receipt['programming'] = 'PASS_NATIVE_SRAM_INIT_DONE_AND_EXPECTED_MAILBOX'
        t = factory()
        board = Board(t,check=False)
        info = board.info()
        receipt['identity'] = info
        require((info['D'],info['MCOLS'],info['LANES'],info['act_rows'],
                info['core_khz'],info['ddr_mts'],info['regmap']) ==
                (128,4,8,4,100000,800,3) and t.reg_read(R.R_CAPS)&R.CAP_HOSTCAL,
                'Loaded full DDR800 identity differs')
        receipt['status'] = 'LITEDRAM_CALIBRATION_RUNNING'
        save()
        receipt['before_calibration_status'] = t.reg_read(R.R_STATUS)
        require(not receipt['before_calibration_status'] & (R.ST_RUN|R.ST_LOADING),
                'Calibration requires an idle accelerator')
        t.reg_write(R.R_CTRL,0)
        t.poll(R.R_STATUS,R.ST_WR_IDLE,R.ST_WR_IDLE,timeout=30)
        with (out/'calibration.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            if args.recalibrate_cpu:
                from opentpu.host import selfcal
                csr = memcal.csr(t)
                require(selfcal.present(csr), 'Matching on-board calibration CPU is absent')
                selfcal.hold(csr)
                csr.w('selfcal_config',3 | (1<<8))  # both complete channels, stride 1
                selfcal.release(csr)
                state = selfcal.wait(csr,timeout=120,poll=.5)
                results = selfcal.result(csr,CORE/'sdram_init.py')
                calibration = dict(by='restarted on-board CPU',state=state,channels=results)
                print('ON_BOARD_WARM_CALIBRATION '+json.dumps(calibration),flush=True)
                require(state['done'] and set(results)=={0,1} and
                        all(v['state']=='ok' and v['traffic_checked'] for v in results.values()),
                        'On-board warm calibration did not pass both channels with traffic checks')
            else:
                calibration = memcal.ensure(t,force=args.recalibrate)
        receipt['calibration'] = calibration
        require(t.reg_read(R.R_STATUS)&96 == 96, 'Both DDR channels must calibrate')
        receipt['status'] = 'FULL_MEMORY_TEST_RUNNING'
        save()
        csr = memcal.csr(t)
        with (out/'memory.log').open('w') as log, contextlib.redirect_stdout(log):
            for ch in (0,1):
                channel = ddrcal.Chan(csr,ch)
                for mode,seed in [(0,0x0123456789abcdef),(2,0x9e3779b97f4a7c15),(0,0)]:
                    for read in (False,True):
                        actual_mode = mode|int(read)
                        result = ddrcal.bist(channel,1<<25,actual_mode,seed,100000000,timeout=120)
                        entry = dict(channel=ch,mode=actual_mode,seed=hex(seed),**result)
                        receipt['memory_passes'].append(entry)
                        print('FULL_DDR_BIST '+json.dumps(entry),flush=True)
                        save()
                        require(result['beats']==1<<25 and not result.get('errors',0) and
                                not any(result.get('lanes',[])), 'Full DDR BIST failed')
        board.scrub()
        receipt['status'] = 'PHYSICAL_MATMUL_RUNNING'
        save()
        with (out/'matmul.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            receipt['matmul'] = matmul_check(board)
            print('PHYSICAL_MATMUL_COMPARISON '+json.dumps(receipt['matmul']),flush=True)
            save()
            require(receipt['matmul']['exact_match'] and
                    receipt['matmul']['actual_instructions']==receipt['matmul']['expected_instructions'],
                    'Physical matmul differs from ISA')
        board.close()
        t.close()
        if args.model_first:
            from opentpu.host.board import device_config
            from opentpu.host.checks import model_check
            receipt.update(status='PHYSICAL_LFM2_RUNNING',
                           extended_selftest='DEFERRED_UNTIL_AFTER_PHYSICAL_LLM')
            save()
            t = factory()
            board = Board(t, check=True)
            cfg = device_config(board.info(), DRAM_BYTES=1<<32)
            with (out/'model.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                ok, message = model_check(t,cfg,args.model,8,False,wformat='int8')
                receipt['model_message'] = message
                print('PHYSICAL_MODEL_RESULT '+message,flush=True)
                save()
                require(ok, 'Physical LFM2 tokens differ from ISA')
            rows = receipt['model_checks']
            require(rows and all(row.get('physical') and row.get('exact_match') and
                    row.get('actual_token_ids') == row.get('expected_token_ids') and
                    row.get('actual_token_ids') and 'Paris' in row.get('text','') for row in rows),
                    'Exact physical LFM2 tokens and expected answer absent')
            receipt.update(status='PASS_PHYSICAL_DDR_MATMUL_AND_LFM2')
            board.close()
            return 0
        receipt['status'] = 'FULL_PHYSICAL_SELFTEST_AND_LFM2_RUNNING'
        save()
        with (out/'selftest.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            code = selftest.main(['--dev','jtag://localhost:3741','--bw-mib','1',
                                 '--model',args.model,'--tokens','8','--wformat','int8'],
                                open_transport=factory)
        receipt['selftest_exit'] = code
        (out/'selftest.exit').write_text(f'{code}\n')
        require(code==0, 'Full physical selftest failed')
        rows = [row for t in opened for row in t.model_checks]
        require(rows and all(row.get('exact_match') and row.get('actual_token_ids') for row in rows),
                'Exact physical model tokens absent or failed')
        receipt.update(status='PASS_FULL_PHYSICAL_SELFTEST_AND_LFM2',model_checks=rows)
        return 0
    except Exception as error:
        receipt.update(status='FAIL',error=repr(error))
        print(receipt['error'],flush=True)
        return 1
    finally:
        if board is not None:
            board.close()
        receipt['io_stats'] = [t.io_stats for t in opened]
        if not receipt['model_checks']:
            receipt['model_checks'] = [row for t in opened for row in t.model_checks]
        for t in opened:
            t.close()
        if bridge is not None:
            if bridge.poll() is None:
                try:
                    link=NativeLink(timeout=5)
                    link.command('QUIT')
                    link.close()
                    bridge.wait(timeout=15)
                except (OSError,subprocess.TimeoutExpired):
                    bridge.terminate()
                    try: bridge.wait(timeout=5)
                    except subprocess.TimeoutExpired: bridge.kill();bridge.wait()
            receipt['vivado_exit']=bridge.returncode
        if hw is not None:
            hw.terminate()
            try: hw.wait(timeout=10)
            except subprocess.TimeoutExpired: hw.kill();hw.wait()
            receipt['hw_server_exit']=hw.returncode
        receipt['finished_utc']=datetime.now(timezone.utc).isoformat()
        save()


if __name__=='__main__':
    raise SystemExit(main())

