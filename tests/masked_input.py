import hashlib
import json
import os
import pty
import select
import signal
import termios
import time
import integration as fixture

def check_input(payload, expected=None, cancel=None, expected_code=0):
    pid, descriptor = pty.fork()
    if pid == 0:
        os.environ['COLUMNS'] = '40'
        before = termios.tcgetattr(0)
        try:
            password = fixture.api.read_masked_password('Test password: ')
            result = {'digest': hashlib.sha256(password.encode()).hexdigest()}
            code = 0
        except KeyboardInterrupt:
            result = {'cancelled': True}
            code = 130
        except fixture.api.SetupError as error:
            result = {'error': str(error)}
            code = 1
        result['terminal_restored'] = termios.tcgetattr(0) == before
        print(json.dumps(result), flush=True)
        os._exit(code)
    transcript = b''
    sent = False
    cancelled = False
    status = None
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            ready, _, _ = select.select([descriptor], [], [], .1)
            if ready:
                try:
                    block = os.read(descriptor, 65536)
                except OSError:
                    block = b''
                transcript += block
                if not sent and b'Test password: ' in transcript:
                    os.write(descriptor, payload)
                    sent = True
                if cancel and sent and not cancelled and b'*' in transcript:
                    if cancel == 'ctrl-c':
                        os.write(descriptor, b'\x03')
                    else:
                        os.kill(pid, signal.SIGTERM)
                    cancelled = True
            done, code = os.waitpid(pid, os.WNOHANG)
            if done:
                status = code
                break
        assert status is not None, 'Input test timed out'
        assert os.waitstatus_to_exitcode(status) == expected_code, transcript.decode(errors='replace')
        lines = transcript.decode().replace('\r', '').splitlines()
        result = json.loads(next(line for line in reversed(lines) if line.startswith('{')))
        assert result['terminal_restored'], 'Terminal settings were not restored'
        if expected is not None:
            assert result['digest'] == hashlib.sha256(expected.encode()).hexdigest()
            assert expected.encode() not in transcript, 'Plaintext password exposed'
        return result
    finally:
        if status is None:
            try:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            except ProcessLookupError:
                pass
        os.close(descriptor)

cases = [
    (b'Safe-pass-473X\x7f!\n', 'Safe-pass-473!', None, 0),
    ('Sûreté-été-473!\n'.encode(), 'Sûreté-été-473!', None, 0),
    (b'\x1b[200~Pasted-password-473!\x1b[201~\n', 'Pasted-password-473!', None, 0),
    (b'Hidden-before-cancel', None, 'ctrl-c', 130),
    (b'Hidden-before-term', None, 'sigterm', 130),
    (b'X' * 73 + b'\n', None, None, 1),
    (b'\x04', None, None, 1),
]
for payload, expected, cancel, code in cases:
    check_input(payload, expected, cancel, code)
result = {'success': True, 'tests': len(cases), 'backspace': True, 'utf8': True, 'paste': True,
          'ctrl_c_restores_terminal': True, 'sigterm_restores_terminal': True,
          'oversize_refused': True, 'no_plaintext_echo': True,
          'installer_sha256': hashlib.sha256(fixture.SCRIPT.read_bytes()).hexdigest()}
(fixture.PROJECT / 'preuves' / 'masked-input.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
