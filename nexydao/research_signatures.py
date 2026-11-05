"""Opt-in Ed25519 SEC receipt signatures using a protected OpenSSL executable.

Only the collector reads private material. Consumers pin a public DER key.
No shell, key generation, login prompts or automatic key trust occurs here.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

PUBLIC_PREFIX = bytes.fromhex('302a300506032b6570032100')
DOMAIN = b'NexyDAO:sec-research:ed25519:v1\x00'
DEFAULT_OPENSSL = Path('/usr/bin/openssl' if os.name == 'posix' else 'C:/Program Files/Git/usr/bin/openssl.exe')


class ReceiptSignatureError(ValueError):
    """Fixed codes only; never include key paths or OpenSSL output."""


def _read(path, limit, private=False):
    if path is None:
        raise ReceiptSignatureError('research_signature_key_required')
    path = Path(path)
    try:
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0)
        with os.fdopen(os.open(path, flags), 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or (os.name == 'posix' and info.st_mode & (0o077 if private else 0o022)):
                raise ReceiptSignatureError('research_signature_key_permissions')
            raw = stream.read(limit+1)
    except OSError:
        raise ReceiptSignatureError('research_signature_key_unavailable') from None
    if not raw or len(raw) > limit:
        raise ReceiptSignatureError('research_signature_key_size')
    return raw


def public_key(path, pin):
    if not isinstance(pin, str) or not re.fullmatch('[0-9a-f]{64}', pin):
        raise ReceiptSignatureError('research_public_key_pin_required')
    raw = _read(path, 44)
    if len(raw) != 44 or not raw.startswith(PUBLIC_PREFIX) or hashlib.sha256(raw).hexdigest() != pin:
        raise ReceiptSignatureError('research_public_key_mismatch')
    return raw


def _command(executable, arguments):
    executable = Path(executable)
    if not executable.is_absolute():
        raise ReceiptSignatureError('absolute_openssl_path_required')
    try:
        executable = executable.resolve(strict=True)
        info = executable.stat()
        if not stat.S_ISREG(info.st_mode) or (os.name == 'posix' and info.st_mode & 0o022):
            raise ReceiptSignatureError('protected_openssl_required')
        if os.name == 'posix':
            for component in (executable, *executable.parents):
                info = component.stat()
                if info.st_uid != 0 or info.st_mode & 0o022:
                    raise ReceiptSignatureError('protected_openssl_required')
        env = {'PATH': os.defpath, 'OPENSSL_CONF': os.devnull}
        if os.name == 'nt':
            env['SYSTEMROOT'] = os.environ.get('SYSTEMROOT', 'C:/Windows')
        result = subprocess.run([str(executable), *arguments], stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=5, check=True, env=env)
        if len(result.stdout) > 2048:
            raise ReceiptSignatureError('research_signature_output_limit')
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        raise ReceiptSignatureError('research_signature_tool_failure') from None


def _write(folder, name, raw):
    path = Path(folder)/name
    # Exclusive creation inside a private temporary directory. Windows ACLs
    # remain an operator requirement, as for the existing HMAC receipt key.
    with path.open('xb') as stream:
        if os.name == 'posix':
            os.fchmod(stream.fileno(), 0o600)
        stream.write(raw)
    return str(path)


def check_signer(private_path, public_path, pin, executable):
    trusted = public_key(public_path, pin)
    private = _read(private_path, 2048, private=True)
    with tempfile.TemporaryDirectory(prefix='nexydao-sec-sign-') as folder:
        key = _write(folder, 'key.pem', private)
        derived = _command(executable, ['pkey', '-in', key, '-passin', 'pass:', '-pubout', '-outform', 'DER'])
    if derived != trusted:
        raise ReceiptSignatureError('research_signing_key_mismatch')


def _message(payload, domain=DOMAIN):
    try:
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    except (TypeError, ValueError):
        raise ReceiptSignatureError('invalid_public_research_payload') from None
    if len(raw) > 64000:
        raise ReceiptSignatureError('research_signature_payload_limit')
    return domain+raw


def sign(payload, private_path, public_path, pin, executable, *, domain=DOMAIN):
    check_signer(private_path, public_path, pin, executable)
    private = _read(private_path, 2048, private=True)
    with tempfile.TemporaryDirectory(prefix='nexydao-sec-sign-') as folder:
        key = _write(folder, 'key.pem', private)
        message = _write(folder, 'message', _message(payload, domain))
        signature = _command(executable, ['pkeyutl', '-sign', '-rawin', '-inkey', key,
                                          '-passin', 'pass:', '-in', message])
    if len(signature) != 64:
        raise ReceiptSignatureError('research_signature_size')
    receipt = {'payload': payload, 'signature': signature.hex(), 'algorithm': 'ed25519', 'key_sha256': pin}
    verify(receipt, public_path, pin, executable, domain=domain)
    return receipt


def verify(receipt, public_path, pin, executable, *, domain=DOMAIN):
    if (not isinstance(receipt, dict) or set(receipt) != {'payload', 'signature', 'algorithm', 'key_sha256'}
            or receipt['algorithm'] != 'ed25519' or receipt['key_sha256'] != pin
            or not isinstance(receipt['signature'], str) or not re.fullmatch('[0-9a-f]{128}', receipt['signature'])):
        raise ReceiptSignatureError('invalid_public_research_signature')
    trusted = public_key(public_path, pin)
    with tempfile.TemporaryDirectory(prefix='nexydao-sec-verify-') as folder:
        key = _write(folder, 'public.der', trusted)
        message = _write(folder, 'message', _message(receipt['payload'], domain))
        signature = _write(folder, 'signature', bytes.fromhex(receipt['signature']))
        _command(executable, ['pkeyutl', '-verify', '-rawin', '-pubin', '-keyform', 'DER',
                              '-inkey', key, '-in', message, '-sigfile', signature])
