#!/usr/bin/env python3
"""Download pinned, checksum-verified checkpoints used by the Chestnut tests.

The hf download CLI stores checkpoints in ~/.cache/huggingface/hub. Symlinks in
ignored models/ let the benchmark tools use that shared cache without copies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINTS = {
    'lfm2': ('LiquidAI/LFM2.5-230M', 'LFM2.5-230M'),
    'qwen3': ('Qwen/Qwen3-0.6B', 'Qwen3-0.6B'),
    'qwen35': ('Qwen/Qwen3.5-0.8B', 'Qwen3.5-0.8B'),
    'lfm2-2.6b': ('LiquidAI/LFM2-2.6B', 'LFM2-2.6B'),
    'smollm3': ('HuggingFaceTB/SmolLM3-3B', 'SmolLM3-3B'),
    'phi4-mini': ('microsoft/Phi-4-mini-instruct', 'Phi-4-mini-instruct'),
    'qwen35-2b': ('Qwen/Qwen3.5-2B', 'Qwen3.5-2B'),
    'qwen35-4b': ('Qwen/Qwen3.5-4B', 'Qwen3.5-4B'),
    'gemma4': ('google/gemma-4-E2B', 'gemma-4-E2B'),
    'gemma4-e4b': ('google/gemma-4-E4B', 'gemma-4-E4B'),
    'lfm2.5-8b-a1b': ('LiquidAI/LFM2.5-8B-A1B', 'LFM2.5-8B-A1B'),
    'qwen35-35b-a3b': ('Qwen/Qwen3.5-35B-A3B', 'Qwen3.5-35B-A3B'),
}


def wanted(item):
    name = item['rfilename']
    return '/' not in name and (name.endswith(('.json', '.jinja', '.safetensors')) or name == 'LICENSE')


def verify(path, item):
    if not path.exists() or path.stat().st_size != item['size']:
        return False
    expected = item.get('lfs', {}).get('sha256')
    if expected:
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest() == expected
    if item.get('blobId'):
        data = path.read_bytes()
        return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == item['blobId']
    return True


def download(name, metadata_root, reserve_gib=2, cache_root=None):
    repo, folder = CHECKPOINTS[name]
    directory = ROOT/'models'/folder
    directory.mkdir(parents=True, exist_ok=True)
    cached = metadata_root/name/'metadata.json'
    if cached.exists():
        metadata = json.loads(cached.read_text())
        if metadata.get('repository') != repo:
            raise ValueError('Cached checkpoint repository mismatch')
    else:
        with urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'?blobs=true', timeout=45) as response:
            upstream = json.load(response)
        metadata = dict(name=name, repository=repo, revision=upstream['sha'], files=upstream['siblings'])
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(metadata, indent=2)+'\n')
    items = [item for item in metadata['files'] if wanted(item)]
    cache_root = Path(cache_root) if cache_root else Path.home()/'.cache/huggingface/hub'
    cache_root = cache_root.expanduser().resolve()
    repo_cache = cache_root/('models--'+repo.replace('/', '--'))
    snapshot = repo_cache/'snapshots'/metadata['revision']
    snapshot.mkdir(parents=True, exist_ok=True)
    # Reuse fully verified files already downloaded by this task. These are real
    # Hub blobs with their published hashes, hard-linked into the canonical cache.
    for item in items:
        local, cached_file = directory/item['rfilename'], snapshot/item['rfilename']
        if cached_file.exists() or not verify(local, item):
            continue
        blob_id = item.get('lfs', {}).get('sha256') or item['blobId']
        blob = repo_cache/'blobs'/blob_id
        blob.parent.mkdir(parents=True, exist_ok=True)
        if not blob.exists():
            try:
                blob.hardlink_to(local.resolve())
            except OSError:
                shutil.copyfile(local, blob)
        cached_file.symlink_to(os.path.relpath(blob, cached_file.parent))
    complete = {item['rfilename'] for item in items if verify(snapshot/item['rfilename'], item)}
    remaining = sum(item['size'] for item in items if item['rfilename'] not in complete)
    free = shutil.disk_usage(cache_root).free
    if remaining + reserve_gib*(1 << 30) > free:
        raise OSError(f'{name}: need {remaining/1e9:.2f} GB plus {reserve_gib} GiB reserve; '
                      f'only {free/1e9:.2f} GB free')
    executable = shutil.which('hf')
    if executable is None:
        raise RuntimeError('Install the Hugging Face hf CLI before downloading checkpoints')
    created = [item['rfilename'] for item in items if item['rfilename'] not in complete]
    subprocess.run([executable, 'download', repo, *[item['rfilename'] for item in items],
                    '--revision', metadata['revision'], '--cache-dir', str(cache_root)], check=True)
    for item in items:
        cached_file, local = snapshot/item['rfilename'], directory/item['rfilename']
        if not verify(cached_file, item):
            raise OSError('Checkpoint size/hash mismatch: '+item['rfilename'])
        if local.exists() and not verify(local, item):
            raise OSError('Existing model file differs from the pinned checkpoint: '+str(local))
        if local.exists() or local.is_symlink():
            local.unlink()
        local.symlink_to(cached_file)
    print(name, 'all requested files verified', flush=True)
    receipt = {**metadata, 'status': 'COMPLETE_VERIFIED', 'created_this_call': created}
    (directory/'download-metadata.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=CHECKPOINTS, required=True)
    parser.add_argument('--metadata-root', type=Path, default=ROOT/'build/chestnut-bench/catalog')
    parser.add_argument('--reserve-gib', type=int, default=2)
    parser.add_argument('--cache-dir', type=Path, default=Path.home()/'.cache/huggingface/hub')
    args = parser.parse_args()
    if args.reserve_gib < 0:
        parser.error('Reserve must be nonnegative')
    print(download(args.model, args.metadata_root, args.reserve_gib, args.cache_dir))


if __name__ == '__main__':
    main()
