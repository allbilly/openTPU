"""Explicit transports for the reviewed c0160002 dual-channel DDR800 candidate.

These do not program, retrain, clear ECC counters, or promote the candidate to
a reliable release. The existing CH1 transport retains its original guards.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import ddrcal, regs as R
from .board import XdmaTransport
from .chestnut import ChestnutTransport

PACKAGE_STATUS = 'EXPERIMENTAL_DUAL_PCIE_OFFLINE_REVIEW_PASS_EXTERNAL_DDR_TIMING_AND_PHYSICAL_PENDING'
CH_BYTES = 1 << 31
LOGICAL_BYTES = 1 << 32
BUILD_ID = 0xc0160002
FULL = dict(MCOLS=4, ACT_ROWS=4, LANES=8, VPU_CL=2, MXU_IMPL=2, CORE_KHZ=100000, DDR_MTS=800)
ECC_CLEAN = dict(ecc_enable=1, ecc_sec_errors=0, ecc_ded_errors=0)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class DualPcieProfile:
    """Validate the packaged image and matched core before opening a device."""

    def __init__(self, package):
        self.package = Path(package).expanduser().resolve()
        manifest = self.package/'manifest.json'
        self.data = m = json.loads(manifest.read_text())
        require(m.get('status') == PACKAGE_STATUS and m.get('build_id_register') == '0xc0160002',
                'Require the reviewed c0160002 dual-channel package')
        require(m.get('compute') == FULL and m.get('memory') == dict(
            physical_user_channels=[0, 1], logical_capacity_bytes=LOGICAL_BYTES,
            virtual_channel_bytes=CH_BYTES, calibration_mask=3, ddr_mts=800, ecc=True),
            'Package must retain full compute and both physical 2 GiB channels')
        names = set()
        for item in m['files']:
            path = (self.package/item['name']).resolve()
            require(path.is_relative_to(self.package) and item['name'] not in names,
                    'Duplicate or escaping package path')
            names.add(item['name'])
            require(path.stat().st_size == item['bytes'] and digest(path) == item['sha256'],
                    'Packaged file changed: '+item['name'])
        self.core = self.package/'core'
        required = {'otpu.bit', 'core/openxc7-profile.json', 'core/csr.csv', 'core/sdram_init.py',
                    'core/otpu_litedram.v', 'core/otpu_litedram.xdc', 'core/otpu_litedram_mem.init',
                    'evidence/offline-image-review.json', 'evidence/cdc-review.json'}
        require(required <= names, 'Required image/core/review files missing from package hashes')
        core = json.loads((self.core/'openxc7-profile.json').read_text())
        require(core.get('parameters') == dict(CORE_KHZ=100000, DDR_MTS=800) and
                core.get('physical_user_channels', [0, 1]) == [0, 1] and
                core.get('calibration_mask', 3) == 3, 'Core is not dual-channel DDR800')
        for item in core['files'].values():
            require(Path(item['name']).name == item['name'], 'Invalid core filename')
            path = self.core/item['name']
            require('core/'+item['name'] in names and path.stat().st_size == item['bytes'] and
                    digest(path) == item['sha256'], 'Matched core changed: '+item['name'])
        self.manifest_sha256 = digest(manifest)
        self.bitstream_sha256 = digest(self.package/'otpu.bit')

    def check_image(self, transport):
        expected = {R.R_ID: R.ID_OTPU, R.R_VERSION: (128 << 16) | (4 << 8) | 8,
                    R.R_REGMAP: 3, R.R_CORE_KHZ: 100000, R.R_BUILD_ID: BUILD_ID,
                    R.R_DDR_MTS: 800, R.R_ACT_ROWS: 4, 0x5c: R.UNMAPPED}
        observed = {off: transport.reg_read(off) for off in expected}
        require(observed == expected, f'Dual-channel image identity differs: {observed}')
        caps = transport.reg_read(R.R_CAPS)
        required = R.CAP_HOSTCAL | R.CAP_DDR | R.CAP_ACT
        require(caps & required == required, 'Dual-channel image capabilities differ')
        return {f'{off:#x}': value for off, value in observed.items()}


class _DualMemory:
    CH_BYTES = CH_BYTES
    owns_device_lock = True

    def _check_image(self):
        self.image_identity = self.profile.check_image(self)

    def _initialize_memory(self):
        self.csr = ddrcal.WordCsr(ddrcal.csr_map(self.calibration_data/'csr.csv'),
                                 self.reg_read, self.reg_write, base=R.R_MEMCAL)
        require(self.csr.r('selfcal_status') >> 16 == 0x5ca1, 'Calibration CSR ABI identity mismatch')
        self.channels = {ch: ddrcal.Chan(self.csr, ch) for ch in (0, 1)}
        # Initialization permits read-only failure reporting. Every memory
        # operation separately requires both channels ready and clean.

    def ecc_state(self):
        return {ch: {name: channel.r(name) for name in ECC_CLEAN}
                for ch, channel in self.channels.items()}

    def guard(self):
        require(not getattr(self, 'failed', False), 'Failed DMA transport requires recovery')
        status = self.reg_read(R.R_STATUS)
        ecc = self.ecc_state()
        require(status & (R.ST_CALIB0 | R.ST_CALIB1) == (R.ST_CALIB0 | R.ST_CALIB1) and
                not status & (R.ST_ERROR | R.ST_AXI_ERR), f'Dual-channel memory not ready: {status:#x}; ECC={ecc}')
        require(all(values == ECC_CLEAN for values in ecc.values()), f'Dual-channel ECC is not clean: {ecc}')
        return ecc

    def _range(self, ch, off, count):
        require(ch in (0, 1) and off >= 0 and count >= 0 and off+count <= CH_BYTES,
                'Dual-channel DMA permits 2 GiB per physical channel')

    def mem_write(self, ch, off, data):
        self._range(ch, off, memoryview(data).nbytes)
        self.guard()
        result = super().mem_write(ch, off, data)
        self.guard()
        return result

    def mem_read(self, ch, off, count, out=None):
        self._range(ch, off, count)
        self.guard()
        result = super().mem_read(ch, off, count, out)
        self.guard()
        return result

    def scrub(self):
        self.guard()
        # Raw BIST zero initializes data and ECC bits. Native checks follow in
        # the runner; a raw BIST pass alone does not qualify the native ECC path.
        for mode in (0, 1):
            for channel in self.channels.values():
                ddrcal.bist_start(channel, 1 << 25, mode, 0)
            for ch, channel in self.channels.items():
                result = ddrcal.bist_wait(channel, 1 << 25, mode, 100000000, timeout=120)
                require(result['beats'] == 1 << 25 and not result.get('errors') and
                        not any(result.get('lanes', [])), f'CH{ch} zero scrub failed: {result}')
        self.guard()


class DualChestnutTransport(_DualMemory, ChestnutTransport):
    def __init__(self, profile: DualPcieProfile):
        self.profile, self.calibration_data = profile, profile.core
        super().__init__()


class DualXdmaTransport(_DualMemory, XdmaTransport):
    def __init__(self, profile: DualPcieProfile, dev='/dev/xdma0'):
        self.profile, self.calibration_data = profile, profile.core
        super().__init__(dev)
        try:
            self._check_image()
            self._initialize_memory()
        except BaseException:
            self.close()
            raise

    def reg_write(self, off, value):
        require(off != R.R_MEMCAL+0x2000, 'Global SoC reset CSR is unsupported')
        return super().reg_write(off, value)
