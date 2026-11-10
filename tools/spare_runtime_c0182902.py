"""Image-bound CH0 calibration checks for the c0182902 JTAG test runner."""
import json
from pathlib import Path

from opentpu.host import regs as R, selfcal
from opentpu.host.dual_pcie import digest, require


def calibration_snapshot(transport):
    return dict(
        mailbox=selfcal.mailbox(transport.csr),
        phase={str(ch): channel.r('phase_dqs_steps') for ch, channel in transport.channels.items()},
        ready={str(ch): channel.r('cal_ready') for ch, channel in transport.channels.items()},
    )


def check_calibration_receipt(path, profile, transport):
    path = Path(path)
    receipt = json.loads(path.read_text())
    require(receipt.get('status') == 'SPARE_PCIE_CH0_CALIBRATION_RECORDED_MEMORY_UNQUALIFIED',
            'A successful c0182902 CH0 calibration receipt is required')
    binding = receipt.get('binding', {})
    require(binding.get('required_build_id') == 'c0182902' and
            binding.get('required_bitstream_sha256') == profile.bitstream_sha256 and
            binding.get('package_manifest_sha256') == profile.manifest_sha256,
            'Calibration receipt belongs to another c0182902 package')
    require(binding.get('firmware_id') == 'c0172168' and
            binding.get('startup_firmware_id') == 'c0172160' and
            binding.get('firmware_sha256') == digest(profile.package/'calibration/selfcal.bin') and
            binding.get('firmware_model_review_sha256') == profile.firmware_model_review_digest(),
            'Calibration firmware/model binding differs')
    matched = {name: profile.core_file_digest(name) for name in (
        'otpu_litedram.v', 'csr.csv', 'sdram_init.py', 'sdram_init_ch0.py',
        'otpu_litedram_mem.init')}
    require(binding.get('matched_core_files') == matched,
            'Calibration receipt names different core configuration files')
    require(receipt.get('hardware_accessed') and receipt.get('firmware_uploaded') and
            receipt.get('calibration_requested') and receipt.get('firmware_words_verified') == 4096,
            'Calibration upload/execution evidence is incomplete')
    require(not receipt.get('flash_written') and not receipt.get('programming_performed'),
            'Unexpected permanent programming/calibration operation')
    startup = receipt.get('startup', {})
    calibration = receipt.get('calibration', {})
    require(startup.get('done') and startup.get('channels', {}).get('1', [None])[0] == 'ok' and
            startup.get('channels', {}).get('0', [None])[0] == 'idle' and
            receipt.get('startup_mailbox', [])[:2] == [selfcal.MB_MAGIC_V, 0xc0172160],
            'The expected CH1-only startup calibration did not complete')
    require(calibration.get('done') and calibration.get('channels', {}).get('0', [None])[0] == 'ok' and
            calibration.get('channels', {}).get('1', [None])[0] == 'idle' and
            receipt.get('mailbox', [])[:2] == [selfcal.MB_MAGIC_V, 0xc0172168],
            'The expected CH0 calibration did not complete')
    require(receipt.get('normal_memory_requires_initialization') is True,
            'Calibration receipt must not be treated as memory qualification')

    actual = calibration_snapshot(transport)
    require(actual['mailbox'] == receipt['mailbox'], 'Live calibration mailbox differs')
    require(actual['phase'] == receipt.get('phase_after') and actual['ready'] == {'0': 1, '1': 1},
            'Live calibration phase/readiness differs from the receipt')
    transport.guard()
    return {'receipt_sha256': digest(path), 'snapshot': actual,
            'memory_qualified': False, 'normal_memory_initialization_required': True}


def require_idle_for_test(transport):
    status = transport.reg_read(R.R_STATUS)
    require(not status & (R.ST_RUN | R.ST_LOADING | R.ST_ERROR | R.ST_AXI_ERR) and
            status & R.ST_WR_IDLE, f'Accelerator must be idle and error-free: {status:#x}')
    transport.guard()
