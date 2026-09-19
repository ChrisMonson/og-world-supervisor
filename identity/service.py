#!/usr/bin/env python3
"""Connection identity, kept apart from the world.

A returning visitor is recognised by a token their browser holds. That token is
exchanged here, directly, for a ticket: a single-use, per-connection value that
means nothing on its own. The world is handed only the ticket, and learns from it
only which character to put on the other end of the socket.

Nothing the world holds or is told survives a character's death in a form that
would join one life to the next. The record that does is here, behind a separate
key that only the supervisor has.
"""

import json
import os
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.environ.get("IDENTITY_DB", "/identity/identity.db")
WORLD_KEY = os.environ.get("IDENTITY_WORLD_KEY", "")
ADMIN_KEY = os.environ.get("IDENTITY_ADMIN_KEY", "")
PORT = int(os.environ.get("IDENTITY_PORT", "8090"))

# A ticket must be redeemed promptly, then stays usable for the connection's life.
REDEEM_WINDOW = int(os.environ.get("IDENTITY_REDEEM_WINDOW", "300"))
TICKET_LIFETIME = int(os.environ.get("IDENTITY_TICKET_LIFETIME", "86400"))

_lock = threading.Lock()
_db = sqlite3.connect(DB_PATH, check_same_thread=False)
_db.row_factory = sqlite3.Row


