"""Explicit c0182800 transports: 4 GiB with ECC on CH1 only.

Requires a separately reviewed package. Opening a transport does not program
or calibrate memory. Existing CH1 and dual-ECC transport guards are unchanged.
"""
from __future__ import annotations
import json
from pathlib import Path
import time

from . import ddrcal,regs as R
from .board import XdmaTransport
from .chestnut import ChestnutTransport
from .dual_pcie import _DualMemory,CH_BYTES,LOGICAL_BYTES,FULL,require,digest

FULL=dict(FULL,CORE_KHZ=100000,DDR_MTS=800)
PACKAGE_STATUS='EXPERIMENTAL_SPARE_DUAL_HOST_OFFLINE_REVIEW_PASS_EXTERNAL_DDR_TIMING_AND_PHYSICAL_PENDING'
BUILD_ID=0xc0182800
LANES=[0,1,2,3,4,5,8,7]
MEMORY=dict(physical_user_channels=[0,1],logical_capacity_bytes=LOGICAL_BYTES,
            virtual_channel_bytes=CH_BYTES,calibration_mask=3,ddr_mts=800,ecc_channels=[1],
            ch0_physical_lanes=LANES,automatic_calibration_channels=[1],host_calibration_channels=[0])


REVIEWED_MANIFEST_SHA256='1c936f343bda648b4120e65bf1507999129c8b9bed67e8bab1e457828e161c3d'
RUNTIME_MANIFEST_SHA256='310e2856d29c0eb2b8f917b8b8a72537bc3d63546a2c3f6d84aaf3524a155093'

