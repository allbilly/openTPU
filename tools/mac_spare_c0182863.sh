#!/usr/bin/env bash
# Run on the Mac with the flashed card connected through Chestnut.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
export PYTHONDONTWRITEBYTECODE=1
py="${SPARE_PYTHON:-python3}"
out="${SPARE_OUT:-build/mac-spare4gb-c0182863-1}"
pkg=runtime/c0182863
stage="${1:-lfm}"
case "$stage" in preflight|lfm|quick|full|memory|inference|bandwidth) ;; *) echo "usage: bash tools/mac_spare_c0182863.sh preflight|lfm|quick|full|memory|inference|bandwidth" >&2; exit 2;; esac
init_args=()
if [[ -n "${SPARE_EXPERIMENTAL_INIT_PAUSE_MS+x}" ]]; then
  [[ "$stage" == lfm ]] || { echo "SPARE_EXPERIMENTAL_INIT_PAUSE_MS requires the lfm stage." >&2; exit 2; }
  case "$SPARE_EXPERIMENTAL_INIT_PAUSE_MS" in
    0|5|20|50|200) init_args=(--experimental-init-pause-ms "$SPARE_EXPERIMENTAL_INIT_PAUSE_MS");;
    *) echo "Experimental initialization pause must be 0, 5, 20, 50 or 200 ms." >&2; exit 2;;
  esac
fi
if [[ "$stage" == preflight ]]; then
  "$py" tools/calibrate_spare_c0182863.py --package "$pkg" --reference-package "$pkg" \
    --firmware "$pkg/calibration" --preflight-only --out "$out/preflight"
  echo "Runtime files and firmware checked; no device opened."
  exit 0
fi

if [[ "$stage" == lfm ]]; then
  "$py" -c 'import json,sys,torch,transformers,safetensors; from opentpu.llm import model_dir; p=model_dir(sys.argv[1]); assert json.loads((p/"config.json").read_text()).get("model_type") in ("lfm2","lfm2_moe"), "LFM2 checkpoint required"; assert all((p/n).is_file() for n in ("tokenizer.json","tokenizer_config.json","model.safetensors")), "Incomplete local checkpoint"; print("LFM2 checkpoint:",p)' "${SPARE_MODEL:-lfm2}"
fi
if [[ "$stage" == quick || "$stage" == lfm ]]; then
  "$py" tools/run_lfm_spare_c0182863.py --package "$pkg" --transport chestnut --stage identity --out "$out/identity"
  "$py" tools/calibrate_spare_c0182863.py --package "$pkg" \
    --reference-package "$pkg" --firmware "$pkg/calibration" \
    --transport chestnut --out "$out/calibration"
  if [[ "$stage" == lfm ]]; then
    "$py" tools/run_lfm_spare_c0182863.py --package "$pkg" --transport chestnut --stage lfm \
      --calibration-receipt "$out/calibration/manifest.json" --model "${SPARE_MODEL:-lfm2}" \
      ${init_args[@]+"${init_args[@]}"} --out "$out/lfm"
  else
    "$py" tools/run_dma_spare_c0182863.py --package "$pkg" --transport chestnut --stage small \
      --calibration-receipt "$out/calibration/manifest.json" --out "$out/dma"
    "$py" tools/run_dma_spare_c0182863.py --package "$pkg" --transport chestnut --stage masked \
      --calibration-receipt "$out/calibration/manifest.json" --out "$out/native-masked"
  fi
else
  [[ -f "$out/calibration/manifest.json" ]] || { echo "Run quick first using this SPARE_OUT." >&2; exit 1; }
  if [[ "$stage" == bandwidth ]]; then
    "$py" tools/run_bandwidth_spare_c0182863.py --package "$pkg" --transport chestnut \
      --calibration-receipt "$out/calibration/manifest.json" --out "$out/bandwidth"
  elif [[ "$stage" == full ]]; then
    "$py" tools/run_dma_spare_c0182863.py --package "$pkg" --transport chestnut --stage full \
      --calibration-receipt "$out/calibration/manifest.json" --out "$out/full-dma"
  else
    "$py" tools/run_lfm_spare_c0182863.py --package "$pkg" --transport chestnut --stage "$stage" \
      --calibration-receipt "$out/calibration/manifest.json" --model "${SPARE_MODEL:-lfm2}" --out "$out/$stage"
  fi
fi
echo "Completed $stage. Keep all results under $out; report the manifests even if an earlier step fails."
