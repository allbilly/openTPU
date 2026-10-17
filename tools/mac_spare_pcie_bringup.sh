#!/usr/bin/env bash
# Run on the Mac with the flashed card connected through Chestnut.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
export PYTHONDONTWRITEBYTECODE=1
py="${SPARE_PYTHON:-python3}"
out="${SPARE_OUT:-build/mac-spare4gb-1}"
pkg=bitstreams/spare-pcie-4gb-ddr800
stage="${1:-quick}"
case "$stage" in lfm|quick|full|memory|inference) ;; *) echo "usage: bash tools/mac_spare_pcie_bringup.sh lfm|quick|full|memory|inference" >&2; exit 2;; esac
if [[ "$stage" == lfm ]]; then
  "$py" -c 'import json,sys,torch,transformers,safetensors; from opentpu.llm import model_dir; p=model_dir(sys.argv[1]); assert json.loads((p/"config.json").read_text()).get("model_type") in ("lfm2","lfm2_moe"), "LFM2 checkpoint required"; assert all((p/n).is_file() for n in ("tokenizer.json","tokenizer_config.json","model.safetensors")), "Incomplete local checkpoint"; print("LFM2 checkpoint:",p)' "${SPARE_MODEL:-lfm2}"
fi
if [[ "$stage" == quick || "$stage" == lfm ]]; then
  "$py" tools/run_spare_pcie_lfm2.py --package "$pkg" --transport chestnut --stage identity --out "$out/identity"
  "$py" tools/run_spare_pcie_calibration.py --package "$pkg" \
    --reference-package bitstreams/ramtest-litedram-ddr800-spare8 --firmware "$pkg/calibration" \
    --transport chestnut --out "$out/calibration"
  if [[ "$stage" == lfm ]]; then
    "$py" tools/run_spare_pcie_lfm2.py --package "$pkg" --transport chestnut --stage lfm \
      --calibration-receipt "$out/calibration/manifest.json" --model "${SPARE_MODEL:-lfm2}" --out "$out/lfm"
  else
    "$py" tools/run_spare_pcie_dma.py --package "$pkg" --transport chestnut --stage small \
      --calibration-receipt "$out/calibration/manifest.json" --out "$out/dma"
    "$py" tools/run_spare_pcie_dma.py --package "$pkg" --transport chestnut --stage masked \
      --calibration-receipt "$out/calibration/manifest.json" --out "$out/native-masked"
  fi
else
  [[ -f "$out/calibration/manifest.json" ]] || { echo "Run quick first using this SPARE_OUT." >&2; exit 1; }
  if [[ "$stage" == full ]]; then
    "$py" tools/run_spare_pcie_dma.py --package "$pkg" --transport chestnut --stage full \
      --calibration-receipt "$out/calibration/manifest.json" --out "$out/full-dma"
  else
    "$py" tools/run_spare_pcie_lfm2.py --package "$pkg" --transport chestnut --stage "$stage" \
      --calibration-receipt "$out/calibration/manifest.json" --model "${SPARE_MODEL:-lfm2}" --out "$out/$stage"
  fi
fi
echo "Completed $stage. Keep all results under $out; report the manifests even if an earlier step fails."
