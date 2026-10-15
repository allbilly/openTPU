#!/usr/bin/env python3
"""Build the pinned openTPU XDMA driver locally; do not install or load it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/fedora-pcie"
REVISION = "b8466090b4e812e191da9e9305ffb11cb7ace768"
TAR_HASH = "d24487ada20d770d27bb83d0fb019c17636ab28e96780ce8ba10df56a2450675"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(url, path):
    if not path.exists():
        temp = path.with_suffix(".partial")
        subprocess.run(["curl", "--fail", "--location", "--retry", "2", url,
                        "-o", str(temp)], check=True)
        temp.rename(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", default=platform.release())
    parser.add_argument("--kernel-root", type=Path, help="use an existing kernel build tree")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.+-]+", args.kernel):
        parser.error("invalid kernel release")
    OUT.mkdir(parents=True, exist_ok=True)
    # A failed repeat must not leave an earlier successful build looking current.
    (OUT / "manifest.json").write_text(json.dumps({
        "status": "BUILDING", "kernel": args.kernel, "source_revision": REVISION,
        "physical_test": "NOT_RUN",
    }, indent=2) + "\n")
    archive = OUT / "xdma-source.tar.gz"
    download("https://api.github.com/repos/Xilinx/dma_ip_drivers/tarball/" + REVISION, archive)
    if sha(archive) != TAR_HASH:
        raise RuntimeError("Pinned XDMA archive hash mismatch")
    with tarfile.open(archive) as tar:
        src = OUT / "source" / tar.getnames()[0]
        if not src.exists():
            tar.extractall(OUT / "source", filter="data")
    patch = ROOT / "opentpu/host/pcie/xdma-otpu.patch"
    dry = subprocess.run(["patch", "--batch", "--forward", "--dry-run", "-p1", "-i", str(patch)],
                         cwd=src, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if dry.returncode == 0:
        subprocess.run(["patch", "--batch", "--forward", "-p1", "-i", str(patch)], cwd=src, check=True)
    else:
        subprocess.run(["patch", "--batch", "--dry-run", "-R", "-p1", "-i", str(patch)],
                       cwd=src, check=True, stdout=subprocess.DEVNULL)
    kernel = args.kernel_root or Path("/lib/modules") / args.kernel / "build"
    rpm_record = None
    if not kernel.is_dir():
        query = subprocess.check_output(["dnf", "repoquery", "--location",
                                        "kernel-devel-" + args.kernel], text=True)
        urls = [line.strip() for line in query.splitlines() if line.startswith("https://")]
        if len(urls) != 1:
            raise RuntimeError("Need one matching Fedora kernel-devel RPM or --kernel-root")
        rpm = OUT / ("kernel-devel-" + args.kernel + ".rpm")
        download(urls[0], rpm)
        with (OUT / "rpm-verify.log").open("w") as log:
            subprocess.run(["rpm", "-K", str(rpm)], stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        headers = OUT / "headers"
        kernel = headers / "usr/src/kernels" / args.kernel
        if not kernel.is_dir():
            headers.mkdir(exist_ok=True)
            process = subprocess.Popen(["rpm2cpio", str(rpm)], stdout=subprocess.PIPE)
            subprocess.run(["cpio", "-idm", "--quiet", "--no-absolute-filenames"],
                           stdin=process.stdout, cwd=headers, check=True)
            process.stdout.close()
            if process.wait():
                raise RuntimeError("RPM extraction failed")
        rpm_record = {"url": urls[0], "sha256": sha(rpm), "signature_check": "PASS"}
    driver = src / "XDMA/linux-kernel/xdma"
    # Use Fedora's compiler for its running kernel rather than a Homebrew compiler.
    env = os.environ.copy()
    env["PATH"] = "/usr/bin:/usr/sbin:/bin:/sbin:" + env.get("PATH", "")
    with (OUT / "driver-build.log").open("w") as log:
        subprocess.run(["make", "-C", str(kernel.resolve()), "M=" + str(driver),
                        "-j2", "modules"], env=env, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    module = driver / "xdma.ko"
    version = subprocess.check_output(["modinfo", "-F", "vermagic", str(module)], env=env, text=True).strip()
    tag = subprocess.check_output(["modinfo", "-F", "otpu", str(module)], env=env, text=True).strip()
    if not version.startswith(args.kernel + " ") or tag != "b846609.1":
        raise RuntimeError("Built XDMA module has wrong kernel or openTPU tag")
    record = {"status": "BUILT_NOT_INSTALLED_NOT_LOADED", "kernel": args.kernel,
              "source_revision": REVISION, "tar_sha256": sha(archive), "patch_sha256": sha(patch),
              "kernel_build_tree": str(kernel.resolve()),
              "kernel_rpm": rpm_record, "module": str(module), "module_sha256": sha(module),
              "vermagic": version, "otpu": tag}
    (OUT / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
