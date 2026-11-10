#!/usr/bin/env bash
# Local preparation and explicit hardware steps; use the repo's existing tools.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
venv="$root/build/fedora-venv"
ypcb_root="${YPCB_ROOT:-$(dirname "$root")/ypcb}"
action="${1:-check}"
if (($#)); then shift; fi
cd "$root"

has_profile_argument() {
  local option
  for option in "$@"; do
    case "$option" in --litedram-core|--litedram-core=*|-h|--help) return 0;; esac
  done
  return 1
}

selected_core() {
  python3 - "$root" <<'PY'
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1])
sys.path.insert(0, str(root/'tools'))
from fedora_prepare_litedram import profile

try:
    explicit = os.environ.get('OTPU_LITEDRAM_CORE')
    if explicit:
        selected = profile(Path(explicit))
    else:
        active = json.loads((root/'build/fedora-openxc7/ddr800-pipeline-active.json').read_text())
        pipeline = json.loads(Path(active['manifest']).read_text())
        selected = profile(Path(pipeline['litedram_core']))
        expected = {key:pipeline['configuration'][key] for key in ('CORE_KHZ', 'DDR_MTS')}
        if selected['parameters'] != expected or expected['DDR_MTS'] != 800:
            raise ValueError('Selected profile does not match the DDR800 build')
    print(selected['data'])
except (OSError, ValueError, KeyError, RuntimeError) as error:
    raise SystemExit('Cannot select the checked DDR profile: '+str(error)+
                     '\nPass --litedram-core or set OTPU_LITEDRAM_CORE to a generated core directory.')
PY
}

