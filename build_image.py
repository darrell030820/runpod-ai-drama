"""Runs inside the Docker build, never on the user's PC."""
import hashlib
import importlib.metadata
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path('/opt/h3-setup')
BAKED = pathlib.Path('/opt/comfyui-baked')
VENV = pathlib.Path('/opt/h3-venv')


def run(*args):
    subprocess.run([str(x) for x in args], check=True)


def patch_start(source, node_names):
    """Fail closed if the pinned base's startup contract changes."""
    lines = source.splitlines()
    lines.insert(1, 'mkdir -p /workspace/runpod-slim')
    def replace_prefix(prefix, replacement):
        positions = [i for i, line in enumerate(lines) if line.startswith(prefix)]
        if len(positions) != 1:
            raise RuntimeError(f'Unexpected base start.sh: {prefix}')
        lines[positions[0]] = replacement
    replace_prefix('VENV_DIR=', 'VENV_DIR="/opt/h3-venv"')
    existing = next(line for line in lines if line.startswith('BAKED_NODES=('))
    names = sorted(set(re.findall(r'"([^"]+)"', existing)) | set(node_names))
    replace_prefix('BAKED_NODES=(', 'BAKED_NODES=(' + ' '.join(json.dumps(n) for n in names) + ')')
    launch = 'python main.py $FIXED_ARGS &'
    if lines.count(launch) != 1:
        raise RuntimeError('Unexpected ComfyUI launch command in base image')
    index = lines.index(launch)
    lines[index:index] = [
        'python /opt/h3-setup/prepare_workspace.py "$COMFYUI_DIR"',
        'python /opt/h3-setup/check_nodes.py --wait 900 > /workspace/runpod-slim/h3-readiness.log 2>&1 &',
    ]
    return '\n'.join(lines) + '\n'


def clone(item, path):
    path.mkdir(parents=True)
    run('git', '-C', path, 'init', '--quiet')
    run('git', '-C', path, 'remote', 'add', 'origin', 'https://github.com/' + item['repo'] + '.git')
    run('git', '-C', path, 'fetch', '--depth=1', 'origin', item['revision'])
    run('git', '-C', path, 'checkout', '--detach', 'FETCH_HEAD')


def main():
    if sys.platform != 'linux' or not BAKED.is_dir():
        raise RuntimeError('Run this only through the supplied Dockerfile')
    start = pathlib.Path('/start.sh')
    reference = ROOT / 'base-start.sh.reference'
    if start.read_bytes() != reference.read_bytes():
        raise RuntimeError('Base startup differs from audited 1.4.7 image')
    repos = json.loads((ROOT / 'repositories.json').read_text())
    old = pathlib.Path('/opt/h3-original-baked')
    BAKED.rename(old)
    clone(next(x for x in repos if x['name'] == 'ComfyUI'), BAKED)
    # Preserve the base image's management and service integrations.
    shutil.copytree(old / 'custom_nodes', BAKED / 'custom_nodes', dirs_exist_ok=True)
    if (old / 'user').exists():
        shutil.copytree(old / 'user', BAKED / 'user', dirs_exist_ok=True)
    shutil.rmtree(old)
    installed = []
    for item in repos:
        if item['name'] == 'ComfyUI':
            continue
        path = BAKED / 'custom_nodes' / item['name']
        if path.exists():
            shutil.rmtree(path)
        clone(item, path)
        installed.append(item['name'])

    # Reference caching is needed; the pack's bundled Motion Context is not.
    # Register only these two cache nodes so Niko owns the continuation nodes,
    # routes and frontend. Keep all upstream source files and git metadata.
    cache = BAKED / 'custom_nodes/ComfyUI-Minimax-H3-Reference-Library'
    shutil.copy2(cache / '__init__.py', cache / '__init__.py.upstream')
    (cache / '__init__.py').write_text(
        'from .cached_h3_reference import SkebaCachedMiniMaxH3ReferenceToVideo, SkebaCachedMiniMaxH3ReferenceFirstLast\n'
        'NODE_CLASS_MAPPINGS = {\n'
        ' "SkebaCachedMiniMaxH3ReferenceToVideo": SkebaCachedMiniMaxH3ReferenceToVideo,\n'
        ' "SkebaCachedMiniMaxH3ReferenceFirstLast": SkebaCachedMiniMaxH3ReferenceFirstLast,\n'
        '}\n', encoding='utf-8')

    # Reuse the image's CUDA 13 PyTorch. Conflicting requirements fail the build
    # instead of silently swapping Torch to a different CUDA release.
    pins = []
    for package in ('torch', 'torchvision', 'torchaudio'):
        pins.append(f'{package}=={importlib.metadata.version(package)}')
    constraints = ROOT / 'torch-constraints.txt'
    constraints.write_text('\n'.join(pins) + '\n')
    run(sys.executable, '-m', 'venv', '--system-site-packages', VENV)
    python = VENV / 'bin/python'
    requirements = [BAKED / 'requirements.txt']
    requirements += [BAKED / 'custom_nodes' / name / 'requirements.txt' for name in installed]
    args = [python, '-m', 'pip', 'install', '--no-cache-dir', '-c', constraints,
            '--extra-index-url', 'https://download.pytorch.org/whl/cu130']
    for req in requirements:
        if req.exists():
            args.extend(['-r', req])
    run(*args)
    run(python, '-m', 'pip', 'check')
    run(python, '-c', 'import torch; assert torch.version.cuda == "13.0", torch.version.cuda')
    run(python, '-m', 'compileall', '-q', ROOT)
    freeze = subprocess.check_output([str(python), '-m', 'pip', 'freeze'], text=True)
    (ROOT / 'installed-packages.txt').write_text(freeze)
    bundle = hashlib.sha256((ROOT / 'repositories.json').read_bytes() +
                            pathlib.Path(__file__).read_bytes()).hexdigest()
    (BAKED / '.runpod-bundle-version').write_text('H3_BUNDLE=' + bundle + '\n')
    start.write_text(patch_start(start.read_text(), installed))
    run('bash', '-n', start)
    print('H3 image dependencies installed; GPU readiness is checked on RunPod.')


if __name__ == '__main__':
    main()
