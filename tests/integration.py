import copy
import hashlib
import http.server
import json
import os
import pathlib
import socket
import socketserver
import struct
import subprocess
import sys
import threading
import types
import unittest
import urllib.request
import base64
import contextlib
import io
from unittest.mock import patch
import yaml

PROJECT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / 'installer.sh'
source = SCRIPT.read_text().split("<<'PY_RZU'\n", 1)[1].rsplit('\nPY_RZU', 1)[0]
api = types.ModuleType('rzu_installer')
exec(compile(source, 'installer.sh (python)', 'exec'), api.__dict__)
CACHE = pathlib.Path('/var/cache/rzu-adguard-test-assets')
RESULT = PROJECT / 'preuves' / 'integration.json'

class FilterHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/slow-filter.txt':
            import time
            time.sleep(25)
        if self.path == '/missing.txt':
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'[Adblock Plus 2.0]\n! Title: RZU isolated test\n||ads.rzu.invalid^\n')

    def log_message(self, *args):
        pass

def dns_answer(data):
    end = 12
    while data[end]:
        end += data[end] + 1
    question = data[12:end + 5]
    qtype = struct.unpack('!H', data[end + 1:end + 3])[0]
    answer = b''
    if qtype == 1:
        answer = b'\xc0\x0c' + struct.pack('!HHIH', 1, 1, 60, 4) + socket.inet_aton('203.0.113.42')
    return data[:2] + struct.pack('!HHHHH', 0x8180, 1, int(bool(answer)), 0, 0) + question + answer

class DnsUDP(socketserver.BaseRequestHandler):
    def handle(self):
        data, stream = self.request
        stream.sendto(dns_answer(data), self.client_address)

class DnsTCP(socketserver.BaseRequestHandler):
    def handle(self):
        length = self.request.recv(2)
        if len(length) != 2:
            return
        data = self.request.recv(struct.unpack('!H', length)[0])
        response = dns_answer(data)
        self.request.sendall(struct.pack('!H', len(response)) + response)

def invoke(*args, timeout=150):
    command = ['bash', str(SCRIPT), *args]
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, 'RZU_SKIP_APT': '1'})

