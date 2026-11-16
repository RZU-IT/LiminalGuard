import contextlib
import copy
import hashlib
import io
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import integration as fixture

api = fixture.api


class ReviewTests(unittest.TestCase):
    def test_help_and_version_need_no_installation(self):
        for arguments in [['--help'], ['verify', '--help'], ['--version'], ['--about'], ['--project']]:
            result = subprocess.run(['bash', str(fixture.SCRIPT), *arguments], text=True,
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('apt-get', result.stdout + result.stderr)

    def test_invalid_arguments_stop_before_dependencies(self):
        for arguments in [['typo'], ['--ip'], ['--color', 'wrong'], ['--username='], ['install', 'remove']]:
            result = subprocess.run(['bash', str(fixture.SCRIPT), *arguments], text=True,
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('error', json.loads(self.invoke_json(arguments)))

    def invoke_json(self, arguments):
        result = subprocess.run(['bash', str(fixture.SCRIPT), '--json', *arguments],
                                capture_output=True, text=True, timeout=10)
        return result.stderr

    def test_repair_does_not_mutate_original_profile(self):
        args = api.arguments([])
        original = api.configuration(args, '192.168.50.2', '$2b$10$test-only')
        previous = copy.deepcopy(original)
        args.allow_adult = True
        updated = api.configuration(args, '192.168.50.3', None, original)
        self.assertEqual(original, previous)
        self.assertNotEqual(updated['dns']['bind_hosts'], original['dns']['bind_hosts'])
        self.assertNotEqual(updated['filtering']['parental_enabled'], original['filtering']['parental_enabled'])

    def test_invalid_configuration_is_reported(self):
        for payload in ['', '[]', 'dns: null', 'users: [bad]']:
            with self.assertRaises(api.SetupError):
                api.read_configuration(payload)
        args = api.arguments([])
        cfg = api.configuration(args, '192.168.50.2', '$2b$10$test-only')
        self.assertEqual(api.read_configuration(fixture.yaml.safe_dump(cfg)), cfg)
        cfg['filters'] = [None]
        with self.assertRaises(api.SetupError):
            api.read_configuration(fixture.yaml.safe_dump(cfg))

    def test_invalid_marker_is_reported(self):
        with tempfile.TemporaryDirectory(prefix='rzu-review-') as directory:
            marker = pathlib.Path(directory) / 'marker.json'
            marker.write_text('[]')
            with self.assertRaises(api.SetupError):
                api.read_json(marker)

    def test_branding_and_json_are_separate(self):
        args = api.arguments(['--color', 'always'])
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()) as output:
            console = api.Console(args)
            console.header('install')
        self.assertIn('LiminalGuard ' + api.TOOL_VERSION, output.getvalue())
        self.assertIn('by RZU Informatique', output.getvalue())
        self.assertTrue(all(len(line) <= 40 for line in output.getvalue().replace('\x1b[38;2;191;177;109m', '').replace('\x1b[0m', '').splitlines()))
        args.json = True
        with contextlib.redirect_stdout(io.StringIO()) as output:
            console = api.Console(args)
            console.header('install')
            console.result({'ok': True}, 'admin')
        self.assertEqual(json.loads(output.getvalue()), {'ok': True})


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReviewTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    proof = {'success': result.wasSuccessful(), 'tests': result.testsRun,
             'scope': 'code review checks only; no installation, service or DNS changes',
             'installer_sha256': hashlib.sha256(fixture.SCRIPT.read_bytes()).hexdigest()}
    (fixture.PROJECT / 'preuves' / 'review.json').write_text(json.dumps(proof, indent=2))
    raise SystemExit(not result.wasSuccessful())
