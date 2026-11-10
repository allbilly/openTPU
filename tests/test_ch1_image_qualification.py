"""Offline evidence gates must bind the core inventory and exact MMCM clock."""
import json
import math
from pathlib import Path

import pytest

from tools import fedora_qualify_ch1_image as Q

CORE_FILES = {'verilog': 'otpu_litedram.v', 'xdc': 'otpu_litedram.xdc',
              'rom': 'otpu_litedram_mem.init', 'csr': 'csr.csv', 'init': 'sdram_init.py'}


def save_json(path, value):
    path.write_text(json.dumps(value))


def entry(directory, name):
    item = Q.describe(directory/name)
    item.pop('path')
    return dict(name=name, **item)


@pytest.fixture
def release_files(tmp_path):
    release, build = tmp_path/'release', tmp_path/'build'
    core = release/'core'
    frozen = build/'source/boards/ypcb-00338/litedram'
    for path in (core, release/'evidence', frozen):
        path.mkdir(parents=True)
    for name in (*CORE_FILES.values(), 'openxc7-profile.json'):
        (core/name).write_text('fixture '+name+'\n')
        (frozen/name).write_bytes((core/name).read_bytes())
    (release/'otpu.bit').write_bytes(b'reference bit fixture')
    review = dict(status='CH1_PCIE_IMAGE_PACKET_CRC_PINS_ROUTE_TIMING_PASS_CDC_REVIEW_PENDING',
                  ecc=dict(scope='Full four-port stock comparison'),
                  bitstream=Q.describe(release/'otpu.bit'))
    save_json(release/'evidence/offline-image-review.json', review)
    manifest = dict(compute=Q.FULL, memory=dict(physical_user_channels=[1],
                    logical_capacity_bytes=1 << 31, virtual_channel_bytes=1 << 30,
                    ddr_mts=800, ecc=True), files=[entry(release, str(p.relative_to(release)))
                    for p in sorted(release.rglob('*')) if p.is_file()])
    save_json(release/'manifest.json', manifest)
    return release, build, manifest


def test_release_reuse_matches_all_six_core_files(release_files):
    release, build, _ = release_files
    result = Q.matched_release_memory(release, build, dict(profile=Q.FULL))
    assert {item['name'] for item in result['matched_core_files']} == {
        'core/'+name for name in (*CORE_FILES.values(), 'openxc7-profile.json')}


@pytest.mark.parametrize('change', ['duplicates', 'omit-rtl', 'substitute-rtl',
                                    'omit-bit', 'omit-review', 'duplicate-review'])
def test_release_reuse_rejects_incomplete_or_ambiguous_inventory(release_files, change):
    release, build, manifest = release_files
    files = manifest['files']
    if change == 'duplicates':
        csr = next(item for item in files if item['name'] == 'core/csr.csv')
        manifest['files'] = [item for item in files if not item['name'].startswith('core/')] + [csr]*6
        (release/'core/otpu_litedram.v').unlink()
        (build/'source/boards/ypcb-00338/litedram/otpu_litedram.v').unlink()
    elif change == 'duplicate-review':
        files.append(next(item for item in files if item['name'] == 'evidence/offline-image-review.json'))
    else:
        name = {'omit-rtl':'core/otpu_litedram.v', 'substitute-rtl':'core/otpu_litedram.v',
                'omit-bit':'otpu.bit', 'omit-review':'evidence/offline-image-review.json'}[change]
        manifest['files'] = [item for item in files if item['name'] != name]
        if change == 'substitute-rtl':
            (release/'core/unrelated.txt').write_text('not the memory implementation')
            manifest['files'].append(entry(release, 'core/unrelated.txt'))
    save_json(release/'manifest.json', manifest)
    with pytest.raises(ValueError, match='Duplicate|Incomplete|must be hashed'):
        Q.matched_release_memory(release, build, dict(profile=Q.FULL))


@pytest.mark.parametrize('change', ['core', 'review', 'historical-bit'])
def test_release_reuse_rejects_changed_or_misbound_evidence(release_files, change):
    release, build, manifest = release_files
    if change == 'core':
        (build/'source/boards/ypcb-00338/litedram/otpu_litedram.v').write_text('different core')
    else:
        path = release/'evidence/offline-image-review.json'
        review = json.loads(path.read_text())
        review['bitstream']['sha256'] = '0'*64
        save_json(path, review)
        if change == 'historical-bit':
            manifest['files'] = [entry(release, item['name']) for item in manifest['files']]
            save_json(release/'manifest.json', manifest)
    with pytest.raises(ValueError, match='differs|changed|another image'):
        Q.matched_release_memory(release, build, dict(profile=Q.FULL))


def test_local_historical_release_inventory_still_passes(tmp_path):
    release = Q.ROOT/'bitstreams/ch1-pcie-2gb'
    manifest = json.loads((release/'manifest.json').read_text())
    if any(not (release/item['name']).is_file() for item in manifest['files']):
        pytest.skip('Optional historical replay needs locally retained release artifacts')
    frozen = tmp_path/'source/boards/ypcb-00338'
    frozen.mkdir(parents=True)
    (frozen/'litedram').symlink_to(release/'core', target_is_directory=True)
    result = Q.matched_release_memory(release, tmp_path, dict(profile=Q.FULL))
    assert result['historical_ecc']['scope'] == 'Full four-port stock comparison'
    assert len(result['matched_core_files']) == 6