class PureTests(unittest.TestCase):
    def test_client_console_is_colored_and_readable(self):
        args = api.arguments(['--color', 'always'])
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()) as stream:
            ui = api.Console(args)
            ui.header('install')
            ui.result({'ok': True, 'address': '192.168.1.50', 'interface': 'http://192.168.1.50:3000', 'adult_blocking': True}, 'admin')
            output = stream.getvalue()
        self.assertIn('\x1b[', output)
        self.assertIn('LiminalGuard', output)
        self.assertIn('100%', output)
        self.assertNotIn('DNS primaire', output)
        self.assertNotIn('Historique', output)
        self.assertNotIn('"ok"', output)

    def test_json_mode_stays_machine_readable(self):
        args = api.arguments(['--json', '--color', 'always'])
        value = {'ok': True, 'address': '192.168.1.50', 'interface': 'http://192.168.1.50:3000', 'adult_blocking': True}
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            ui = api.Console(args)
            ui.header('verify')
            ui.progress(30)
            ui.result(value, 'admin')
        self.assertEqual(json.loads(stream.getvalue()), value)
        self.assertNotIn('\x1b[', stream.getvalue())

    def test_no_color_is_respected(self):
        for args, env in [(api.arguments(['--color', 'never']), {}),
                          (api.arguments(['--color', 'always']), {'NO_COLOR': '1'})]:
            with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(io.StringIO()) as stream:
                api.Console(args).header('verify')
            self.assertNotIn('\x1b[', stream.getvalue())

    def test_architectures(self):
        for arch, machine, expected in [('armhf', 'armv7l', 'armv7'), ('armhf', 'aarch64', 'armv7'),
                                         ('arm64', 'aarch64', 'arm64'), ('amd64', 'x86_64', 'amd64'),
                                         ('armhf', 'armv6l', 'armv6')]:
            self.assertEqual(api.architecture(arch, machine), expected)
        with self.assertRaises(api.SetupError):
            api.architecture('mips', 'mips')

    def test_profile(self):
        args = api.arguments(['--test-mode', '--ip', '127.0.0.2'])
        cfg = api.configuration(args, '127.0.0.2', '$2b$10$placeholder')
        self.assertFalse(cfg['querylog']['enabled'])
        self.assertFalse(cfg['querylog']['file_enabled'])
        self.assertFalse(cfg['statistics']['enabled'])
        self.assertFalse(cfg['dhcp']['enabled'])
        self.assertTrue(cfg['filtering']['parental_enabled'])
        self.assertEqual(cfg['dns']['cache_size'], 4194304)
        self.assertNotIn('192.168.1.21', yaml.safe_dump(cfg))
        self.assertEqual(cfg['dns']['bind_hosts'], ['127.0.0.2'])

    def test_repair_preserves_customizations(self):
        args = api.arguments(['--test-mode', '--ip', '127.0.0.2'])
        old = api.configuration(args, '127.0.0.2', '$2b$10$unchanged')
        old['user_rules'].append('||keep-my-rule.invalid^')
        old['filters'].append(dict(id=100, enabled=True, url='https://example.org/filter.txt'))
        new = api.configuration(args, '127.0.0.2', None, old)
        self.assertEqual(new['users'], old['users'])
        self.assertIsNot(new['users'], old['users'])
        self.assertIsNot(new['filters'], old['filters'])
        self.assertIn('||keep-my-rule.invalid^', new['user_rules'])
        self.assertEqual(len(new['filters']), 2)

    def test_fail_closed_hash(self):
        bad = pathlib.Path('/tmp/rzu-adguard-corrupted.tar.gz')
        bad.write_bytes(b'not an archive')
        with self.assertRaises(api.SetupError):
            api.extract_binary(bad, pathlib.Path('/tmp/rzu-never-extracted'), 'amd64')
        self.assertFalse(pathlib.Path('/tmp/rzu-never-extracted').exists())

    def test_non_https_refused(self):
        for url in ['ftp://example.org/a', 'https://user:password@example.org', 'http://example.org/a']:
            with self.assertRaises(api.SetupError):
                api.arguments(['--test-mode', '--upstream', url])

    def test_password_file_permissions(self):
        path = pathlib.Path('/tmp/rzu-adguard-permission-test-' + str(os.getpid()))
        path.write_text('Not-a-production-password-473!')
        args = api.arguments(['--test-mode', '--password-file', str(path)])
        try:
            path.chmod(0o644)
            with self.assertRaises(api.SetupError):
                api.password_hash(args)
            path.chmod(0o600)
            self.assertTrue(api.password_hash(args).startswith('$2b$'))
        finally:
            path.unlink(missing_ok=True)

class RealBinaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (CACHE / 'amd64.tar.gz').exists():
            raise RuntimeError('Executer tests/prepare_assets.py avant les tests isoles.')
        cls.root = pathlib.Path('/tmp/rzu-adguard-integration-' + str(os.getpid()))
        cls.password = pathlib.Path('/tmp/rzu-adguard-test-password-' + str(os.getpid()))
        cls.password.write_text('Only-a-test-password-473!')
        cls.password.chmod(0o600)
        cls.common = ['--json', '--test-mode', '--test-root', str(cls.root), '--ip', '127.0.0.2',
                      '--test-no-external-checks',
                      '--archive', str(CACHE / 'amd64.tar.gz'), '--upstream', 'udp://127.0.0.1:10053',
                      '--filter-url', 'http://127.0.0.1:10080/filter.txt', '--password-file', str(cls.password)]

    @classmethod
    def tearDownClass(cls):
        if cls.root.exists() and (cls.root / api.MARKER).exists():
            invoke('remove', *cls.common)
        cls.password.unlink(missing_ok=True)

    def test_01_install_and_real_dns(self):
        result = invoke('install', *self.common)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(api.dns_probe('127.0.0.2'), ['0.0.0.0'])
        self.assertEqual(api.dns_probe('127.0.0.2', tcp=True), ['0.0.0.0'])
        self.assertEqual(api.dns_probe('127.0.0.2', 'example.com'), ['203.0.113.42'])
        for _ in range(30):
            if api.dns_probe('127.0.0.2', 'ads.rzu.invalid') == ['0.0.0.0']:
                break
            import time
            time.sleep(.2)
        else:
            self.fail('Downloaded DNS blocklist not loaded')
        cfg = yaml.safe_load((self.root / 'AdGuardHome.yaml').read_text())
        self.assertTrue(api.bcrypt.checkpw(b'Only-a-test-password-473!', cfg['users'][0]['password'].encode()))
        self.assertEqual((self.root / 'AdGuardHome.yaml').stat().st_mode & 0o777, 0o600)

    def test_02_idempotent_preserves_config_and_password(self):
        path = self.root / 'AdGuardHome.yaml'
        before = path.read_bytes()
        result = invoke('install', *self.common)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.read_bytes(), before)

    def test_03_verify(self):
        result = invoke('verify', *self.common)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_04_repair(self):
        path = self.root / 'AdGuardHome.yaml'
        data = yaml.safe_load(path.read_text())
        password = data['users'][0]['password']
        data['querylog']['enabled'] = True
        data['statistics']['enabled'] = True
        data['user_rules'].append('||keep-custom.invalid^')
        api.write_yaml(path, data)
        result = invoke('repair', *self.common)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        repaired = yaml.safe_load(path.read_text())
        self.assertFalse(repaired['querylog']['enabled'])
        self.assertFalse(repaired['statistics']['enabled'])
        self.assertEqual(repaired['users'][0]['password'], password)
        self.assertIn('||keep-custom.invalid^', repaired['user_rules'])

    def test_05_no_query_history(self):
        history = list((self.root / 'work').rglob('querylog*'))
        self.assertFalse(history, str(history))

        request = urllib.request.Request('http://127.0.0.2:3000/control/stats', headers={
            'Authorization': 'Basic ' + base64.b64encode(b'admin:Only-a-test-password-473!').decode()})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        stats = json.load(opener.open(request, timeout=5))
        self.assertEqual(stats['num_dns_queries'], 0)

    def test_06_unmanaged_refused(self):
        foreign = pathlib.Path('/tmp/rzu-adguard-unmanaged-' + str(os.getpid()))
        foreign.mkdir()
        sentinel = foreign / 'do-not-change.txt'
        sentinel.write_text('preserve')
        result = invoke('install', '--test-mode', '--test-root', str(foreign), '--ip', '127.0.0.2')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(), 'preserve')

    def test_07_port_conflict_refused(self):
        conflict = pathlib.Path('/tmp/rzu-adguard-conflict-' + str(os.getpid()))
        with socket.socket() as listener:
            listener.bind(('127.0.0.3', 3000))
            listener.listen()
            result = invoke('install', '--json', '--test-mode', '--test-root', str(conflict), '--ip', '127.0.0.3')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('occupe', result.stderr)
        self.assertFalse(conflict.exists())

    def test_08_remove_and_reinstall(self):
        before = yaml.safe_load((self.root / 'AdGuardHome.yaml').read_text())['users']
        removed = invoke('remove', *self.common)
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertTrue((self.root / 'AdGuardHome.yaml').exists())
        installed = invoke('install', *self.common)
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.assertEqual(yaml.safe_load((self.root / 'AdGuardHome.yaml').read_text())['users'], before)

    def test_09_tampered_binary_refused(self):
        removed = invoke('remove', *self.common)
        self.assertEqual(removed.returncode, 0, removed.stderr)
        path = self.root / 'AdGuardHome'
        original = path.read_bytes()
        try:
            api.atomic_write(path, original + b'tampered', 0o755)
            result = invoke('install', *self.common)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('endommage', result.stderr)
        finally:
            api.atomic_write(path, original, 0o755)