def setup():
    with _lock:
        _db.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS accounts (
                token        TEXT PRIMARY KEY,
                created_at   INTEGER NOT NULL,
                last_seen_at INTEGER NOT NULL,
                character_id TEXT
            );

            CREATE TABLE IF NOT EXISTS character_history (
                character_id TEXT PRIMARY KEY,
                token        TEXT    NOT NULL,
                name         TEXT    NOT NULL,
                born_at      INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS ix_history_token ON character_history (token, born_at);

            CREATE TABLE IF NOT EXISTS tickets (
                ticket     TEXT PRIMARY KEY,
                token      TEXT    NOT NULL,
                issued_at  INTEGER NOT NULL,
                redeemed_at INTEGER
            );

            CREATE INDEX IF NOT EXISTS ix_tickets_token ON tickets (token);
        """)
        _db.commit()


def now():
    return int(time.time())


def issue_ticket(token):
    """Exchanges a visitor's token for a ticket. Mints a token if they have none."""
    with _lock:
        if not token or not isinstance(token, str) or len(token) > 128:
            token = secrets.token_hex(24)

        moment = now()
        _db.execute("""
            INSERT INTO accounts (token, created_at, last_seen_at) VALUES (?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET last_seen_at = excluded.last_seen_at
        """, (token, moment, moment))

        ticket = secrets.token_hex(24)
        _db.execute("INSERT INTO tickets (ticket, token, issued_at) VALUES (?, ?, ?)",
                    (ticket, token, moment))

        # Tickets are per-connection and short-lived; old ones are not kept around.
        _db.execute("DELETE FROM tickets WHERE issued_at < ?", (moment - TICKET_LIFETIME,))
        _db.commit()

        return {"token": token, "ticket": ticket}


def _ticket_row(ticket, require_unredeemed=False):
    row = _db.execute("SELECT * FROM tickets WHERE ticket = ?", (ticket,)).fetchone()

    if row is None:
        return None

    if now() - row["issued_at"] > TICKET_LIFETIME:
        return None

    if require_unredeemed:
        if row["redeemed_at"] is not None:
            return None
        if now() - row["issued_at"] > REDEEM_WINDOW:
            return None

    return row


def redeem(ticket):
    """The world asks who is on the other end. It gets a character, never a token."""
    with _lock:
        row = _ticket_row(ticket, require_unredeemed=True)

        if row is None:
            return None

        _db.execute("UPDATE tickets SET redeemed_at = ? WHERE ticket = ?", (now(), ticket))
        account = _db.execute("SELECT character_id FROM accounts WHERE token = ?",
                              (row["token"],)).fetchone()
        _db.commit()

        return {"characterId": account["character_id"] if account else None}


def bind(ticket, character_id, name):
    """The world reports which character it created for this connection."""
    with _lock:
        row = _ticket_row(ticket)

        if row is None:
            return None

        _db.execute("UPDATE accounts SET character_id = ? WHERE token = ?",
                    (character_id, row["token"]))
        _db.execute("""
            INSERT OR IGNORE INTO character_history (character_id, token, name, born_at)
            VALUES (?, ?, ?, ?)
        """, (character_id, row["token"], name, now()))
        _db.commit()

        return {"ok": True}


def release(ticket):
    """The character on this connection is finished. Nothing carries forward."""
    with _lock:
        row = _ticket_row(ticket)

        if row is None:
            return None

        _db.execute("UPDATE accounts SET character_id = NULL WHERE token = ?", (row["token"],))
        _db.commit()

        return {"ok": True}


def lineage(token=None):
    """For the supervisor only: which characters belonged to the same hands."""
    with _lock:
        if token:
            rows = _db.execute(
                "SELECT character_id, name, born_at FROM character_history WHERE token = ? ORDER BY born_at",
                (token,)).fetchall()
            return {"token": token, "characters": [dict(row) for row in rows]}

        rows = _db.execute(
            "SELECT token, character_id, name, born_at FROM character_history ORDER BY token, born_at"
        ).fetchall()

        grouped = {}
        for row in rows:
            grouped.setdefault(row["token"], []).append({
                "characterId": row["character_id"],
                "name": row["name"],
                "bornAt": row["born_at"],
            })

        return {"lineages": [{"token": token, "characters": characters}
                             for token, characters in grouped.items()]}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # The access log would be a record of who connected when.

    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_chunked(self, cap=8192):
        """Some clients send chunked bodies rather than a length."""
        body = b""

        while True:
            line = self.rfile.readline(64).strip()

            if not line:
                return body

            try:
                size = int(line.split(b";")[0], 16)
            except ValueError:
                return body

            if size == 0:
                self.rfile.readline(8)  # trailing CRLF
                return body

            body += self.rfile.read(size)
            self.rfile.readline(8)

            if len(body) > cap:
                return body[:cap]

    def _body(self):
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            raw = self._read_chunked()
        else:
            length = int(self.headers.get("Content-Length") or 0)

            if length <= 0 or length > 8192:
                return {}

            raw = self.rfile.read(length)

        try:
            return json.loads(raw.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _authorised(self, header, expected):
        supplied = self.headers.get(header, "")
        return bool(expected) and secrets.compare_digest(supplied, expected)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok"})

        if self.path.startswith("/lineage"):
            if not self._authorised("X-Identity-Admin", ADMIN_KEY):
                return self._send(401, {"error": "unauthorised"})

            parts = self.path.split("/")
            token = parts[2] if len(parts) > 2 and parts[2] else None
            return self._send(200, lineage(token))

        self._send(404, {"error": "not found"})

    def do_POST(self):
        body = self._body()

        # The only route a browser calls, and the only one that handles a token.
        if self.path == "/tickets":
            return self._send(200, issue_ticket(body.get("token")))

        if not self._authorised("X-Identity-Key", WORLD_KEY):
            return self._send(401, {"error": "unauthorised"})

        ticket = body.get("ticket") or ""

        if self.path == "/tickets/redeem":
            result = redeem(ticket)
        elif self.path == "/tickets/bind":
            result = bind(ticket, body.get("characterId") or "", body.get("name") or "")
        elif self.path == "/tickets/release":
            result = release(ticket)
        else:
            return self._send(404, {"error": "not found"})

        return self._send(200, result) if result else self._send(404, {"error": "unknown ticket"})


def main():
    if not WORLD_KEY or not ADMIN_KEY:
        raise SystemExit("IDENTITY_WORLD_KEY and IDENTITY_ADMIN_KEY must both be set.")

    setup()
    print(f"identity listening on {PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
