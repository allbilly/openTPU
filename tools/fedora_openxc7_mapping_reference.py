#!/usr/bin/env python3
"""Run the complete static reference pipeline with pinned mapping-adoption evidence."""
import json
from pathlib import Path
import fedora_resume_openxc7_reference as reference
import fedora_openxc7_static_reference as static
from fedora_openxc7_pcie_pipeline import recorded
HERE=Path(__file__).resolve()

def main():
 original_select=reference.select_jtag_backend
 def select(selection):
  backend,gates,inventory=original_select(selection)
  info=json.loads(Path(selection).read_text())
  evidence=info.get('mapping_provenance')
  if not evidence:raise RuntimeError('Missing full mapping adoption evidence')
  for item in evidence:
   recorded(item);inventory[item['path']]=item['sha256']
  inventory[str(HERE)]=reference.digest(HERE)
  return backend,gates,inventory
 reference.select_jtag_backend=select
 return static.controller()
if __name__=='__main__':raise SystemExit(main())
