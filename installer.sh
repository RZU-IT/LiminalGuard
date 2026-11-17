#!/usr/bin/env bash
set -euo pipefail
rzu_machine=0
rzu_color=auto
rzu_color_next=0
for rzu_arg in "$@"; do
  if [[ $rzu_color_next == 1 ]]; then rzu_color=$rzu_arg; rzu_color_next=0; fi
  case $rzu_arg in
    --json) rzu_machine=1 ;;
    --color) rzu_color_next=1 ;;
    --color=*) rzu_color=${rzu_arg#--color=} ;;
  esac
done
rzu_notice() {
  [[ $rzu_machine != 1 ]] || return 0
  if [[ -z ${NO_COLOR+x} && ( $rzu_color == always || ( $rzu_color != never && -t 1 && ${TERM:-} != dumb ) ) ]]; then
    printf '\033[38;2;191;177;109m%s\033[0m\n' "$1"
  else
    printf '%s\n' "$1"
  fi
}
rzu_error() {
  if [[ $rzu_machine == 1 ]]; then
    printf '{"ok":false,"error":"%s"}\n' "$1" >&2
  else
    printf '%s\n' "$1" >&2
  fi
}
rzu_banner() {
  rzu_notice '  ┌───┐ LiminalGuard 0.1.0-beta.1'
  rzu_notice '  │ ┌─┘ by RZU Informatique'
  rzu_notice '  └─┘   AdGuard Home setup'
}
for rzu_arg in "$@"; do
  case $rzu_arg in
    -h|--help)
      rzu_banner
      cat <<'HELP'

sudo bash installer.sh          Installer AdGuard Home
sudo bash installer.sh verify   Vérifier le fonctionnement
sudo bash installer.sh repair   Réappliquer le profil, conserver le compte
sudo bash installer.sh remove   Retirer le service, conserver les données

Options : --interface eth0 ; --ip ADRESSE ; --username IDENTIFIANT
  --allow-adult ; --password-file FICHIER ; --archive FICHIER
  --upstream URL ; --filter-url URL ; --json
  --color auto|always|never ; --version ; --about ; --project

Raspberry Pi OS / Debian 11+ et systemd, en 32 ou 64 bits.
Guide réseau et maintenance : README.md.
HELP
      exit 0 ;;
    --version) printf '%s\n' 'LiminalGuard 0.1.0-beta.1'; exit 0 ;;
    --about)
      rzu_banner
      printf '%s\n' "Développé par RZU Informatique avec l’assistance d’OpenAI Codex." 'Licence MIT · Version expérimentale.'
      exit 0 ;;
    --project) printf '%s\n' 'https://github.com/RZU-IT/LiminalGuard'; exit 0 ;;
  esac
done
rzu_action=install
rzu_action_seen=0
rzu_test=0
rzu_value=''
for rzu_arg in "$@"; do
  if [[ -n $rzu_value ]]; then
    if [[ -z $rzu_arg || $rzu_arg == --* ]]; then
      rzu_error 'Valeur manquante. Consulte --help.'; exit 2
    fi
    if [[ $rzu_value == --color && $rzu_arg != auto && $rzu_arg != always && $rzu_arg != never ]]; then
      rzu_error 'Couleur attendue : auto, always ou never.'; exit 2
    fi
    rzu_value=''
    continue
  fi
  case $rzu_arg in
    --json|--allow-adult|--test-no-external-checks) ;;
    --test-mode) rzu_test=1 ;;
    --interface|--ip|--username|--password-file|--archive|--upstream|--filter-url|--color|--test-root|--runner|--runner-arch) rzu_value=$rzu_arg ;;
    --interface=*|--ip=*|--username=*|--password-file=*|--archive=*|--upstream=*|--filter-url=*|--test-root=*|--runner=*|--runner-arch=*)
      if [[ -z ${rzu_arg#*=} ]]; then rzu_error 'Valeur manquante. Consulte --help.'; exit 2; fi ;;
    --color=auto|--color=always|--color=never) ;;
    install|verify|repair|remove)
      if [[ $rzu_action_seen == 1 ]]; then rzu_error 'Une seule action est attendue.'; exit 2; fi
      rzu_action=$rzu_arg; rzu_action_seen=1 ;;
    *) rzu_error 'Argument inconnu. Consulte --help.'; exit 2 ;;
  esac
done
if [[ -n $rzu_value ]]; then rzu_error 'Valeur manquante. Consulte --help.'; exit 2; fi
if [[ $EUID != 0 ]]; then
  rzu_error 'Lance sudo bash installer.sh pour installer.'
  exit 1
fi
if [[ ! -r /etc/os-release ]]; then rzu_error 'Distribution Linux inconnue.'; exit 1; fi
# shellcheck source=/dev/null
. /etc/os-release
case ${ID:-}:${ID_LIKE:-} in
  debian:*|raspbian:*|ubuntu:*|*:debian*) ;;
  *) rzu_error 'Utiliser Raspberry Pi OS, Debian ou Ubuntu.'; exit 1 ;;