class ArmBinaryTests(unittest.TestCase):
    def test_arm_binaries_under_qemu(self):
        for arch, runner in [('armv7', '/usr/bin/qemu-arm-static'), ('arm64', '/usr/bin/qemu-aarch64-static'), ('armv6', '/usr/bin/qemu-arm-static')]:
            with self.subTest(architecture=arch):
                if not pathlib.Path(runner).exists():
                    self.fail('Installer qemu-user-static pour les tests ARM')
                root = pathlib.Path('/tmp/rzu-adguard-arm-' + arch + '-' + str(os.getpid()))
                password = pathlib.Path('/tmp/rzu-adguard-arm-password-' + arch + '-' + str(os.getpid()))
                password.write_text('ARM-only-test-password-473!')
                password.chmod(0o600)
                args = ['--json', '--test-mode', '--test-no-external-checks', '--test-root', str(root), '--ip', '127.0.0.2',
                        '--archive', str(CACHE / (arch + '.tar.gz')), '--runner', runner, '--runner-arch', arch,
                        '--upstream', 'udp://127.0.0.1:10053', '--filter-url', 'http://127.0.0.1:10080/filter.txt',
                        '--password-file', str(password)]
                try:
                    result = invoke('install', *args, timeout=160)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(api.dns_probe('127.0.0.2'), ['0.0.0.0'])
                    self.assertEqual(api.dns_probe('127.0.0.2', 'example.com', tcp=True), ['203.0.113.42'])
                    print('ARM real binary PASS:', arch, flush=True)
                finally:
                    if root.exists() and (root / api.MARKER).exists():
                        invoke('remove', *args)
                    password.unlink(missing_ok=True)

class SlowFilterTests(unittest.TestCase):
    def test_slow_filter_download_completes_before_success(self):
        root = pathlib.Path('/tmp/rzu-adguard-slow-filter-' + str(os.getpid()))
        password = pathlib.Path('/tmp/rzu-adguard-slow-password-' + str(os.getpid()))
        password.write_text('Slow-filter-test-password-473!')
        password.chmod(0o600)
        args = ['--json', '--test-mode', '--test-no-external-checks', '--test-root', str(root), '--ip', '127.0.0.6',
                '--archive', str(CACHE / 'amd64.tar.gz'), '--upstream', 'udp://127.0.0.1:10053',
                '--filter-url', 'http://127.0.0.1:10080/slow-filter.txt', '--password-file', str(password)]
        try:
            result = invoke('install', *args, timeout=150)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(api.dns_probe('127.0.0.6', 'ads.rzu.invalid'), ['0.0.0.0'])
            self.assertTrue((root / 'work/data/filters/1.txt').is_file())
        finally:
            if root.exists() and (root / api.MARKER).exists():
                invoke('remove', *args)
            password.unlink(missing_ok=True)


class FailedInstallTests(unittest.TestCase):
    def test_missing_filter_never_reports_success(self):
        root = pathlib.Path('/tmp/rzu-adguard-failed-filter-' + str(os.getpid()))
        password = pathlib.Path('/tmp/rzu-adguard-failure-password-' + str(os.getpid()))
        password.write_text('Failure-only-test-password-473!')
        password.chmod(0o600)
        args = ['--json', '--test-mode', '--test-no-external-checks', '--test-root', str(root), '--ip', '127.0.0.4',
                '--archive', str(CACHE / 'amd64.tar.gz'), '--upstream', 'udp://127.0.0.1:10053',
                '--filter-url', 'http://127.0.0.1:10080/missing.txt', '--password-file', str(password)]
        try:
            result = invoke('install', *args, timeout=150)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('pas encore telechargee', result.stderr)
            self.assertNotIn('Failure-only-test-password-473!', result.stdout + result.stderr)
            self.assertFalse((root / 'test-pid').exists())
        finally:
            if root.exists() and (root / api.MARKER).exists():
                invoke('remove', *args)
            password.unlink(missing_ok=True)

