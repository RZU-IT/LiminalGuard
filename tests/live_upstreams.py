import base64
import hashlib
import json
import os
import pathlib
import socket
import subprocess
import tempfile
import time
import types
import urllib.request
import yaml

PROJECT = pathlib.Path(__file__).resolve().parents[1]
source = (PROJECT / 'installer.sh').read_text().split("<<'PY_RZU'\n", 1)[1].rsplit('\nPY_RZU', 1)[0]
api = types.ModuleType('rzu_installer')
exec(compile(source, 'installer.sh (python)', 'exec'), api.__dict__)
before = hashlib.sha256(pathlib.Path('/etc/resolv.conf').read_bytes()).hexdigest()
address, dns_port, web_port = '127.0.0.5', 55335, 30035
for kind, port in [(socket.SOCK_STREAM, dns_port), (socket.SOCK_DGRAM, dns_port), (socket.SOCK_STREAM, web_port)]:
    with socket.socket(socket.AF_INET, kind) as probe:
        probe.bind((address, port))

with tempfile.TemporaryDirectory(prefix='rzu-adguard-live-', dir='/var/tmp') as directory:
    root = pathlib.Path(directory)
    binary = root / 'AdGuardHome'
    api.extract_binary('/var/cache/rzu-adguard-test-assets/amd64.tar.gz', binary, 'amd64')
    args = api.arguments([])
    hashed = api.bcrypt.hashpw(b'Live-only-test-password-473!', api.bcrypt.gensalt()).decode()
    cfg = api.configuration(args, address, hashed)
    cfg['dns']['port'] = dns_port
    cfg['http']['address'] = address + ':' + str(web_port)
    path = root / 'AdGuardHome.yaml'
    api.write_yaml(path, cfg)
    (root / 'work').mkdir()
    log = open(root / 'process.log', 'wb')
    process = subprocess.Popen([str(binary), '--no-check-update', '-c', str(path), '-w', str(root / 'work')],
                               cwd=str(root), stdout=log, stderr=log)
    try:
        last = None
        for _ in range(40):
            try:
                answer = api.dns_probe(address, 'example.com', port=dns_port)
                if answer and '0.0.0.0' not in answer:
                    break
            except OSError as exc:
                last = exc
            time.sleep(.5)
        else:
            raise RuntimeError('Encrypted upstream smoke test failed: ' + str(last))
        assert api.dns_probe(address, port=dns_port) == ['0.0.0.0']
        assert api.dns_probe(address, tcp=True, port=dns_port) == ['0.0.0.0']

        adult = api.dns_probe(address, 'pornhub.com', port=dns_port)
        auth = 'Basic ' + base64.b64encode(b'admin:Live-only-test-password-473!').decode()
        request = urllib.request.Request('http://' + address + ':' + str(web_port) + '/control/filtering/check_host?name=pornhub.com',
                                         headers={'Authorization': auth})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        classification = json.load(opener.open(request, timeout=10))
        print('Parental response:', json.dumps({'dns': adult, 'classification': classification}), flush=True)

        assert classification.get('reason') == 'FilteredParental', 'Parental filtering did not classify the test domain as blocked'
        assert hashlib.sha256(pathlib.Path('/etc/resolv.conf').read_bytes()).hexdigest() == before
        result = {'success': True, 'upstreams': api.UPSTREAMS, 'adult_domain_blocked': True,
                  'dns_udp': True, 'dns_tcp': True, 'host_dns_unchanged': True,
                  'listen_address': address, 'dns_port': dns_port, 'web_port': web_port,
                  'installer_sha256': hashlib.sha256((PROJECT / 'installer.sh').read_bytes()).hexdigest()}
        (PROJECT / 'preuves').mkdir(exist_ok=True)
        (PROJECT / 'preuves/live-upstreams.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
