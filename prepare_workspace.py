"""RunPod startup hook: persistent models, inputs and workflow, with no rendering."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(16 * 1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def signature(path, model):
    stat = path.stat()
    return {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'sha256': model['sha256']}


def ensure_model(model, root):
    target = root / model['directory'] / model['name']
    target.parent.mkdir(parents=True, exist_ok=True)
    receipt = target.with_name(target.name + '.h3-verified.json')
    if target.exists():
        try:
            if json.loads(receipt.read_text()) == signature(target, model) and target.stat().st_size == model['size']:
                print('Reusing verified model:', target.name, flush=True)
                return
        except (OSError, ValueError):
            pass
        if target.stat().st_size == model['size'] and digest(target) == model['sha256']:
            receipt.write_text(json.dumps(signature(target, model)))
            print('Verified existing model:', target.name, flush=True)
            return
        raise RuntimeError(f'Existing file does not match expected model: {target}. Move it aside before retrying; it was not overwritten.')

    partial = target.with_name(target.name + '.part')
    remaining = max(0, model['size'] - (partial.stat().st_size if partial.exists() else 0))
    if shutil.disk_usage(target.parent).free < remaining + 2 * 1024**3:
        raise RuntimeError(f'Insufficient persistent storage for {target.name}; need {remaining / 1e9:.2f} GB plus 2 GB free.')
    url = 'https://huggingface.co/{}/resolve/{}/{}'.format(
        model['repo'], model['revision'], urllib.parse.quote(model['filename'], safe='/'))
    print(f'Downloading {target.name} ({model["size"] / 1e9:.2f} GB) directly to RunPod...', flush=True)
    # Public model URLs. curl resumes .part files after interrupted pod startup.
    if not partial.exists() or partial.stat().st_size < model['size']:
        subprocess.run(['curl', '--fail', '--location', '--retry', '5', '--retry-delay', '5',
                        '--connect-timeout', '30', '--continue-at', '-', '--output', str(partial), url], check=True)
    if partial.stat().st_size != model['size'] or digest(partial) != model['sha256']:
        raise RuntimeError(f'Download checksum failed: {partial}. Kept for inspection; move it aside before retrying.')
    partial.replace(target)
    receipt.write_text(json.dumps(signature(target, model)))
    print('Download verified:', target.name, flush=True)


def main():
    comfy = pathlib.Path(sys.argv[1]).resolve()
    if not (comfy / 'main.py').is_file():
        raise RuntimeError('ComfyUI workspace has not been initialized')
    model_root = comfy / 'models'
    # Copy reference images only when absent; never overwrite a user's edits.
    for source in (ROOT / 'input').rglob('*.png'):
        destination = comfy / 'input' / source.relative_to(ROOT / 'input')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
    workflow = ROOT / 'EP01_SOL_FULL_6_GEN_CACHED_EXACT.json'
    destination = comfy / 'user/default/workflows/H3_PREPARED' / workflow.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(workflow, destination)
    for model in json.loads((ROOT / 'models.json').read_text()):
        ensure_model(model, model_root)
    # Cache compiled kernels on the volume. Reuse remains dependent on GPU,
    # source and runtime versions; this does not eliminate first-run warmup.
    print('H3 models and reference inputs ready. Starting ComfyUI.', flush=True)


if __name__ == '__main__':
    main()