esac
if [[ $rzu_test != 1 ]] && { ! command -v systemctl >/dev/null || [[ ! -d /run/systemd/system ]]; }; then
  rzu_error 'systemd doit être actif. Aucun paquet installé.'; exit 1
fi
if ! command -v python3 >/dev/null || ! python3 -c 'import yaml, bcrypt' 2>/dev/null || ! command -v ip >/dev/null || [[ ! -s /etc/ssl/certs/ca-certificates.crt ]]; then
  if [[ $rzu_action == verify || $rzu_action == remove ]]; then
    rzu_error 'Dependances absentes. Aucun paquet installe pendant verify/remove.'
    exit 1
  fi
  if [[ ${RZU_SKIP_APT:-0} == 1 ]]; then rzu_error 'Dependances Python absentes.'; exit 1; fi
  rzu_banner
  export RZU_BANNER_SHOWN=1
  if [[ $rzu_machine != 1 && -t 1 ]]; then printf 'Installation [----------------]   0%%'; fi
  umask 077
  rzu_apt_log=$(mktemp /tmp/rzu-adguard-dependencies.XXXXXX)
  trap 'rm -f -- "$rzu_apt_log"' EXIT
  if ! apt-get update >"$rzu_apt_log" 2>&1 || ! DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 python3-yaml python3-bcrypt ca-certificates iproute2 >>"$rzu_apt_log" 2>&1; then
    if [[ $rzu_machine != 1 && -t 1 ]]; then printf '\r\033[2K'; fi
    rzu_error 'Installation impossible.'
    exit 1
  fi
  rm -f -- "$rzu_apt_log"
  trap - EXIT
  if [[ $rzu_machine != 1 && -t 1 ]]; then printf '\r\033[2K'; fi
fi
exec python3 - "$@" <<'PY_RZU'
from __future__ import annotations
import argparse, base64, codecs, contextlib, copy, fcntl, hashlib, ipaddress, json
import os, pathlib, platform, re, shutil, socket, stat, struct, subprocess
import select, signal, sys, tarfile, tempfile, termios, textwrap, time, urllib.error, urllib.parse, urllib.request
import bcrypt
import yaml

if sys.version_info < (3, 9):
    raise SystemExit('Python 3.9 minimum : utiliser Raspberry Pi OS / Debian 11 ou plus recent.')

TOOL_VERSION = '0.1.0-beta.1'
PROJECT_URL = 'https://github.com/RZU-IT/LiminalGuard'
VERSION = 'v0.107.80'
SCHEMA = 34
DIGESTS = {
    'amd64': '28593bc761d71469abdbc6f39ca42cbed763ec92b63082c729177b037ed51d18',
    'armv7': '760b941d49eaf92c3fd85ddd47f81530382f5cab8054165fd7f4089e1e9389dc',
    'arm64': 'd5e17d0d724418ddef8b7723ed8ade7eef4e621ec5b0e43a341859cca71a3d8f',
    'armv6': 'e42499af6434625506e13a64cbc281c65f94a956d5bdc6af0bfe4841d11729fd',
}
FILTER_URL = 'https://adguardteam.github.io/AdGuardSDNSFilter/Filters/filter.txt'
UPSTREAMS = ['https://dns.adguard-dns.com/dns-query', 'https://dns.quad9.net/dns-query']
UNIT = 'rzu-adguard-home.service'
MARKER = '.rzu-installation.json'
TEST_DOMAIN = 'test-blocage.rzu.invalid'
UI_FOR_ERRORS = None

class SetupError(Exception):
    pass

class Console:
    def __init__(self, args):
        self.machine = args.json
        self.terminal = sys.stdout.isatty()
        self.color = args.color == 'always' or (args.color == 'auto' and self.terminal and os.environ.get('TERM') != 'dumb')
        if args.color == 'never' or 'NO_COLOR' in os.environ:
            self.color = False
        self.width = max(28, min(68, shutil.get_terminal_size((60, 24)).columns))

    def colored(self, text, code):
        return '\033[' + code + 'm' + text + '\033[0m' if self.color else text

    def header(self, action):
        if self.machine:
            return
        if os.environ.get('RZU_BANNER_SHOWN') != '1':
            for line in ['  ┌───┐ LiminalGuard ' + TOOL_VERSION,
                         '  │ ┌─┘ by RZU Informatique',
                         '  └─┘   AdGuard Home setup']:
                print(self.colored(line, '38;2;191;177;109'), flush=True)
        if action != 'install':
            self.progress(0)

    def progress(self, percent):
        if self.machine or (not self.terminal and percent != 100):
            return
        size = max(6, self.width - 21)
        filled = size * percent // 100
        line = 'Installation [' + '#' * filled + '-' * (size - filled) + '] ' + str(percent).rjust(3) + '%'
        line = self.colored(line, '38;2;151;171;126' if percent == 100 else '38;2;191;177;109')
        print(('\r' if self.terminal else '') + line, end='' if self.terminal else '\n', flush=True)

    def finish(self):
        self.progress(100)
        if self.terminal and not self.machine:
            print(flush=True)

    def result(self, data, username):
        if self.machine:
            print(json.dumps(data, ensure_ascii=False), flush=True)
        else:
            self.finish()

    def failure(self, error):
        if self.machine:
            print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        else:
            print('\n' + self.colored('Installation impossible.', '1;31'), file=sys.stderr, flush=True)