use_selected_backend() {
  # Explicit caller overrides retain the low-level helper's existing behavior.
  if [[ -n "${OTPU_NEXTPNR:-}" || -n "${OTPU_NEXTPNR_SOURCE:-}" ]]; then
    return
  fi
  local selection
  selection="$(python3 - "$root" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
sys.path.insert(0, str(root/'tools'))
from fedora_openxc7 import digest

def checked(item):
    p = Path(item['path'])
    if p.stat().st_size != item['bytes'] or digest(p) != item['sha256']:
        raise ValueError('Selected artifact changed: '+str(p))
    return p

try:
    active = json.loads((root/'build/fedora-openxc7/implementation-active.json').read_text())
    pipeline = json.loads(Path(active['pipeline_manifest']).read_text())
    expected = dict(MCOLS=4, ACT_ROWS=4, LANES=8, VPU_CL=2, MXU_IMPL=2,
                    CORE_KHZ=100000, DDR_MTS=800)
    if pipeline['configuration'] != expected:
        raise ValueError('Selected pipeline is not the full DDR800 accelerator')
    selected = pipeline['corrected_backend']
    for name in ('carry_probe', 'cascade_probe', 'upper_carry_probe'):
        gate = pipeline[name]
        if gate['status'] not in ('CARRY_ROUTE_EQUIVALENCE_AND_STRICT_FRAMES_PASS',
                                 'PROBE_ROUTE_AND_STRICT_FRAMES_PASS_NUMERICAL_TIMING_NOT_QUALIFIED'):
            raise ValueError('Selected correction gate did not pass: '+name)
        probe = json.loads(checked(gate['manifest']).read_text())
        checked(gate['strict_frames'])
        if probe['binary'] != selected['binary']:
            raise ValueError('Selected probe tested a different backend: '+name)
    backend = json.loads(checked(selected['manifest']).read_text())
    if backend['binary'] != selected['binary'] or backend['source'] != selected['source']:
        raise ValueError('Selected backend metadata differs')
    binary = checked(backend['binary'])
    inventory = json.loads(checked(backend['source_inventory']).read_text())
    source = Path(backend['source'])
    for relative, expected_hash in inventory.items():
        if digest(source/relative) != expected_hash:
            raise ValueError('Selected backend source changed: '+relative)
    if '\n' in str(binary) or '\n' in str(source):
        raise ValueError('Unsupported newline in selected paths')
    print(binary)
    print(source)
except (OSError, ValueError, KeyError, RuntimeError) as error:
    raise SystemExit('Cannot select the verified openXC7 backend: '+str(error)+
                     '\nSet explicit OTPU_NEXTPNR and OTPU_NEXTPNR_SOURCE for another backend.')
PY
)"
  local -a backend_paths
  mapfile -t backend_paths <<<"$selection"
  [[ ${#backend_paths[@]} == 2 ]] || { echo 'Invalid selected backend paths' >&2; return 2; }
  export OTPU_NEXTPNR="${backend_paths[0]}"
  export OTPU_NEXTPNR_SOURCE="${backend_paths[1]}"
}

program_sram() {
  local bit="$1"
  shift
  [[ -f "$bit" ]] || { echo "Missing OpenTPU bitstream: $bit" >&2; return 2; }
  local init_log
  init_log="$(mktemp "${TMPDIR:-/tmp}/opentpu-sram-init.XXXXXX")"
  echo "SRAM initialization log: $init_log"
  bash "$ypcb_root/dlc10-init.sh" | tee "$init_log"
  python3 tools/fedora_check_jtag_chain.py --init-log "$init_log"
  if (($#)); then
    # Cable initialization takes time. Recheck the exact completed native image
    # before passing it to the loader, as well as before accessing the cable.
    local verified
    verified="$(python3 tools/fedora_check_native_image.py --emit-bit "$@")"
    [[ "$verified" == "$bit" ]] || { echo 'Native image selection changed' >&2; return 2; }
  fi
  exec "${YPCB_LOADER:-$ypcb_root/openFPGALoader/build-xpcu-debug/openFPGALoader}" \
    --cable xilinxPlatformCableUsb --freq 6000000 --index-chain 0 "$bit"
}

case "$action" in
  setup)
    python3 -m venv "$venv"
    "$venv/bin/python" -m pip install --no-compile -e . pytest
    "$venv/bin/python" -m pip install --no-compile --index-url https://download.pytorch.org/whl/cpu torch
    "$venv/bin/python" -m pip install --no-compile transformers safetensors
    "$venv/bin/python" -m pip check
    "$venv/bin/python" -m pip freeze > "$root/build/fedora-python-requirements.txt"
    ;;
  check)
    "$venv/bin/python" -m pip check
    "$venv/bin/otpu-smi" --help >/dev/null
    "$venv/bin/otpu-selftest" --help >/dev/null
    "$venv/bin/otpu-diag" --help >/dev/null
    use_selected_backend
    core_directory="$(selected_core)"
    python3 tools/fedora_openxc7.py check --litedram-core "$core_directory"
    printf 'FPGA image: '
    if [[ -f "${BIT:-$root/build/vivado/otpu.bit}" ]]; then
      sha256sum "${BIT:-$root/build/vivado/otpu.bit}"
    else
      echo 'not built'
    fi
    "$venv/bin/otpu-setup" --check
    ;;
  lint)
    PATH="$venv/bin:$PATH" make -C boards/ypcb-00338 lint
    ;;
  sim)
    # Real Verilator board model, no --fake and no physical-card claim.
    # Reduce host C++ compilation time; this is not a simulator performance run.
    export MAKEFLAGS="${MAKEFLAGS:-} ${OTPU_SIM_MAKEFLAGS:---load-average=4 OPT_FAST=-O0 OPT_SLOW=-O0 OPT_GLOBAL=-O0}"
    exec "$venv/bin/otpu-selftest" --sim --bw-mib 1 "$@"
    ;;
  build)
    echo 'Building the standalone OpenTPU accelerator + dual LiteDRAM with openXC7.'
    echo 'This stage produces a synthesis netlist; placement, timing and frame assembly follow.'
    if ! has_profile_argument "$@"; then
      core_directory="$(selected_core)"
      set -- --litedram-core "$core_directory" "$@"
    fi
    exec python3 tools/fedora_openxc7.py jtag-synth --abc-fast "$@"
    ;;
  openxc7)
    if (($# == 0)); then set -- check; fi
    case "$1" in check|jtag-route) use_selected_backend;; esac
    if [[ "$1" == check ]] && ! has_profile_argument "$@"; then
      core_directory="$(selected_core)"
      set -- "$1" --litedram-core "$core_directory" "${@:2}"
    fi
    exec python3 tools/fedora_openxc7.py "$@"
    ;;
  jtag)
    if ! has_profile_argument "$@"; then
      core_directory="$(selected_core)"
      set -- --litedram-core "$core_directory" "$@"
    fi
    exec "$venv/bin/python" tools/fedora_jtag.py "$@"
    ;;
  xvc-build)
    exec python3 tools/fedora_prepare_xvc.py "$@"
    ;;
  jtag-server)
    exec python3 tools/fedora_xvc_server.py "$@"
    ;;
  build-vivado)
    if ! command -v vivado >/dev/null && [[ -z "${VIVADO_DOCKER:-}" ]]; then
      echo 'Full Vivado with an xc7k480t license is required. Source its settings64.sh first.' >&2
      exit 2
    fi
    PATH="$venv/bin:$PATH" make -C boards/ypcb-00338 bit "$@"
    ;;
  program)
    # Volatile FPGA SRAM only; the existing DLC10 initializer checks IDCODE.
    program_sram "${BIT:-$root/build/vivado/otpu.bit}"
    ;;
  native-check)
    exec python3 tools/fedora_check_native_image.py "$@"
    ;;
  program-vivado)
    [[ $# == 2 && "$1" == --manifest ]] || {
      echo 'usage: program-vivado --manifest COMPLETED_NATIVE_MANIFEST' >&2; exit 2;
    }
    bit="$(python3 tools/fedora_check_native_image.py --emit-bit "$@")"
    program_sram "$bit" "$@"
    ;;
  pcie)
    # Run when the card is physically installed in a suitable PCIe host.
    exec "$venv/bin/otpu-setup" "$@"
    ;;
  selftest)
    exec "$venv/bin/otpu-selftest" "$@"
    ;;
  diag)
    exec "$venv/bin/otpu-diag" "$@"
    ;;
  *)
    echo "usage: $0 {setup|check|lint|sim|build|openxc7|jtag|xvc-build|jtag-server|build-vivado|program|native-check|program-vivado|pcie|selftest|diag} [args]" >&2
    exit 2
    ;;
esac