class SparePcieProfile:
    def __init__(self,package):
        self.package=Path(package).expanduser().resolve();manifest=self.package/'manifest.json'
        self.runtime_only=(self.package/'runtime.json').is_file()
        if self.runtime_only:
            self._load_runtime()
            return
        self.data=m=json.loads(manifest.read_text())
        require(m.get('status')==PACKAGE_STATUS and m.get('build_id_register')=='0xc0182800',
                'Require the reviewed c0182800 spare-lane package')
        require(m.get('compute')==FULL and m.get('memory')==MEMORY,'Wrong spare memory/compute profile')
        names=set()
        for item in m['files']:
            path=(self.package/item['name']).resolve()
            require(path.is_relative_to(self.package) and item['name'] not in names,'Duplicate or escaping package path')
            names.add(item['name'])
            require(path.stat().st_size==item['bytes'] and digest(path)==item['sha256'],'Packaged file changed: '+item['name'])
        self.core=self.package/'core'
        required={'otpu.bit','core/openxc7-profile.json','core/variant-profile.json','core/sdram_init_ch0.py',
                  'core/csr.csv','core/sdram_init.py','core/otpu_litedram.v','core/otpu_litedram.xdc',
                  'core/otpu_litedram_mem.init','evidence/offline-image-review.json','evidence/cdc-review.json',
                  'evidence/csr-gray-review.json','evidence/adapter-model.json',
                  'evidence/adapter-source.py','evidence/dual-host-model.json',
                  'evidence/dual-host/otpu_host_reset.sv','evidence/dual-host/otpu_jtag_axi_abort.sv',
                  'evidence/bridge-model.json','evidence/controller-model.json','calibration/pipeline-binding.json'}
        require(required<=names,'Incomplete spare package')
        profile=json.loads((self.core/'variant-profile.json').read_text())
        require(profile.get('variant')=='spare8-pipelined-shared-bus' and 'native_probe' not in profile and
                profile.get('parameters')==dict(CORE_KHZ=100000,DDR_MTS=800) and
                profile.get('physical_databits')==[64,72] and profile.get('ecc_channels')==[1] and
                profile.get('ch0_physical_lanes')==LANES and profile.get('automatic_calibration_channels')==[1] and
                profile.get('native_read_depth_per_port')==32 and profile.get('native_raw_ports_used')==2 and
                profile.get('masked_writes_globally_exclusive') is True and
                profile.get('shared_read_response_bus') is True and
                profile.get('single_read_response_per_cycle') is True,
                'Expected two-port spare core with CH1-only automatic calibration')
        require(json.loads((self.core/'openxc7-profile.json').read_text())==profile,'Core profiles disagree')
        for item in profile['files'].values():
            require(Path(item['name']).name==item['name'],'Invalid core filename')
            path=self.core/item['name']
            require('core/'+item['name'] in names and path.stat().st_size==item['bytes'] and digest(path)==item['sha256'],
                    'Matched core differs: '+item['name'])
        require(digest(self.core/'sdram_init_ch0.py')==profile['ch0_init_sha256'],'CH0 calibration profile changed')
        q=json.loads((self.package/'evidence/offline-image-review.json').read_text())
        c=json.loads((self.package/'evidence/cdc-review.json').read_text())
        g=json.loads((self.package/'evidence/csr-gray-review.json').read_text())
        self.bitstream_sha256=digest(self.package/'otpu.bit');self.manifest_sha256=digest(manifest)
        require(q['status']=='SPARE_DUAL_HOST_ARTIFACT_CHECKS_PASS_CDC_AND_RUNTIME_PENDING' and
                c['status']=='SPARE_DUAL_HOST_CDC_REVIEW_PASS_EXTERNAL_DDR_TIMING_AND_PHYSICAL_PENDING' and
                g['status']=='PASS_ROUTED_CSR_GRAY_SKEW_AND_SYNCHRONIZERS_PHYSICAL_PENDING',
                'Spare artifact/CDC/gray-pointer reviews incomplete')
        require(all(v['bitstream']['sha256']==self.bitstream_sha256 for v in (q,c,g)),
                'Review belongs to another image')
        check_dual_host_evidence(self)

    def _load_runtime(self):
        """Check small files for an already flashed card, not absent build outputs.

        The pinned export records the reviewed image and its provenance. Only
        live registers can establish the identity of the connected FPGA; they
        do not cryptographically attest the flash contents.
        """
        manifest=self.package/'runtime.json'
        require(digest(manifest)==RUNTIME_MANIFEST_SHA256,'Runtime metadata changed')
        runtime=json.loads(manifest.read_text())
        require(runtime['kind']=='C0182800_REVIEWED_IMAGE_RUNTIME_FILES', 'Wrong runtime export')
        names=set()
        for item in runtime['files']:
            name=item['name'];path=(self.package/name).resolve()
            require(path.is_relative_to(self.package) and name not in names,'Invalid runtime path')
            names.add(name)
            require(path.stat().st_size==item['bytes'] and digest(path)==item['sha256'],
                    'Runtime file changed: '+name)
        require(digest(self.package/'reviewed-image.json')==REVIEWED_MANIFEST_SHA256,
                'Wrong original image review')
        self.data=m=json.loads((self.package/'reviewed-image.json').read_text())
        require(m['status']==PACKAGE_STATUS and m['build_id_register']=='0xc0182800' and
                m['compute']==FULL and m['memory']==MEMORY,'Wrong runtime image configuration')
        inventory={item['name']:item for item in m['files']}
        for name in names-{'reviewed-image.json'}:
            require(name in inventory and digest(self.package/name)==inventory[name]['sha256'],
                    'Runtime file differs from reviewed image: '+name)
        self.core=self.package/'core'
        self.bitstream_sha256=inventory['otpu.bit']['sha256']
        self.manifest_sha256=digest(manifest)
        self.runtime_metadata=runtime
        require(m.get('host')==dict(interfaces=['pcie','jtag'],jtag_chain=2,jtag_max_hz=6000000,host_dma_hz=250000000), 'Wrong combined-interface image')
        require(runtime['host']==m['host'], 'Runtime interface binding differs')


    def core_file_digest(self,name):
        require(Path(name).name==name,'Invalid core filename')
        if not self.runtime_only or (self.core/name).is_file():
            return digest(self.core/name)
        # The netlist is deliberately not distributed for runtime use. This is
        # a recorded build binding, not a local netlist integrity check.
        require(name=='otpu_litedram.v','Required runtime core file absent')
        return next(item['sha256'] for item in self.data['files'] if item['name']=='core/'+name)

    def check_image(self,transport):
        expected={R.R_ID:R.ID_OTPU,R.R_VERSION:(128<<16)|(4<<8)|8,R.R_REGMAP:3,
                  R.R_CORE_KHZ:100000,R.R_BUILD_ID:BUILD_ID,R.R_DDR_MTS:800,R.R_ACT_ROWS:4,
                  0x5c:0x10000203,0x60:0x78543210,0x64:2}
        actual={off:transport.reg_read(off) for off in expected}
        require(actual==expected,f'Spare image identity differs: {actual}')
        required=R.CAP_HOSTCAL|R.CAP_DDR|R.CAP_ACT
        require(transport.reg_read(R.R_CAPS)&required==required,'Spare image capabilities differ')
        return {f'{k:#x}':v for k,v in actual.items()}


