import json
import os
import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from nexydao.ibkr import (BrokerConfig, ProbeError, Wire, TAGS, MAX_FRAME,
                          paper_account, probe, readonly_message, save_snapshot)
from nexydao.safety import PaperBroker


def frame(*fields):
    body = ("\0".join(str(f) for f in fields) + "\0").encode()
    return struct.pack("!I", len(body)) + body


class Socket:
    def __init__(self, data):
        self.data, self.sent, self.closed = bytearray(data), [], False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def settimeout(self, timeout):
        pass

    def sendall(self, value):
        self.sent.append(value)

    def recv(self, length):
        # Deliberately split headers and payloads across arbitrary TCP reads.
        count = min(length, 3, len(self.data))
        chunk = bytes(self.data[:count])
        del self.data[:count]
        return chunk


class BrokerTests(unittest.TestCase):
    def session(self, accounts="DU12345", rows=None, end=True):
        rows = rows if rows is not None else [frame(63, 1, 9101, accounts, tag, "123.45", "USD") for tag in TAGS]
        return Socket(frame(178, "broker-time") + frame(9, 1, 999) + frame(15, 1, accounts)
                      + b"".join(rows) + (frame(64, 1, 9101) if end else b""))

    def test_probe_sends_only_exact_readonly_messages_and_closes(self):
        sock = self.session()
        result = probe(BrokerConfig(expected_account="DU12345"), lambda *a, **k: sock)
        self.assertTrue(sock.closed)
        self.assertFalse(result["execution_authorized"])
        self.assertTrue(result["expected_account_matched"])
        self.assertEqual(len(result["values"]), 4)
        self.assertEqual(sock.sent[0], b"API\0" + struct.pack("!I", 9) + b"v100..178")
        self.assertEqual(sock.sent[1:], [struct.pack("!I", len(body)) + body for body in
                                      (readonly_message(c) for c in ("start", "accounts", "summary", "cancel_summary"))])

    def test_rejects_live_or_ambiguous_accounts_before_summary(self):
        for accounts in ("U12345", "DU123,U999", "DU123,DU456", "DU", "", "DU123,", "DF123"):
            with self.subTest(accounts=accounts):
                sock = self.session(accounts)
                with self.assertRaises(ProbeError):
                    probe(BrokerConfig(), lambda *a, **k: sock)
                self.assertEqual(len(sock.sent), 3)
                self.assertTrue(sock.closed)

    def test_expected_account_mismatch_blocks_summary(self):
        sock = self.session()
        with self.assertRaises(ProbeError):
            probe(BrokerConfig(expected_account="DU999"), lambda *a, **k: sock)
        self.assertEqual(len(sock.sent), 3)

    def test_regional_paper_account_format(self):
        sock = self.session(accounts="DUH12345")
        result = probe(BrokerConfig(expected_account="DUH12345"), lambda *a, **k: sock)
        self.assertTrue(result['expected_account_matched'])
        self.assertEqual(len(result['values']), 4)
        self.assertFalse(result['execution_authorized'])

    def test_localhost_paper_port_is_fixed(self):
        for kwargs in ({"host": "35.184.88.154"}, {"port": 4001}, {"expected_account": "U123"},
                       {"timeout": 0}, {"timeout": 61}, {"client_id": 0}):
            with self.assertRaises(ValueError):
                BrokerConfig(**kwargs)

    def test_environment_configuration(self):
        with patch.dict(os.environ, {"NEXYDAO_IBKR_EXPECTED_ACCOUNT": "DU123", "NEXYDAO_IBKR_CLIENT_ID": "95"}, clear=True):
            config = BrokerConfig.from_env()
            self.assertEqual(config.client_id, 95)
            self.assertNotIn("DU123", repr(config))

    def test_mutation_commands_unavailable(self):
        for command in ("placeOrder", "cancelOrder", "reqGlobalCancel", "execute", 3):
            with self.assertRaises(PermissionError):
                readonly_message(command)
        with self.assertRaises(PermissionError):
            PaperBroker().execute()

    def test_malformed_or_incomplete_summary_fails_closed(self):
        rows = [frame(63, 1, 9101, "DU12345", tag, "1", "USD") for tag in TAGS]
        cases = [rows[:1], rows + rows[:1], [frame(63, 1, 9101, "U123", "NetLiquidation", "1", "USD")],
                 [frame(63, 1, 9101, "DU12345", "NetLiquidation", "NaN", "USD")],
                 [frame(63, 1, 9101, "DU12345", "UnexpectedTag", "1", "USD")],
                 [frame(63, 1, 999, "DU12345", "NetLiquidation", "1", "USD")],
                 [frame(4, 2, -1, 502, "sensitive error text")]]
        for rows in cases:
            with self.subTest(rows=rows):
                with self.assertRaises(ProbeError) as error:
                    probe(BrokerConfig(), lambda *a, **k: self.session(rows=rows))
                self.assertNotIn("sensitive", str(error.exception))

    def test_disconnect_before_end_rejected(self):
        with self.assertRaises(ProbeError):
            probe(BrokerConfig(), lambda *a, **k: self.session(end=False))

    def test_account_change_during_summary_rejected(self):
        sock = self.session(rows=[frame(15, 1, "U12345")])
        with self.assertRaises(ProbeError):
            probe(BrokerConfig(), lambda *a, **k: sock)
        self.assertTrue(sock.closed)

    def test_failed_probe_preserves_last_snapshot(self):
        from nexydao.ibkr import run_check
        root = Path(__file__).resolve().parents[1] / "data"
        with tempfile.TemporaryDirectory(dir=root) as folder:
            path = Path(folder) / "snapshot.json"
            path.write_text('previous snapshot')
            with patch('nexydao.ibkr.probe', side_effect=ProbeError('account_mismatch')):
                with self.assertRaises(ProbeError):
                    run_check(BrokerConfig(snapshot=path))
            self.assertEqual(path.read_text(), 'previous snapshot')

    def test_oversize_frame_and_deadline_rejected(self):
        wire = Wire(Socket(struct.pack("!I", MAX_FRAME + 1)), time.monotonic() + 1)
        with self.assertRaises(ProbeError):
            wire.receive()
        with self.assertRaises(ProbeError):
            Wire(Socket(b""), time.monotonic() - 1).receive()

    def test_snapshot_persisted_atomically(self):
        root = Path(__file__).resolve().parents[1] / "data"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            path = Path(folder) / "snapshot.json"
            digest = save_snapshot(path, {"execution_authorized": False})
            self.assertEqual(len(digest), 64)
            self.assertFalse(json.loads(path.read_text())["execution_authorized"])
            self.assertEqual(list(Path(folder).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
