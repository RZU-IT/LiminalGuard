import argparse
import hashlib
import json
import pathlib
import time
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=pathlib.Path, default=root / '.distribution' / 'LiminalGuard.zip')
args = parser.parse_args()
script_hash = hashlib.sha256((root / 'installer.sh').read_bytes()).hexdigest()
proofs = [root / 'preuves' / name for name in ['integration.json', 'interactive-prompt.json', 'live-upstreams.json', 'masked-input.json', 'review.json']]
for proof in proofs:
    data = json.loads(proof.read_text())
    if (not data.get('success') or data.get('installer_sha256') != script_hash
            or (proof.name in ('integration.json', 'live-upstreams.json') and not data.get('host_dns_unchanged'))):
        raise SystemExit('Tests absents, echoues ou perimes : ' + proof.name)
files = [(root / 'installer.sh', 'installer.sh'), (root / 'CLIENT_README.md', 'README.md'),
         (root / 'LICENSE', 'LICENSE'), (root / 'NOTICE.txt', 'NOTICE.txt'),
         (root / 'assets/liminalguard-icon.svg', 'assets/liminalguard-icon.svg'),
         (root / 'assets/liminalguard-logo.svg', 'assets/liminalguard-logo.svg')]
args.output.parent.mkdir(parents=True, exist_ok=True)
temporary = args.output.with_suffix('.building.zip')
hashes = {}
with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path, rel in files:
        payload = path.read_bytes()
        hashes[rel] = hashlib.sha256(payload).hexdigest()
        info = zipfile.ZipInfo('LiminalGuard/' + rel, time.localtime(path.stat().st_mtime)[:6])
        info.create_system = 3
        info.external_attr = ((0o100755 if path.name == 'installer.sh' else 0o100644) << 16)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, payload)
    archive.writestr('LiminalGuard/SHA256.json', json.dumps(hashes, indent=2))
with zipfile.ZipFile(temporary) as archive:
    if archive.testzip() is not None:
        raise SystemExit('Archive CRC verification failed')
    for rel, expected in hashes.items():
        if hashlib.sha256(archive.read('LiminalGuard/' + rel)).hexdigest() != expected:
            raise SystemExit('Archive hash verification failed: ' + rel)
temporary.replace(args.output)
print(json.dumps({'zip': str(args.output), 'files': len(hashes) + 1, 'crc': 'PASS', 'sha256': 'PASS',
                  'installer_sha256': script_hash}))
