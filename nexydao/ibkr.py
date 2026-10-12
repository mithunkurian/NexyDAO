"""Bounded, read-only legacy TWS wire probe; no SDK or order messages.

Negotiates protocol 100..178, before protobuf. Gateway compatibility is checked
at connection time. This module is not available as an agent tool.
"""
import hashlib
import json
import os
import re
import socket
import struct
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

TAGS = ("NetLiquidation", "TotalCashValue", "AvailableFunds", "BuyingPower")
MAX_FRAME = 65536
WARNINGS = {2104, 2106, 2107, 2108, 2158}
PAPER_ACCOUNT_PATTERN = r"DU[A-Z]*[0-9]+"


class ProbeError(RuntimeError):
    """Curated errors only; never include broker payloads or account identifiers."""


@dataclass(frozen=True)
class BrokerConfig:
    host: str = "127.0.0.1"
    port: int = 4002
    client_id: int = 91
    timeout: int = 15
    expected_account: str = field(default="", repr=False)
    snapshot: Path = Path("data/ibkr-paper-snapshot.json")

    def __post_init__(self):
        if self.host != "127.0.0.1" or self.port != 4002:
            raise ValueError("Only localhost paper port 4002 is permitted")
        if not 1 <= self.client_id <= 9999 or not 1 <= self.timeout <= 60:
            raise ValueError("Invalid bounded broker settings")
        if self.expected_account and not re.fullmatch(PAPER_ACCOUNT_PATTERN, self.expected_account):
            raise ValueError("Expected account must be in the paper DU namespace")

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("NEXYDAO_IBKR_HOST", "127.0.0.1"),
                   int(os.environ.get("NEXYDAO_IBKR_PORT", "4002")),
                   int(os.environ.get("NEXYDAO_IBKR_CLIENT_ID", "91")),
                   int(os.environ.get("NEXYDAO_IBKR_TIMEOUT_SECONDS", "15")),
                   os.environ.get("NEXYDAO_IBKR_EXPECTED_ACCOUNT", ""),
                   Path(os.environ.get("NEXYDAO_IBKR_SNAPSHOT", "data/ibkr-paper-snapshot.json")))


def paper_account(accounts, expected=""):
    # Reject mixed/live/advisor account lists rather than choosing the first entry.
    values = accounts.split(",")
    if len(values) != 1 or not re.fullmatch(PAPER_ACCOUNT_PATTERN, values[0]):
        raise ProbeError("single_paper_account_required")
    if expected and values[0] != expected:
        raise ProbeError("account_mismatch")
    return values[0]


def readonly_message(command, client_id=91):
    # Closed set of complete outbound messages, not arbitrary message IDs/payloads.
    messages = {
        "start": (71, 2, client_id, ""),
        "accounts": (17, 1),
        "summary": (62, 1, 9101, "All", ",".join(TAGS)),
        "cancel_summary": (63, 1, 9101),
    }
    if command not in messages:
        raise PermissionError("Broker mutation commands are unavailable")
    return ("\0".join(str(v) for v in messages[command]) + "\0").encode("ascii")


class Wire:
    def __init__(self, sock, deadline):
        self.sock, self.deadline = sock, deadline

    def receive_exact(self, length):
        data = bytearray()
        while len(data) < length:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise ProbeError("broker_timeout")
            self.sock.settimeout(remaining)
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise ProbeError("broker_disconnected")
            data.extend(chunk)
        return bytes(data)

    def receive(self):
        length = struct.unpack("!I", self.receive_exact(4))[0]
        if not 1 <= length <= MAX_FRAME:
            raise ProbeError("invalid_broker_frame")
        data = self.receive_exact(length)
        if not data.endswith(b"\0"):
            raise ProbeError("invalid_broker_fields")
        return data[:-1].decode("utf-8").split("\0")

    def send(self, command, client_id=91):
        body = readonly_message(command, client_id)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProbeError("broker_timeout")
        self.sock.settimeout(remaining)
        self.sock.sendall(struct.pack("!I", len(body)) + body)


def check_error(fields):
    if fields[0] == "4":
        if len(fields) < 4 or int(fields[3]) not in WARNINGS:
            raise ProbeError("broker_reported_error")


def probe(config, connector=socket.create_connection):
    deadline = time.monotonic() + config.timeout
    with connector((config.host, config.port), timeout=config.timeout) as sock:
        # The only direct write is the fixed protocol negotiation, never an order.
        hello = b"v100..178"
        sock.sendall(b"API\0" + struct.pack("!I", len(hello)) + hello)
        wire = Wire(sock, deadline)
        handshake = wire.receive()
        if len(handshake) != 2 or not 100 <= int(handshake[0]) <= 178:
            raise ProbeError("unsupported_protocol_version")
        wire.send("start", config.client_id)
        wire.send("accounts")
        account = None
        while account is None:
            fields = wire.receive()
            check_error(fields)
            if fields[0] == "15":
                if len(fields) != 3:
                    raise ProbeError("invalid_account_response")
                account = paper_account(fields[2], config.expected_account)
        wire.send("summary")
        values = {}
        try:
            while True:
                fields = wire.receive()
                check_error(fields)
                if fields[0] == "15":
                    if len(fields) != 3 or paper_account(fields[2], account) != account:
                        raise ProbeError("account_changed_during_summary")
                elif fields[0] == "63":
                    if len(fields) != 7 or fields[2] != "9101" or fields[3] != account:
                        raise ProbeError("unexpected_summary_account_or_request")
                    tag, value, currency = fields[4:]
                    if not re.fullmatch(r'-?[0-9]{1,16}(?:\.[0-9]{1,12})?', value):
                        raise ProbeError("invalid_account_value")
                    number = Decimal(value)
                    if tag not in TAGS or not number.is_finite() or not re.fullmatch(r"[A-Z]{3}", currency):
                        raise ProbeError("invalid_account_value")
                    key = (tag, currency)
                    if key in values:
                        raise ProbeError("duplicate_account_value")
                    if len(values) >= 40:
                        raise ProbeError("account_summary_size_limit")
                    values[key] = value
                elif fields[0] == "64":
                    if fields != ["64", "1", "9101"]:
                        raise ProbeError("unexpected_summary_end")
                    if set(tag for tag, _ in values) != set(TAGS):
                        raise ProbeError("incomplete_account_summary")
                    break
        finally:
            # Disconnect is sufficient if the deadline/connection no longer permits cancellation.
            try:
                wire.send("cancel_summary")
            except (OSError, ProbeError):
                pass
    return {"schema_version": 1, "source": "ibkr_gateway_account_summary",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "protocol_version": int(handshake[0]), "account": account,
            "paper_identity_evidence": "single_DU_account_namespace",
            "expected_account_matched": bool(config.expected_account),
            "execution_authorized": False,
            "values": [{"tag": tag, "currency": currency, "value": value}
                       for (tag, currency), value in sorted(values.items())]}


def save_snapshot(path, snapshot):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, sort_keys=True, indent=2).encode("utf-8")
    fd, name = tempfile.mkstemp(prefix="ibkr-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return hashlib.sha256(payload).hexdigest()


def run_check(config):
    snapshot = probe(config)
    digest = save_snapshot(config.snapshot, snapshot)
    # Account IDs and balances stay in the private local snapshot, not stdout/AI memory.
    return {"status": "read_only_account_check_passed", "paper_identity_evidence": snapshot["paper_identity_evidence"],
            "expected_account_matched": snapshot["expected_account_matched"],
            "summary_values_received": len(snapshot["values"]), "snapshot_sha256": digest,
            "execution_authorized": False}
