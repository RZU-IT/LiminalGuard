import hashlib
import importlib.util
import pathlib
import types
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
source = ROOT.joinpath('installer.sh').read_text().split("<<'PY_RZU'\n", 1)[1].rsplit('\nPY_RZU', 1)[0]
module = types.ModuleType('rzu_installer')
exec(compile(source, 'installer.sh (python)', 'exec'), module.__dict__)
cache = pathlib.Path('/var/cache/rzu-adguard-test-assets')
cache.mkdir(parents=True, exist_ok=True)
for arch in ['amd64', 'armv7', 'arm64', 'armv6']:
    path = cache / (arch + '.tar.gz')
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == module.DIGESTS[arch]:
        print(arch, 'cached / SHA256 OK', flush=True)
        continue
    url = 'https://github.com/AdguardTeam/AdGuardHome/releases/download/' + module.VERSION + '/AdGuardHome_linux_' + arch + '.tar.gz'
    module.download(url, path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == module.DIGESTS[arch]
    print(arch, 'downloaded / SHA256 OK', flush=True)