class _SpareMemory(_DualMemory):
    def guard(self):
        require(not getattr(self,'failed',False),'Failed DMA transport requires recovery')
        status=self.reg_read(R.R_STATUS);ecc=self.ecc_state()
        require(status&(R.ST_CALIB0|R.ST_CALIB1)==(R.ST_CALIB0|R.ST_CALIB1) and
                not status&(R.ST_ERROR|R.ST_AXI_ERR),f'Spare memory not ready: {status:#x}')
        expected={ch:dict(ecc_enable=ch,ecc_sec_errors=0,ecc_ded_errors=0) for ch in (0,1)}
        require(ecc==expected,f'Spare ECC profile/error state differs: {ecc}')
        require(all(c.r('cal_ready') and c.r('bist_done') for c in self.channels.values()),
                'Calibration incomplete or raw BIST active')
        return ecc

    def scrub(self):
        """Destructive whole-range zero initialization, serialized in 4 MiB chunks.

        Includes CH1 parity bytes; raw verification does not qualify native ECC.
        Preserve failed counters and never mark memory initialized on failure.
        """
        self.guard();status=self.reg_read(R.R_STATUS)
        require(not status&(R.ST_RUN|R.ST_LOADING) and status&R.ST_WR_IDLE,'Accelerator must be idle before scrub')
        self.reg_write(R.R_SCRATCH,0)
        self.scrub_log=[]
        with self._dma:
            for mode in (0,1):
                for ch,c in self.channels.items():
                    for base in range(0,CH_BYTES,4<<20):
                        self.guard();epoch=c.r('bist_raw_sequence');beats=(4<<20)//64
                        for name,value in [('base',base//64),('length',beats),('seed',0),('mode',mode),('start',1)]:
                            c.w('bist_'+name,value)
                        deadline=time.monotonic()+10
                        while not c.r('bist_done'):
                            if time.monotonic()>deadline:raise TimeoutError('Spare zero initialization timed out')
                            time.sleep(.005)
                        result=dict(channel=ch,base=base,mode=mode,beats=c.r('bist_beats'),ticks=c.r('bist_ticks'),
                                    epoch=c.r('bist_raw_sequence'),returns=c.r('bist_raw_returns'))
                        if mode:
                            result.update(errors=c.r('bist_errors'),bits=c.r('bist_lane_bits'),
                                          lanes=[c.r(f'bist_lane{i}_errors') for i in range(8 if ch==0 else 9)])
                        self.scrub_log.append(result)
                        require(result['beats']==beats and result['ticks']>0 and
                                result['epoch']==(epoch+1)&0xffffffff and result['returns']==(beats if mode else 0),
                                f'Incomplete zero initialization: {result}')
                        require(not result.get('errors') and not result.get('bits') and not any(result.get('lanes',[])),
                                f'Zero initialization failed: {result}')
                        time.sleep(.2)
        self.guard()


class SpareChestnutTransport(_SpareMemory,ChestnutTransport):
    def __init__(self,profile:SparePcieProfile):
        self.profile,self.calibration_data=profile,profile.core
        super().__init__()


class SpareXdmaTransport(_SpareMemory,XdmaTransport):
    def __init__(self,profile:SparePcieProfile,dev='/dev/xdma0'):
        self.profile,self.calibration_data=profile,profile.core
        super().__init__(dev)
        try:self._check_image();self._initialize_memory()
        except BaseException:self.close();raise

    def reg_write(self,off,value):
        require(off!=R.R_MEMCAL+0x2000,'Global SoC reset CSR is unsupported')
        return super().reg_write(off,value)


def check_dual_host_evidence(profile):
    require(profile.data.get('host')==dict(interfaces=['pcie','jtag'],jtag_chain=2,
            jtag_max_hz=6000000,host_dma_hz=250000000),'Incorrect combined-host package configuration')
    model=json.loads((profile.package/'evidence/adapter-model.json').read_text())
    core=json.loads((profile.core/'variant-profile.json').read_text())
    require(model['status']=='PASS_SHARED_PIPELINED_NATIVE_CREDITS_ORDERING_AND_EXCLUSIVE_RMW' and
            len(model['reports'])==8 and digest(profile.package/'evidence/adapter-model.json')==core['adapter_model_sha256'],
            'Missing matching pipeline protocol evidence')
    selected=[v for n,v in model['sources'].items() if n.endswith('/spare_native_pipeline_shared.py')]
    require(selected==[core['adapter_source_sha256']] and
            digest(profile.package/'evidence/adapter-source.py')==selected[0],'Pipeline source binding differs')
    host=json.loads((profile.package/'evidence/dual-host-model.json').read_text())
    require(host['status']=='PASS_DUAL_HOST_RESET_AND_JTAG_AXI_ABORT_PROTOCOL' and len(host['reports'])==2,
            'Missing host reset/JTAG-abort model evidence')
    expected={'functional':'otpu_host_reset.sv','jtag-axi-abort':'otpu_jtag_axi_abort.sv'}
    require({r['case'] for r in host['reports']}==set(expected),'Host model cases differ')
    for row in host['reports']:
        name=expected[row['case']]
        hashes=[v for n,v in row['sources'].items() if Path(n).name==name]
        require(row['exit_code']==0 and hashes==[digest(profile.package/'evidence/dual-host'/name)],
                'Host RTL differs from the reviewed model: '+name)

    skew=host['registered_reset_skew_case']
    require(skew['exit_code']==0,'Registered reset skew regression missing')
    for name,status in (('bridge-model.json','PASS_ORIGINAL_BRIDGE_DEFECT_REPRODUCED_SHARED_PIPELINE_CORRECTION_VERIFIED'),
                        ('controller-model.json','PASS_SHARED_PIPELINE_REAL_LITEDRAM_CONTROLLER_BRIDGE_REGRESSION')):
        require(json.loads((profile.package/'evidence'/name).read_text())['status']==status,
                'Missing corrected adapter integration proof: '+name)


from .jtag import JtagTransport


class SpareJtagTransport(_SpareMemory,JtagTransport):
    """Exact-image USER2 transport; serial access is not a bandwidth proxy."""
    # _DualMemory validates ranges but returns no address. JtagTransport needs
    # the physical channel base, so preserve its static address calculation.
    _range=staticmethod(JtagTransport._range)

    @property
    def failed(self):
        return self._failed

    def __init__(self,profile,host='localhost',port=3721):
        self.profile,self.calibration_data=profile,profile.core
        super().__init__(host,port,calibration_data=profile.core)
        try:
            self._check_image()
            self._initialize_memory()
        except BaseException:
            self.close()
            raise

    def reg_write(self,off,value):
        require(off!=R.R_MEMCAL+0x2000,'Global SoC reset CSR is unsupported')
        return super().reg_write(off,value)