@pytest.fixture
def dual_files(tmp_path):
    generation, ecc, build = tmp_path/'generation', tmp_path/'ecc', tmp_path/'build'
    core = generation/'core'
    generator, tested = generation/'generator', ecc/'generator'
    frozen = build/'source/boards/ypcb-00338/litedram'
    for path in (core, generator, tested, frozen):
        path.mkdir(parents=True)
    for name in CORE_FILES.values():
        (core/name).write_text('fixture '+name+'\n')
        (frozen/name).write_bytes((core/name).read_bytes())
    profile = dict(parameters=dict(CORE_KHZ=100000, DDR_MTS=800),
                   physical_user_channels=[0, 1],
                   files={key:entry(core, name) for key, name in CORE_FILES.items()})
    save_json(core/'openxc7-profile.json', profile)
    (generator/'ecc_ports.py').write_text('# fixture ECC implementation\n')
    (tested/'ecc_ports.py').write_bytes((generator/'ecc_ports.py').read_bytes())
    test = '\n'.join(['range(2)']*7+['pend = [[], []]', 'rnd.choice([None, None, 0, 1])'])
    (generator/'ecc_ports_check.py').write_text(test)
    (tested/'ecc_ports_check.py').write_text(test.replace('range(2)', 'range(4)').replace(
        'pend = [[], []]', 'pend = [[], [], [], []]').replace(
        'rnd.choice([None, None, 0, 1])', 'rnd.choice([None, None, 0, 1, 2, 3])'))
    save_json(generation/'manifest.json', dict(status='GENERATED_PROFILE_PASS_IMPLEMENTATION_NOT_RUN',
        source={str(path):Q.describe(path)['sha256'] for path in generator.iterdir()}))
    return generation, ecc, build, profile


def test_dual_generation_matches_all_five_core_files(dual_files):
    generation, ecc, build, _ = dual_files
    result = Q.matched_dual_generation(generation, ecc, build)
    assert {Path(item['path']).name for item in result['matched_core_files']} == set(CORE_FILES.values())


@pytest.mark.parametrize('change', ['duplicates', 'omit-rtl', 'substitute-rtl', 'implemented-rtl', 'ecc-source'])
def test_dual_generation_rejects_incomplete_or_changed_sources(dual_files, change):
    generation, ecc, build, profile = dual_files
    if change == 'duplicates':
        profile['files'] = {str(i):profile['files']['csr'] for i in range(5)}
        (generation/'core/otpu_litedram.v').unlink()
        (build/'source/boards/ypcb-00338/litedram/otpu_litedram.v').unlink()
    elif change == 'omit-rtl':
        del profile['files']['verilog']
    elif change == 'substitute-rtl':
        profile['files']['verilog']['name'] = 'unrelated.txt'
    elif change == 'implemented-rtl':
        (build/'source/boards/ypcb-00338/litedram/otpu_litedram.v').write_text('different implementation')
    else:
        (ecc/'generator/ecc_ports.py').write_text('different tested ECC')
    save_json(generation/'core/openxc7-profile.json', profile)
    with pytest.raises(ValueError, match='Duplicate|Incomplete|differs'):
        Q.matched_dual_generation(generation, ecc, build)


def clock_manifest(requested):
    divide = math.floor(800/requested*8+.5)/8
    actual = 800/divide
    clock = dict(requested_mhz=requested, output_divide=divide, actual_mhz=actual,
                 actual_hz=math.floor(actual*1e6), core_khz=math.floor(actual*1000+.5), vco_mhz=800)
    return dict(profile=dict(Q.FULL, CORE_KHZ=clock['core_khz']), compute_clock=clock)


@pytest.mark.parametrize('requested', [6.25, 6.33, 7, 100, 133.33, 150, 800])
def test_routed_clock_uses_exact_ratio_not_rounded_register(requested):
    manifest = clock_manifest(requested)
    khz = manifest['profile']['CORE_KHZ']
    exact_period = 1.25*manifest['compute_clock']['output_divide']
    clocks = dict(core_clk_otpu_bd_clk_wiz_0_0=exact_period, crg_s7mmcm_clkout=10.)
    assert Q.compute_period_ns(manifest, khz) == exact_period
    Q.check_clock_periods(clocks, manifest, khz)
    clocks['core_clk_otpu_bd_clk_wiz_0_0'] += .002
    with pytest.raises(ValueError, match='Implemented clock period differs'):
        Q.check_clock_periods(clocks, manifest, khz)


@pytest.mark.parametrize('field,value', [('core_khz', 6331), ('actual_mhz', 6.33),
    ('actual_hz', 6330000), ('output_divide', 126.5), ('vco_mhz', 799),
    ('requested_mhz', 7), ('actual_mhz', float('nan')), ('actual_hz', True)])
def test_exact_clock_metadata_must_agree_with_request_and_register(field, value):
    manifest = clock_manifest(6.33)
    manifest['compute_clock'][field] = value
    with pytest.raises(ValueError, match='clock|MMCM'):
        Q.compute_period_ns(manifest, 6330)


def test_historical_fixed_clock_is_supported_but_unknown_rounding_is_not():
    manifest = dict(profile=Q.FULL)
    Q.check_clock_periods(dict(core_clk_otpu_bd_clk_wiz_0_0=10., crg_s7mmcm_clkout=10.), manifest, 100000)
    with pytest.raises(ValueError, match='metadata is missing'):
        Q.compute_period_ns(dict(profile=dict(Q.FULL, CORE_KHZ=6330)), 6330)
    with pytest.raises(ValueError, match='Implemented clock period differs'):
        Q.check_clock_periods(dict(core_clk_otpu_bd_clk_wiz_0_0=10., crg_s7mmcm_clkout=10.002), manifest, 100000)
