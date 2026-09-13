"""Check actual registrations after startup; this does not submit a render."""
import argparse
import json
import pathlib
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent


def expected_nodes(workflow):
    subgraphs = workflow.get('definitions', {}).get('subgraphs', [])
    subgraph_ids = {s['id'] for s in subgraphs}
    return {n['type'] for graph in [workflow] + subgraphs for n in graph['nodes']
            if n['type'] not in subgraph_ids and n['type'] not in {'Note', 'MarkdownNote', 'Reroute'}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait', type=int, default=0)
    parser.add_argument('--url', default='http://127.0.0.1:8188')
    args = parser.parse_args()
    deadline = time.monotonic() + args.wait
    while True:
        try:
            with urllib.request.urlopen(args.url.rstrip('/') + '/object_info', timeout=30) as response:
                info = json.load(response)
            break
        except (OSError, ValueError):
            if time.monotonic() >= deadline:
                raise SystemExit('FAILED: ComfyUI did not become ready. Check the ComfyUI startup log.')
            time.sleep(3)
    workflow = json.loads((ROOT / 'EP01_SOL_FULL_6_GEN_CACHED_EXACT.json').read_text())
    expected = expected_nodes(workflow)
    missing = sorted(expected - set(info))
    providers = {key: info.get(key, {}).get('python_module') for key in [
        'MiniMaxH3MotionContext', 'MiniMaxH3MotionContextTrim',
        'SkebaCachedMiniMaxH3ReferenceToVideo', 'SolH3Exact']}
    print(json.dumps({'required_node_count': len(expected), 'missing_nodes': missing,
                      'providers': providers}, indent=2), flush=True)
    if missing:
        raise SystemExit('FAILED: required nodes are missing; inspect custom-node import errors.')
    for key in ('MiniMaxH3MotionContext', 'MiniMaxH3MotionContextTrim'):
        if 'ComfyUI-H3-Motion-Context' not in (providers[key] or ''):
            raise SystemExit(f'FAILED: unexpected provider for {key}: {providers[key]}. Check duplicate node packs.')
    print('PASS: all workflow node types registered. GPU render validation is still required.', flush=True)


if __name__ == '__main__':
    main()

