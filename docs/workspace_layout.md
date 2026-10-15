# Workspace layout

The active OpenTPU checkout is `${OTPU_ROOT}` (`~/openTPU`). Shared
YPCB tooling and the other checkouts live under `${YPCB_ROOT}`.

```text
~/openTPU/                         active accelerator source and local build outputs
~/ypcb/
  dlc10-init.sh                    shared legacy DLC10 initialization wrapper
  openFPGALoader/                  separate upstream clone with local driver changes
  firmware/                       local firmware; excluded from this tooling repository
  ref/                            existing reference clones
  projects/                       other checkouts moved from the former workspace root
    bonetto-soc/
    inspur-adventures/
    ypcb_00338_1p1_hack/
    openTPU-upstream-e15b4a44/      linked OpenTPU worktree
    openTPU -> ~/openTPU           compatibility entry
  local-overrides/                 source changes for the separate local repositories
  migration-receipts/              local migration evidence and recovery copies
```

The legacy `~/ypcb_ref` entry is a compatibility symlink to
`${YPCB_ROOT}/projects`. Its `openTPU` entry points to `~/openTPU`.
Current scripts and documentation use the new canonical locations. Keep the
compatibility entries: frozen build commands, Python virtual-environment
launchers and hashed receipts still refer to their original absolute paths.
Those generated records were preserved without rewriting their contents.

## Portable paths and external tools

Run OpenTPU commands from the checkout root. Documentation uses these variables
for local paths rather than embedding a developer's username:

```bash
export OTPU_ROOT="$(git rev-parse --show-toplevel)"
export OTPU_WORKSPACE_ROOT="$(dirname "$OTPU_ROOT")"
export YPCB_ROOT="${YPCB_ROOT:-$OTPU_WORKSPACE_ROOT/ypcb}"
```

Python helpers derive the checkout root from their own file. Vivado is found
on `PATH`, or through `OTPU_VIVADO_BIN`/`VIVADO_BIN` (the executable directory)
or `VIVADO_ROOT`/`XILINX_VIVADO` (the installation root). Set `VIVADO_ROOT` to
your installation before sourcing `"$VIVADO_ROOT/settings64.sh"` if needed.
Yosys uses `PATH` or `OTPU_YOSYS`; its data directory and Slang plugin can be
supplied with `OTPU_YOSYS_SHARE` and `OTPU_SLANG`.

Experimental donor tools use the configured `OTPU_WORKSPACE_ROOT` and
`YPCB_ROOT`. These identify optional neighbouring checkouts; they are not
required to use the already-flashed PCIe image on another Linux PC. Historical
cross-checkout build evidence is shown as local variable-based paths; it is
not included in Git. Published source and current documentation contain no
fixed developer home directory.

The directory moves were atomic on the same filesystem. Git HEADs, tracked
and untracked source hashes, linked-worktree access, virtual-environment
imports and the identities of the retained OpenXC7 processes were checked.
Local details are in `~/ypcb/migration-receipts/current.json`.

## Git repositories and transfer

OpenTPU's `origin` points to `allbilly/openTPU`; `upstream` retains
`FeSens/openTPU`. The local
checkpoint branch is `ypcb/ch1-bringup`, based on the exact source used
for this bring-up. Upstream main has advanced; this checkpoint does not merge
those changes into the verified local design.
Only the local remotes are configured. Creating the GitHub repositories,
authentication and pushing are left to the user.

The separate `allbilly/ypcb` tooling repository records the shared scripts,
patches, layout and local overrides. Nested project clones keep their own Git
histories. The two copies of some reference repositories have differing local
changes and remain separate.

Git excludes OpenTPU's `build/`, model checkpoints and Python environment.
The [bitstream index](bitstreams.md) lists the local generated files and hashes.
The matched host/model archive for the other Linux PC is
`~/openTPU/build/fedora-vivado/ch1-pcie-flash-host-20261015.tar`; transfer it
separately. A Git clone alone does not contain that archive or model weights.
Use the [PCIe host instructions](permanent_pcie_ch1.md#pcie-host-pc) on the
PC containing the card. The flashed FPGA design is already stored on the card.
