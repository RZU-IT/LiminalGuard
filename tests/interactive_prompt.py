import http.server
import hashlib
import json
import os
import pathlib
import pty
import select
import re
import html
import signal
import socketserver
import threading
import time
import integration as fixture

if os.stat('/proc/self/ns/net').st_ino == os.stat('/proc/1/ns/net').st_ino:
    raise SystemExit('Test reserve a un espace reseau prive')

services = [http.server.ThreadingHTTPServer(('127.0.0.1', 10080), fixture.FilterHandler),
            socketserver.ThreadingUDPServer(('127.0.0.1', 10053), fixture.DnsUDP),
            socketserver.ThreadingTCPServer(('127.0.0.1', 10053), fixture.DnsTCP)]
for server in services:
    threading.Thread(target=server.serve_forever, daemon=True).start()

root = pathlib.Path('/tmp/rzu-adguard-interactive-' + str(os.getpid()))
args = ['--test-mode', '--test-no-external-checks', '--test-root', str(root), '--ip', '127.0.0.2',
        '--archive', str(fixture.CACHE / 'amd64.tar.gz'), '--upstream', 'udp://127.0.0.1:10053',
        '--filter-url', 'http://127.0.0.1:10080/filter.txt']
secret = b'Interactive-only-password-473!'
pid, fd = pty.fork()
if pid == 0:
    os.execvpe('bash', ['bash', str(fixture.SCRIPT), 'install', *args], {**os.environ, 'RZU_SKIP_APT': '1',
                'TERM': 'xterm-256color', 'COLUMNS': '40', 'LINES': '24'})

output = b''
sent = 0
status = None
try:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        readable, _, _ = select.select([fd], [], [], .2)
        if readable:
            try:
                data = os.read(fd, 65536)
            except OSError:
                data = b''
            output += data
            if sent == 0 and b'Mot de passe admin :' in output:
                os.write(fd, secret + b'\n')
                sent = 1
        done, code = os.waitpid(pid, os.WNOHANG)
        if done:
            status = code
            break
    assert status is not None, 'Prompt timed out'
    assert os.waitstatus_to_exitcode(status) == 0, output.decode(errors='replace')
    assert sent == 1, 'Exactly one administrator password prompt is expected'
    assert secret not in output, 'Password was echoed'
    assert b'************' in output, 'Password must be masked with stars'
    config = fixture.yaml.safe_load((root / 'AdGuardHome.yaml').read_text())
    assert fixture.api.bcrypt.checkpw(secret, config['users'][0]['password'].encode()), 'Full password must be preserved'
    assert b'100%' in output, output.decode(errors='replace')
    assert b'\x1b[' in output, 'Interactive colors must be visible'
    raw_text = output.decode().replace('\r\n', '\n')
    visible_text = '\n'.join(line.split('\r')[-1] for line in raw_text.split('\n'))
    plain = re.sub(r'\x1b\[[0-9;]*m', '', visible_text)
    assert all(len(line) <= 40 for line in plain.splitlines()), 'Mobile layout exceeds 40 columns'
    assert '"ok"' not in plain, 'Client mode must not show raw JSON'
    assert 'DNS primaire' not in plain and '[1/5]' not in plain, 'Detailed client output must be absent'
    lines = [line for line in plain.splitlines() if line.strip()]
    assert len(lines) == 5, 'Only branding, password prompt and loading bar may be displayed'
    assert 'LiminalGuard ' + fixture.api.TOOL_VERSION in lines[0]
    assert 'by RZU Informatique' in lines[1]
    assert 'AdGuard Home setup' in lines[2]
    assert lines[3].startswith('Mot de passe admin : ')
    assert lines[4].startswith('Installation [') and lines[4].endswith('100%')
    (fixture.PROJECT / 'preuves' / 'apercu-terminal.txt').write_text(plain)
    palette = {'38;2;191;177;109': '#bfb16d', '38;2;151;171;126': '#97ab7e', '1;35': '#c084fc', '1;36': '#22d3ee', '1;32': '#4ade80', '1;33': '#facc15',
               '1;31': '#fb7185', '90': '#94a3b8'}
    escaped = html.escape(visible_text)
    def ansi(match):
        code = match.group(1)
        return '</span>' if code == '0' else '<span style="color:' + palette.get(code, '#e2e8f0') + '">'
    rendered = re.sub(r'\x1b\[([0-9;]*)m', ansi, escaped)
    preview = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LiminalGuard</title><body style="margin:0;background:#0f172a;color:#e2e8f0;padding:20px"><pre style="max-width:44ch;margin:auto;font:14px/1.6 ui-monospace,monospace;white-space:pre-wrap">' + rendered + '</pre>'
    (fixture.PROJECT / 'preuves' / 'apercu-terminal.html').write_text(preview)
    result = {'success': True, 'password_prompts': 1, 'password_echoed': False, 'password_mask': 'stars',
              'installed_and_functional': True, 'test': 'real CLI in pseudo-terminal',
              'colors': True, 'mobile_columns': 40, 'raw_json': False,
              'installer_sha256': hashlib.sha256(fixture.SCRIPT.read_bytes()).hexdigest()}
    (fixture.PROJECT / 'preuves' / 'interactive-prompt.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
finally:
    if status is None:
        try:
            os.kill(pid, signal.SIGTERM)
            os.waitpid(pid, 0)
        except ProcessLookupError:
            pass
    os.close(fd)
    if (root / fixture.api.MARKER).exists():
        removed = fixture.invoke('remove', *args)
        assert removed.returncode == 0, removed.stderr
