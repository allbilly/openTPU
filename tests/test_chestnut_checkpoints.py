"""Keep downloaded models in the shared HF cache and verify their contents."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import chestnut_checkpoints as C


def metadata(tmp_path):
    data = b'full checkpoint bytes'
    item = dict(rfilename='model.safetensors', size=len(data),
                lfs={'sha256': hashlib.sha256(data).hexdigest()})
    root = tmp_path/'metadata'
    (root/'lfm2').mkdir(parents=True)
    meta = dict(repository='LiquidAI/LFM2.5-230M', revision='a'*40, files=[item])
    (root/'lfm2/metadata.json').write_text(json.dumps(meta))
    return root, meta, item, data


@pytest.mark.parametrize('relative_cache', [False, True])
def test_hf_download_uses_shared_cache_and_models_only_links_to_it(tmp_path, monkeypatch, relative_cache):
    root, meta, item, data = metadata(tmp_path)
    cache = tmp_path/'cache'
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(C, 'ROOT', tmp_path/'repo')
    monkeypatch.setattr(C.shutil, 'which', lambda name: '/bin/hf')
    calls = []
    def download(command, check):
        calls.append(command)
        target = cache/'models--LiquidAI--LFM2.5-230M/snapshots'/meta['revision']/item['rfilename']
        target.write_bytes(data)
    monkeypatch.setattr(C.subprocess, 'run', download)
    directory = C.download('lfm2', root, 0, Path('cache') if relative_cache else cache)
    assert calls[0][:3] == ['/bin/hf', 'download', 'LiquidAI/LFM2.5-230M']
    assert '--local-dir' not in calls[0]
    assert calls[0][calls[0].index('--cache-dir')+1] == str(cache)
    link = directory/item['rfilename']
    assert link.is_symlink() and link.read_bytes() == data
    assert link.resolve().is_relative_to(cache)


def test_corrupt_download_is_rejected_before_creating_model_link(tmp_path, monkeypatch):
    root, meta, item, data = metadata(tmp_path)
    cache = tmp_path/'cache'
    monkeypatch.setattr(C, 'ROOT', tmp_path/'repo')
    monkeypatch.setattr(C.shutil, 'which', lambda name: '/bin/hf')
    def download(command, check):
        target = cache/'models--LiquidAI--LFM2.5-230M/snapshots'/meta['revision']/item['rfilename']
        target.write_bytes(b'x'*len(data))
    monkeypatch.setattr(C.subprocess, 'run', download)
    with pytest.raises(OSError, match='hash mismatch'):
        C.download('lfm2', root, 0, cache)
    assert not (C.ROOT/'models/LFM2.5-230M/model.safetensors').exists()


def test_existing_verified_model_is_seeded_without_copying_weights(tmp_path, monkeypatch):
    root, meta, item, data = metadata(tmp_path)
    cache = tmp_path/'cache'
    monkeypatch.setattr(C, 'ROOT', tmp_path/'repo')
    local = C.ROOT/'models/LFM2.5-230M/model.safetensors'
    local.parent.mkdir(parents=True)
    local.write_bytes(data)
    original_inode = local.stat().st_ino
    monkeypatch.setattr(C.shutil, 'which', lambda name: '/bin/hf')
    monkeypatch.setattr(C.subprocess, 'run', lambda *args, **kwargs: None)
    C.download('lfm2', root, 0, cache)
    assert local.is_symlink() and local.stat().st_ino == original_inode
    assert local.resolve().is_relative_to(cache)