def run(argv, **kwargs):
    kwargs.setdefault('capture_output', True)
    try:
        return subprocess.run(argv, check=True, text=True, **kwargs)
    except subprocess.CalledProcessError as exc:
        diagnostic = (exc.stderr or '').strip()[-1800:]
        diagnostic = re.sub(r'\$2[aby]\$\S+', '[hash masque]', diagnostic)
        raise SetupError('Commande echouee : ' + pathlib.Path(argv[0]).name + (' : ' + diagnostic if diagnostic else '')) from None

def architecture(dpkg_arch=None, machine=None):
    if dpkg_arch is None:
        dpkg_arch = run(['dpkg', '--print-architecture'], capture_output=True).stdout.strip()
    machine = machine or platform.machine()
    if dpkg_arch == 'armhf':
        return 'armv6' if machine == 'armv6l' else 'armv7'
    aliases = {'arm64': 'arm64', 'amd64': 'amd64', 'armel': 'armv6'}
    if dpkg_arch not in aliases:
        raise SetupError('Architecture non prise en charge : ' + dpkg_arch)
    return aliases[dpkg_arch]

def atomic_write(path, data, mode=0o600):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.rzu-', dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)

def write_yaml(path, data):
    atomic_write(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True).encode())

def read_json(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise SetupError('Marqueur d’installation invalide.')
    return value


def read_configuration(payload):
    cfg = yaml.safe_load(payload)
    if not isinstance(cfg, dict):
        raise SetupError('Configuration AdGuard illisible : objet YAML attendu.')
    for section in ('dns', 'http', 'filtering', 'querylog', 'statistics', 'dhcp'):
        if not isinstance(cfg.get(section), dict):
            raise SetupError('Section de configuration invalide : ' + section)
    users = cfg.get('users')
    if not isinstance(users, list) or not users or any(
            not isinstance(user, dict) or not isinstance(user.get('name'), str)
            or not isinstance(user.get('password'), str) for user in users):
        raise SetupError('Configuration du compte administrateur invalide.')
    hosts = cfg['dns'].get('bind_hosts')
    if not isinstance(hosts, list) or len(hosts) != 1 or not isinstance(hosts[0], str):
        raise SetupError('Une seule adresse DNS IPv4 est attendue.')
    try:
        ipaddress.IPv4Address(hosts[0])
    except ipaddress.AddressValueError:
        raise SetupError('Adresse DNS IPv4 invalide.') from None
    filters = cfg.get('filters')
    if not isinstance(filters, list) or any(
            not isinstance(item, dict) or not isinstance(item.get('id'), int)
            or not isinstance(item.get('url'), str) for item in filters):
        raise SetupError('Configuration des listes de filtrage invalide.')
    if not isinstance(cfg.get('user_rules'), list) or any(not isinstance(rule, str) for rule in cfg['user_rules']):
        raise SetupError('Configuration des règles personnelles invalide.')
    return cfg

def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def get_address(args):
    if args.ip:
        address = ipaddress.IPv4Address(args.ip)
        if args.test_mode:
            if not address.is_loopback:
                raise SetupError('Le test isole exige une adresse loopback.')
            return str(address)
        if not any(address in n for n in map(ipaddress.ip_network, ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'])):
            raise SetupError('Choisir une IPv4 privee du reseau domestique.')
        interfaces = json.loads(run(['ip', '-j', '-4', 'addr', 'show'], capture_output=True).stdout)
        if not any(a.get('local') == str(address) for i in interfaces for a in i.get('addr_info', [])):
            raise SetupError('Cette adresse IPv4 ne se trouve pas sur ce Raspberry.')
        return str(address)
    if args.interface:
        interfaces = json.loads(run(['ip', '-j', '-4', 'addr', 'show', 'dev', args.interface], capture_output=True).stdout)
        choices = [a['local'] for i in interfaces for a in i.get('addr_info', []) if a.get('scope') == 'global']
    else:
        routes = json.loads(run(['ip', '-j', '-4', 'route', 'get', '1.1.1.1'], capture_output=True).stdout)
        choices = [r['prefsrc'] for r in routes if 'prefsrc' in r]
    if len(set(choices)) != 1:
        raise SetupError('Adresse ambigue ou absente. Preciser --interface eth0 ou --ip ADRESSE.')
    args.ip = choices[0]
    return get_address(args)

def read_masked_password(prompt):
    try:
        descriptor = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
    except OSError:
        raise SetupError('Ouvre une connexion SSH interactive pour saisir ton mot de passe.') from None
    original = None
    handlers = {}
    characters = []
    decoder = codecs.getincrementaldecoder('utf-8')('strict')
    visible = 0
    mask_width = max(1, shutil.get_terminal_size((60, 24)).columns - len(prompt) - 2)
    def update_mask():
        nonlocal visible
        count = min(len(characters), mask_width)
        if count > visible:
            os.write(descriptor, b'*' * (count - visible))
        elif count < visible:
            os.write(descriptor, b'\b \b' * (visible - count))
        visible = count
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    try:
        original = termios.tcgetattr(descriptor)
        hidden = original[:]
        hidden[6] = original[6][:]
        hidden[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON)
        hidden[6][termios.VMIN] = 1
        hidden[6][termios.VTIME] = 0
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            handlers[signum] = signal.signal(signum, interrupted)
        termios.tcsetattr(descriptor, termios.TCSAFLUSH, hidden)
        os.write(descriptor, prompt.encode('utf-8'))
        while True:
            byte = os.read(descriptor, 1)
            if not byte or byte == b'\x04':
                raise SetupError('Saisie annulée.')
            if byte in (b'\r', b'\n'):
                if decoder.getstate()[0]:
                    raise SetupError('Saisie incomplète. Retape le mot de passe.')
                return ''.join(characters)
            if byte in (b'\x08', b'\x7f'):
                if decoder.getstate()[0]:
                    decoder.reset()
                elif characters:
                    characters.pop()
                    update_mask()
                continue
            if byte == b'\x15':
                characters.clear()
                update_mask()
                decoder.reset()
                continue
            if byte == b'\x1b':
                sequence = bytearray()
                deadline = time.monotonic() + 0.15
                while time.monotonic() < deadline and len(sequence) < 16:
                    ready, _, _ = select.select([descriptor], [], [], 0.02)
                    if not ready:
                        break
                    part = os.read(descriptor, 1)
                    if not part:
                        break
                    sequence.extend(part)
                    if len(sequence) == 1 and part not in (b'[', b'O'):
                        break
                    if len(sequence) > 1 and 0x40 <= part[0] <= 0x7E:
                        break
                continue
            if byte[0] < 32:
                continue
            try:
                character = decoder.decode(byte)
            except UnicodeDecodeError:
                raise SetupError('Caractère non reconnu. Retape le mot de passe.') from None
            if character:
                if len((''.join(characters) + character).encode('utf-8')) > 72:
                    raise SetupError('Mot de passe trop long : 72 octets maximum.')
                characters.append(character)
                update_mask()
    finally:
        if original is not None:
            with contextlib.suppress(OSError, termios.error):
                termios.tcsetattr(descriptor, termios.TCSAFLUSH, original)
        for signum, previous in handlers.items():
            signal.signal(signum, previous)
        with contextlib.suppress(OSError):
            os.write(descriptor, b'\n')
        os.close(descriptor)

def password_hash(args):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', args.username):
        raise SetupError('Identifiant : 1 a 32 lettres/chiffres/points/tirets.')
    if args.password_file:
        p = pathlib.Path(args.password_file)
        meta = p.lstat()
        if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o077 or meta.st_uid not in (0, int(os.environ.get('SUDO_UID', '0'))):
            raise SetupError('Fichier de mot de passe : fichier prive de son proprietaire, chmod 600.')
        password = p.read_text(encoding='utf-8').rstrip('\r\n')
    else:
        password = read_masked_password('Mot de passe admin : ')
    if len(password) < 12 or len(password.encode()) > 72:
        raise SetupError('Choisir un mot de passe entre 12 caracteres et 72 octets UTF-8.')
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()

def download(url, destination, maximum=80 * 1024 * 1024):
    request = urllib.request.Request(url, headers={'User-Agent': 'LiminalGuard/' + TOOL_VERSION})
    with urllib.request.urlopen(request, timeout=40) as response, open(destination, 'wb') as stream:
        if urllib.parse.urlsplit(response.url).scheme != 'https':
            raise SetupError('Redirection non HTTPS refusee.')
        size = 0
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            if size > maximum:
                raise SetupError('Telechargement anormalement volumineux.')
            stream.write(block)

def extract_binary(archive, target, arch):
    h = hashlib.sha256()
    with open(archive, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    if h.hexdigest() != DIGESTS[arch]:
        raise SetupError('SHA256 officiel incorrect : installation arretee avant activation.')

    with tarfile.open(archive, 'r:gz') as package:
        candidates = [m for m in package.getmembers() if pathlib.PurePosixPath(m.name).parts == ('AdGuardHome', 'AdGuardHome')]
        if len(candidates) != 1:
            raise SetupError('Executable officiel absent ou duplique dans l archive.')
        member = candidates[0]
        if not member.isfile() or member.size > 100 * 1024 * 1024:
            raise SetupError('Archive AdGuard inattendue.')
        with package.extractfile(member) as src, open(target, 'wb') as dst:
            shutil.copyfileobj(src, dst)
    os.chmod(target, 0o755)

def configuration(args, address, hashed_password, previous=None):
    cfg = copy.deepcopy(previous) if previous else {}
    cfg['schema_version'] = SCHEMA
    cfg.setdefault('http', {})['address'] = address + ':3000'
    if not previous:
        cfg['users'] = [{'name': args.username, 'password': hashed_password}]
    if not cfg.get('users') or any(not u.get('password', '').startswith(('$2a$', '$2b$', '$2y$')) for u in cfg['users']):
        raise SetupError('Compte administrateur bcrypt obligatoire.')
    cfg.update(auth_attempts=5, block_auth_min=15, language='fr', theme='auto')
    dns = cfg.setdefault('dns', {})
    dns.update(bind_hosts=[address], port=53, upstream_dns=args.upstream or UPSTREAMS,
               bootstrap_dns=['94.140.14.14', '94.140.15.15'], upstream_timeout='10s',
               anonymize_client_ip=True, cache_size=4194304, ratelimit=20,
               use_private_ptr_resolvers=False)
    filtering = cfg.setdefault('filtering', {})
    filtering.update(protection_enabled=True, filtering_enabled=True,
                     parental_enabled=not args.allow_adult, safebrowsing_enabled=True,
                     blocking_mode='default')
    if args.test_no_external_checks:
        filtering.update(parental_enabled=False, safebrowsing_enabled=False)
    cfg.setdefault('querylog', {}).update(enabled=False, file_enabled=False)
    cfg.setdefault('statistics', {})['enabled'] = False
    cfg.setdefault('dhcp', {})['enabled'] = False
    cfg.setdefault('tls', {})['enabled'] = False
    cfg.setdefault('clients', {})['runtime_sources'] = dict(whois=False, arp=False, rdns=False, dhcp=False, hosts=False)
    cfg.setdefault('log', {}).update(enabled=True, file='diagnostic.log', max_size=1,
                                     max_backups=1, max_age=3, compress=True, verbose=False)
    filters = cfg.setdefault('filters', [])
    official = next((f for f in filters if f.get('url') == (args.filter_url or FILTER_URL)), None)
    if official:
        official['enabled'] = True
    else:
        ids = {f['id'] for f in filters}
        filter_id = next(i for i in range(1, 100000) if i not in ids)
        filters.append(dict(enabled=True, url=args.filter_url or FILTER_URL, name='AdGuard DNS filter', id=filter_id))
    rules = cfg.setdefault('user_rules', [])
    marker = '||' + TEST_DOMAIN + '^'
    if marker not in rules:
        rules.append(marker)
    return cfg

def check_ports(address):
    for kind, port in [(socket.SOCK_STREAM, 3000), (socket.SOCK_STREAM, 53), (socket.SOCK_DGRAM, 53)]:
        with socket.socket(socket.AF_INET, kind) as probe:
            if kind == socket.SOCK_STREAM:

                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((address, port))
                if kind == socket.SOCK_STREAM:
                    probe.listen(1)
            except OSError:
                raise SetupError('Port {} occupe sur {} : aucun service existant ne sera coupe.'.format(port, address))

def dns_probe(address, domain=TEST_DOMAIN, tcp=False, port=53):
    labels = b''.join(bytes([len(x)]) + x.encode('ascii') for x in domain.split('.')) + b'\x00'
    ident = int.from_bytes(os.urandom(2), 'big')
    message = struct.pack('!HHHHHH', ident, 0x0100, 1, 0, 0, 0) + labels + struct.pack('!HH', 1, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM) as stream:
        stream.settimeout(3)
        if tcp:
            stream.connect((address, port))
            stream.sendall(struct.pack('!H', len(message)) + message)
            def exact(n):
                data = b''
                while len(data) < n:
                    part = stream.recv(n - len(data))
                    if not part:
                        raise SetupError('Reponse DNS TCP tronquee.')
                    data += part
                return data
            data = exact(struct.unpack('!H', exact(2))[0])
        else:
            stream.sendto(message, (address, port))
            data, _ = stream.recvfrom(65535)
    try:
        rid, flags, qd, an, _, _ = struct.unpack_from('!HHHHHH', data)
        if rid != ident or not flags & 0x8000 or flags & 0x000F or an < 1:
            raise SetupError('La resolution DNS a echoue : ' + domain)
        def skip_name(pos):
            while data[pos]:
                if data[pos] & 0xC0 == 0xC0:
                    return pos + 2
                pos += 1 + data[pos]
            return pos + 1
        pos = 12
        for _ in range(qd):
            pos = skip_name(pos) + 4
        values = []
        for _ in range(an):
            pos = skip_name(pos)
            typ, cls, ttl, length = struct.unpack_from('!HHIH', data, pos)
            pos += 10
            if typ == 1 and cls == 1 and length == 4:
                values.append(socket.inet_ntoa(data[pos:pos + 4]))
            pos += length
        return values
    except (IndexError, struct.error):
        raise SetupError('Réponse DNS mal formée ou tronquée.') from None


class Installer:
    def __init__(self, args):
        self.args = args
        self.root = pathlib.Path(args.test_root if args.test_mode else '/opt/AdGuardHome')
        self.cfg = self.root / 'AdGuardHome.yaml'
        self.binary = self.root / 'AdGuardHome'
        self.marker = self.root / MARKER
        self.unit = pathlib.Path('/etc/systemd/system') / UNIT
        self.process = None
        self.output = None
        self.ui = Console(args)

    def owned(self):
        if not self.marker.is_file() or self.root.is_symlink():
            raise SetupError('Installation existante non geree par RZU : aucun remplacement automatique.')
        if read_json(self.marker).get('owner') != 'rzu-adguard-home-v1':
            raise SetupError('Marqueur de propriete invalide.')

    def command(self):
        prefix = [self.args.runner] if self.args.runner else []
        return prefix + [str(self.binary), '--no-check-update', '-c', str(self.cfg), '-w', str(self.root / 'work')]

    def start(self):
        if self.args.test_mode:
            self.output = open(self.root / 'test-process.log', 'ab')
            self.process = subprocess.Popen(self.command(), cwd=str(self.root), stdout=self.output, stderr=self.output)
            atomic_write(self.root / 'test-pid', str(self.process.pid).encode())
        else:
            if not self.unit.exists():
                atomic_write(self.unit, self.service_file(), 0o644)
            elif 'Description=RZU AdGuard Home' not in self.unit.read_text():
                raise SetupError('Service non gere par RZU : activation refusee.')
            run(['systemctl', 'daemon-reload'])
            run(['systemctl', 'enable', '--now', UNIT])

    def running(self):
        if self.args.test_mode:
            path = self.root / 'test-pid'
            if not path.exists():
                return False
            cmd = pathlib.Path('/proc') / path.read_text().strip() / 'cmdline'
            return cmd.exists() and str(self.binary).encode() in cmd.read_bytes().split(b'\0')
        return subprocess.run(['systemctl', 'is-active', '--quiet', UNIT], check=False).returncode == 0

    def verify_binary(self):
        state = read_json(self.marker)
        if state.get('version') != VERSION:
            raise SetupError('Utiliser la version du script correspondant a cette installation avant de la modifier.')
        if file_hash(self.binary) != state.get('binary_sha256'):
            raise SetupError('Executable installe modifie ou endommage : activation refusee.')

    def stop(self):
        if self.args.test_mode:
            p = self.root / 'test-pid'
            if p.exists():
                pid = int(p.read_text())

                cmd = pathlib.Path('/proc') / str(pid) / 'cmdline'
                if cmd.exists() and str(self.binary).encode() in cmd.read_bytes().split(b'\0'):
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(pid, 15)
                    for _ in range(100):
                        status = pathlib.Path('/proc') / str(pid) / 'stat'
                        if not status.exists() or ') Z ' in status.read_text():
                            break
                        time.sleep(0.05)
                p.unlink()
        else:
            run(['systemctl', 'stop', UNIT])

    def service_file(self):
        root = str(self.root)
        return ('[Unit]\nDescription=RZU AdGuard Home - filtre DNS domestique\n'
                'Wants=network-online.target\nAfter=network-online.target\n'
                '[Service]\nType=simple\nExecStart=' + root + '/AdGuardHome --no-check-update -c ' + root + '/AdGuardHome.yaml -w ' + root + '/work\n'
                'WorkingDirectory=' + root + '\nRestart=on-failure\nRestartSec=5\nTimeoutStopSec=20\n'
                'UMask=0077\nNice=10\nNoNewPrivileges=true\nPrivateTmp=true\nPrivateDevices=true\n'
                'ProtectSystem=strict\nProtectHome=true\nProtectKernelTunables=true\n'
                'ProtectKernelModules=true\nProtectControlGroups=true\n'
                'CapabilityBoundingSet=CAP_NET_BIND_SERVICE\nReadWritePaths=' + root + '\n'
                'LogRateLimitIntervalSec=60s\nLogRateLimitBurst=20\n'
                '[Install]\nWantedBy=multi-user.target\n').encode()

    def verify(self, wait=False):
        self.owned()
        self.verify_binary()
        cfg = read_configuration(self.cfg.read_text())
        address = cfg['dns']['bind_hosts'][0]
        if cfg.get('querylog', {}).get('enabled', True) or cfg.get('querylog', {}).get('file_enabled', True) or cfg.get('statistics', {}).get('enabled', True):
            raise SetupError('Historique ou statistiques actifs : utiliser repair pour le profil sans historique.')
        if cfg.get('dhcp', {}).get('enabled'):
            raise SetupError('Le DHCP AdGuard est actif, contrairement au profil RZU.')
        if not cfg.get('filtering', {}).get('protection_enabled') or not cfg.get('filtering', {}).get('filtering_enabled'):
            raise SetupError('Le filtrage est desactive.')
        run(self.command() + ['--check-config'], capture_output=True, timeout=20)
        if not self.args.test_mode:
            run(['systemctl', 'is-enabled', '--quiet', UNIT])
            run(['systemctl', 'is-active', '--quiet', UNIT])
        error = None
        deadline = time.monotonic() + (120 if wait else 0)
        while True:
            try:
                enabled_filters = [f for f in cfg.get('filters', []) if f.get('enabled')]
                if not enabled_filters:
                    raise SetupError('Aucune liste de blocage active.')
                for item in enabled_filters:
                    cached = self.root / 'work' / 'data' / 'filters' / (str(item['id']) + '.txt')
                    if not cached.is_file() or cached.stat().st_size == 0:
                        raise SetupError('Liste de blocage pas encore telechargee : ' + item.get('name', str(item['id'])))
                for tcp in [False, True]:
                    if dns_probe(address, tcp=tcp) != ['0.0.0.0']:
                        raise SetupError('La regle de verification du blocage ne fonctionne pas.')
                answers = dns_probe(address, 'example.com')
                if not answers or '0.0.0.0' in answers:
                    raise SetupError('La resolution normale ne fonctionne pas.')
                try:
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    opener.open('http://' + address + ':3000/control/status', timeout=3)
                except urllib.error.HTTPError as exc:
                    if exc.code != 401:
                        raise
                else:
                    raise SetupError('Interface de controle sans authentification.')
                error = None
                break
            except (OSError, SetupError, ValueError) as exc:
                error = exc
                if not wait or time.monotonic() >= deadline:
                    break
                time.sleep(0.5)
        if error:
            raise SetupError('Verification fonctionnelle : ' + str(error))
        result = dict(ok=True, tool='LiminalGuard', tool_version=TOOL_VERSION, project_url=PROJECT_URL, version=VERSION, address=address, interface='http://' + address + ':3000',
                              dns_udp=True, dns_tcp=True, blocking=True, normal_resolution=True,
                              authenticated=True, history=False, statistics=False,
                              adult_blocking=bool(cfg['filtering'].get('parental_enabled')), test_mode=self.args.test_mode)
        self.ui.result(result, cfg['users'][0]['name'])

    def install(self):
        if self.root.exists():
            self.owned()
            self.verify_binary()
            if not self.running():
                current = read_configuration(self.cfg.read_text())
                check_ports(current['dns']['bind_hosts'][0])
                self.start()
                return self.verify(wait=True)
            return self.verify(wait=False)
        if not self.args.test_mode and (self.unit.exists() or pathlib.Path('/etc/systemd/system/AdGuardHome.service').exists()):
            raise SetupError('Un service AdGuard existe deja. Aucune installation superposee.')
        address = get_address(self.args)
        check_ports(address)
        hashed = password_hash(self.args)
        self.ui.progress(30)
        arch = architecture() if not self.args.runner_arch else self.args.runner_arch
        with tempfile.TemporaryDirectory(prefix='.rzu-adguard-', dir=str(self.root.parent)) as temporary:
            stage = pathlib.Path(temporary)
            package = stage / 'official.tar.gz'
            if self.args.archive:
                package = pathlib.Path(self.args.archive)
            else:
                url = 'https://github.com/AdguardTeam/AdGuardHome/releases/download/' + VERSION + '/AdGuardHome_linux_' + arch + '.tar.gz'
                download(url, package)
            target = stage / 'AdGuardHome'
            target.mkdir(mode=0o700)
            extract_binary(package, target / 'AdGuardHome', arch)
            (target / 'work').mkdir(mode=0o700)
            cfg = configuration(self.args, address, hashed)
            write_yaml(target / 'AdGuardHome.yaml', cfg)
            prefix = [self.args.runner] if self.args.runner else []
            run(prefix + [str(target / 'AdGuardHome'), '--check-config', '-c', str(target / 'AdGuardHome.yaml'), '-w', str(target / 'work')], capture_output=True, timeout=20)
            atomic_write(target / MARKER, json.dumps(dict(owner='rzu-adguard-home-v1', version=VERSION,
                         architecture=arch, binary_sha256=file_hash(target / 'AdGuardHome'))).encode())
            os.replace(target, self.root)
        if not self.args.test_mode:
            atomic_write(self.unit, self.service_file(), 0o644)
        self.ui.progress(65)
        try:
            self.start()
            self.ui.progress(90)
            self.verify(wait=True)
        except (Exception, KeyboardInterrupt):
            with contextlib.suppress(Exception):
                self.stop()
            if not self.args.test_mode:
                subprocess.run(['systemctl', 'disable', UNIT], check=False, capture_output=True)
            raise

    def repair(self):
        self.owned()
        self.verify_binary()
        address = get_address(self.args)
        old = self.cfg.read_bytes()
        previous = read_configuration(old)
        cfg = configuration(self.args, address, None, previous)

        check = self.root / 'pending-config.yaml'
        write_yaml(check, cfg)
        try:
            run(self.command()[:len(self.command()) - 4] + ['-c', str(check), '-w', str(self.root / 'work'), '--check-config'], capture_output=True, timeout=20)
        finally:
            check.unlink(missing_ok=True)
        backup = self.root / 'backups' / ('configuration-' + time.strftime('%Y%m%d-%H%M%S') + '.yaml')
        atomic_write(backup, old)
        self.stop()
        try:
            write_yaml(self.cfg, cfg)
            self.start()
            self.verify(wait=True)
        except (Exception, KeyboardInterrupt):
            self.stop()
            atomic_write(self.cfg, old)
            self.start()
            raise

    def remove(self):
        self.owned()
        if not self.args.test_mode:
            if not self.unit.exists() or 'Description=RZU AdGuard Home' not in self.unit.read_text():
                raise SetupError('Service absent ou non gere par RZU : aucune suppression.')
        self.stop()
        if not self.args.test_mode:
            run(['systemctl', 'disable', UNIT])
            self.unit.unlink()
            run(['systemctl', 'daemon-reload'])
        if self.args.json:
            print(json.dumps({'ok': True, 'removed': True, 'data_preserved': True, 'directory': str(self.root)}))
        else:
            self.ui.finish()

def arguments(argv=None):
    parser = argparse.ArgumentParser(prog='installer.sh', description='LiminalGuard : installer AdGuard Home sans historique DNS.')
    parser.add_argument('action', nargs='?', choices=['install', 'verify', 'repair', 'remove'], default='install')
    parser.add_argument('--ip')
    parser.add_argument('--interface')
    parser.add_argument('--username', default='admin')
    parser.add_argument('--password-file')
    parser.add_argument('--allow-adult', action='store_true')
    parser.add_argument('--archive', help='Archive officielle locale, SHA256 obligatoire.')
    parser.add_argument('--upstream', action='append')
    parser.add_argument('--filter-url')
    parser.add_argument('--json', action='store_true', help='Sortie pour un autre programme.')
    parser.add_argument('--color', choices=['auto', 'always', 'never'], default='auto')
    parser.add_argument('--test-mode', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--test-root', default='/tmp/rzu-adguard-test', help=argparse.SUPPRESS)
    parser.add_argument('--runner', help=argparse.SUPPRESS)
    parser.add_argument('--runner-arch', choices=sorted(DIGESTS), help=argparse.SUPPRESS)
    parser.add_argument('--test-no-external-checks', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.test_mode:
        if os.stat('/proc/self/ns/net').st_ino == os.stat('/proc/1/ns/net').st_ino:
            raise SetupError('Mode test refuse hors espace reseau prive.')
        root = pathlib.Path(args.test_root)
        if not root.is_absolute() or not str(root.resolve()).startswith('/tmp/rzu-') or root.is_symlink():
            raise SetupError('Racine de test attendue sous /tmp/rzu-.')
    elif args.runner or args.runner_arch or args.test_no_external_checks:
        raise SetupError('Emulation reservee aux tests isoles.')
    for url in (args.upstream or []) + ([args.filter_url] if args.filter_url else []):
        parsed = urllib.parse.urlsplit(url)
        local = args.test_mode and parsed.hostname in ['127.0.0.1', '127.0.0.2', 'localhost']
        if not parsed.hostname or parsed.username or parsed.password or (parsed.scheme != 'https' and not local) or any(c in url for c in '\r\n'):
            raise SetupError('Adresse de serveur/filtre invalide : HTTPS requis.')
    return args

def main():
    global UI_FOR_ERRORS
    os.umask(0o077)
    args = arguments()
    UI_FOR_ERRORS = Console(args)
    root = pathlib.Path(args.test_root if args.test_mode else '/opt/AdGuardHome')
    lock_path = pathlib.Path('/tmp/rzu-adguard-' + hashlib.sha256(str(root).encode()).hexdigest()[:16] + '.lock') if args.test_mode else pathlib.Path('/run/lock/rzu-adguard-home.lock')
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SetupError('Une autre operation RZU est en cours.')
        installer = Installer(args)
        installer.ui.header(args.action)
        getattr(installer, args.action)()

if __name__ == '__main__':
    try:
        main()
    except (SetupError, OSError, ValueError, subprocess.SubprocessError, yaml.YAMLError, tarfile.TarError) as exc:
        class ErrorOptions:
            json = '--json' in sys.argv
            color = 'auto'
        (UI_FOR_ERRORS or Console(ErrorOptions())).failure(exc)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nOpération annulée.', file=sys.stderr)
        sys.exit(130)
PY_RZU