class SystemdTests(unittest.TestCase):
    def test_real_systemd_lifecycle(self):
        old_unit = api.UNIT
        old_address = api.get_address
        unit = 'rzu-adguard-isolated-test-' + str(os.getpid()) + '.service'
        root = pathlib.Path('/var/lib/rzu-adguard-isolated-test-' + str(os.getpid()))
        password = pathlib.Path('/tmp/rzu-adguard-service-password-' + str(os.getpid()))
        password.write_text('Systemd-only-test-password-473!')
        password.chmod(0o600)
        ns = '/proc/' + str(os.getpid()) + '/ns/net'
        class IsolatedService(api.Installer):
            def service_file(self):
                return super().service_file().replace(b'[Service]\n', ('[Service]\nNetworkNamespacePath=' + ns + '\n').encode())
        args = api.arguments(['--test-mode', '--test-no-external-checks', '--ip', '127.0.0.2',
                              '--archive', str(CACHE / 'amd64.tar.gz'), '--upstream', 'udp://127.0.0.1:10053',
                              '--filter-url', 'http://127.0.0.1:10080/filter.txt', '--password-file', str(password)])
        args.test_mode = False
        api.UNIT = unit
        api.get_address = lambda args: '127.0.0.2'
        installer = IsolatedService(args)
        installer.root = root
        installer.cfg = root / 'AdGuardHome.yaml'
        installer.binary = root / 'AdGuardHome'
        installer.marker = root / api.MARKER
        try:
            installer.install()
            self.assertTrue(installer.running())
            subprocess.run(['systemd-analyze', 'verify', str(installer.unit)], check=True, capture_output=True)
            self.assertEqual(api.dns_probe('127.0.0.2'), ['0.0.0.0'])
            installer.repair()
            installer.remove()
            self.assertFalse(installer.unit.exists())
            self.assertTrue(installer.cfg.exists())
            installer.install()
            self.assertTrue(installer.running())
        finally:
            if installer.unit.exists():
                installer.remove()
            api.UNIT = old_unit
            api.get_address = old_address
            password.unlink(missing_ok=True)

if __name__ == '__main__':
    if os.stat('/proc/self/ns/net').st_ino == os.stat('/proc/1/ns/net').st_ino:
        raise SystemExit('Run with sudo unshare --net -- bash -c "ip link set lo up; python3 tests/integration.py"')
    host_dns_before = hashlib.sha256(pathlib.Path('/etc/resolv.conf').read_bytes()).hexdigest()
    services = [http.server.ThreadingHTTPServer(('127.0.0.1', 10080), FilterHandler),
                socketserver.ThreadingUDPServer(('127.0.0.1', 10053), DnsUDP),
                socketserver.ThreadingTCPServer(('127.0.0.1', 10053), DnsTCP)]
    for server in services:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(PureTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(RealBinaryTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(SlowFilterTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(FailedInstallTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(ArmBinaryTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(SystemdTests)])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    RESULT.parent.mkdir(exist_ok=True)
    host_dns_unchanged = hashlib.sha256(pathlib.Path('/etc/resolv.conf').read_bytes()).hexdigest() == host_dns_before
    RESULT.write_text(json.dumps({'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                                 'success': result.wasSuccessful(), 'namespace': 'isolated network',
                                 'upstream': 'local fixture, not production DNS',
                                 'host_dns_unchanged': host_dns_unchanged,
                                 'installer_sha256': hashlib.sha256(SCRIPT.read_bytes()).hexdigest()}, indent=2))
    sys.exit(not (result.wasSuccessful() and host_dns_unchanged))
