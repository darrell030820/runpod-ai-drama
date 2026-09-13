"""CPU checks for setup logic. No Docker image, network model downloads or GPU."""
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load('build_image')
prepare = load('prepare_workspace')
check = load('check_nodes')


class SetupTests(unittest.TestCase):
    def test_exact_base_patch_preserves_services(self):
        source = (ROOT / 'base-start.sh.reference').read_text(encoding='utf-8')
        result = build.patch_start(source, ['ComfyUI-Sol-H3', 'ComfyUI-H3-Motion-Context'])
        self.assertIn('VENV_DIR="/opt/h3-venv"', result)
        self.assertEqual(result.count('python /opt/h3-setup/prepare_workspace.py'), 1)
        self.assertIn('"ComfyUI-Sol-H3"', result)
        for service in ['setup_ssh', 'start_jupyter', 'nohup filebrowser', 'upgrade_comfyui_if_needed']:
            self.assertIn(service, result)
        self.assertLess(result.index('python /opt/h3-setup/prepare_workspace.py'), result.index('python main.py $FIXED_ARGS &'))
        with self.assertRaises(RuntimeError):
            build.patch_start(source.replace('python main.py $FIXED_ARGS &', 'changed launcher'), [])

    def test_existing_download_and_fast_reuse(self):
        content = b'known model bytes'
        model = {'directory': 'vae', 'name': 'test.safetensors', 'size': len(content),
                 'sha256': hashlib.sha256(content).hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            target = root / 'vae/test.safetensors'
            target.parent.mkdir()
            target.write_bytes(content)
            with patch.object(prepare.subprocess, 'run', side_effect=AssertionError('No download expected')):
                prepare.ensure_model(model, root)
                with patch.object(prepare, 'digest', side_effect=AssertionError('No repeated hashing expected')):
                    prepare.ensure_model(model, root)
                target.write_bytes(b'corrupt')
                with self.assertRaises(RuntimeError):
                    prepare.ensure_model(model, root)
                self.assertEqual(target.read_bytes(), b'corrupt')

    def test_resumed_download_is_verified(self):
        content = b'complete file'
        model = {'directory': 'vae', 'name': 'test.safetensors', 'size': len(content),
                 'sha256': hashlib.sha256(content).hexdigest(), 'repo': 'owner/repo',
                 'revision': 'a' * 40, 'filename': 'test.safetensors'}
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            partial = root / 'vae/test.safetensors.part'
            partial.parent.mkdir()
            partial.write_bytes(content[:4])
            def finish(args, **kwargs):
                self.assertIn('--continue-at', args)
                self.assertEqual(partial.read_bytes(), content[:4])
                partial.write_bytes(content)
            with patch.object(prepare.subprocess, 'run', side_effect=finish):
                prepare.ensure_model(model, root)
            self.assertFalse(partial.exists())
            self.assertEqual((root / 'vae/test.safetensors').read_bytes(), content)

    def test_workflow_preserved_and_inputs_present(self):
        workflow = json.loads((ROOT / 'EP01_SOL_FULL_6_GEN_CACHED_EXACT.json').read_text())
        original = ROOT.parent / 'EP01_SOL_FULL_6_GEN_CACHED_EXACT.json'
        if original.exists():
            self.assertEqual(workflow, json.loads(original.read_text()))
        required = check.expected_nodes(workflow)
        self.assertIn('SolH3Exact', required)
        self.assertIn('H3PromptReferenceInputs', required)
        self.assertFalse(any(len(x) == 36 and '-' in x for x in required))
        for node in workflow['nodes']:
            if node['type'] == 'LoadImage':
                self.assertTrue((ROOT / 'input' / node['widgets_values'][0]).is_file())
        models = json.loads((ROOT / 'models.json').read_text())
        self.assertEqual(len(models), 5)
        for model in models:
            self.assertEqual(len(model['sha256']), 64)
            self.assertEqual(len(model['revision']), 40)
        print(f'Workflow requires {len(required)} registered node types; all eight reference inputs present.')


if __name__ == '__main__':
    unittest.main()
