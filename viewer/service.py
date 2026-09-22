"""A window onto the caretaker's turns, for reading from somewhere else.

Supervisor plane. Nothing here is reachable from the world, and nothing the
caretaker can do reaches this: it has no shell, no network tools and no way to
name a port. That is deliberate rather than incidental -- its own transcripts are
the worst thing it could read, and every leak this project has had came from
something built for our convenience.

Read-only by construction: it opens files and serves them. There is no route
that writes anything.
"""

import html
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

import render  # noqa: E402

SUPERVISOR = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get("STATE_DIR", SUPERVISOR / "state"))
TURNS = STATE / "agent" / "turns"
TOKEN = os.environ.get("VIEWER_TOKEN", "")

# A turn whose file has not been touched for this long is over, whatever the
# absence of a turn record says. A record is only written when a turn completes,
# so a crashed turn would otherwise stay "live" forever.
STALE_AFTER = 120


def turns():
    """Every turn, newest first, with whatever is known about each."""
    found = []

    for path in sorted(TURNS.glob("*.transcript.jsonl"), reverse=True):
        name = path.name.replace(".transcript.jsonl", "")
        when, _, kind = name.rpartition("-")
        record = TURNS / f"{name}.json"
        age = time.time() - path.stat().st_mtime

        entry = {
            "name": name,
            "kind": kind,
            "when": when,
            "live": not record.exists() and age < STALE_AFTER,
            "abandoned": not record.exists() and age >= STALE_AFTER,
            "bytes": path.stat().st_size,
        }

        if record.exists():
            try:
                entry.update(json.loads(record.read_text()))
            except (OSError, json.JSONDecodeError):
                pass

        found.append(entry)

    return found


def when_reads(stamp):
    try:
        moment = datetime.strptime(stamp, "%Y-%m-%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return moment.astimezone().strftime("%a %H:%M:%S")
    except ValueError:
        return stamp


def as_html(markdown):
    """
    The turn as render.py already writes it, kept as laid out. Enough inline
    formatting to read; no dependency, and no attempt at a markdown engine.
    """
    text = html.escape(markdown)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+?)`", r"<code>\1</code>", text)
    text = re.sub(r"^(#{1,3}) (.+)$", r'<span class="h">\2</span>', text, flags=re.M)
    return text


STYLE = """
:root { color-scheme: dark; --bg:#14161a; --fg:#d6d9de; --dim:#7d848f;
        --line:#272b32; --live:#6fd08c; --link:#8ab4f8; }
* { box-sizing: border-box; }
body { background:var(--bg); color:var(--fg); margin:0;
       font:14px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;
       -webkit-text-size-adjust:100%; }
header { position:sticky; top:0; z-index:2; background:var(--bg);
         border-bottom:1px solid var(--line); padding:12px 16px;
         display:flex; gap:10px 14px; align-items:baseline; flex-wrap:wrap; }
h1 { font-size:15px; margin:0; font-weight:600; overflow-wrap:anywhere; }
.meta { color:var(--dim); font-size:12px; }
main { padding:12px 16px 60px; max-width:900px; }
a { color:var(--link); text-decoration:none; }

/* One turn: a row on a wide screen, a stacked card on a narrow one. */
.turn { display:block; padding:11px 0; border-bottom:1px solid var(--line);
        color:var(--fg); }
.turn:active { background:#1b1e24; }
.top { display:flex; flex-wrap:wrap; gap:6px 12px; align-items:baseline; }
.when { color:var(--link); }
.kind { color:var(--dim); }
.took { margin-left:auto; }
.said { color:var(--dim); margin-top:3px; overflow-wrap:anywhere; }

.live { color:var(--live); }
.dot { display:inline-block; width:7px; height:7px; border-radius:50%;
       background:var(--live); margin-right:5px; animation:p 1.4s infinite; }
@keyframes p { 50% { opacity:.25 } }

pre { white-space:pre-wrap; overflow-wrap:anywhere; word-break:break-word;
      margin:0; font-size:13px; }
code { color:#c3e88d; }
b { color:#fff; font-weight:600; }
.h { display:block; color:#fff; font-weight:600; margin:16px 0 4px; }
.back { display:inline-block; margin-bottom:12px; }

@media (max-width:640px) {
    body { font-size:13px; }
    pre { font-size:12px; line-height:1.5; }
    .took { margin-left:0; }
}
"""


def page(title, body, refresh=0):
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{meta}<title>{html.escape(title)}</title><style>{STYLE}</style></head>
<body>{body}</body></html>"""


def index():
    cards = []

    for entry in turns():
        if entry["live"]:
            state = '<span class="live"><span class="dot"></span>running</span>'
            detail = f"{entry['bytes'] // 1024} KB so far"
        elif entry["abandoned"]:
            state = '<span class="meta">unfinished</span>'
            detail = ""
        else:
            state = f"{entry.get('elapsed', '?')}s"
            detail = f"{entry.get('turns', '?')} steps"
            if entry.get("tokensPerSecond"):
                detail += f" · {entry['tokensPerSecond']} tok/s"
            if entry.get("cost"):
                detail += f" · ${entry['cost']:.2f}"

        said = (entry.get("text") or "").strip().split("\n")[0][:160]

        cards.append(
            f"<a class=turn href='/turn/{entry['name']}'>"
            f"<div class=top><span class=when>{when_reads(entry['when'])}</span>"
            f"<span class=kind>{entry['kind']}</span>"
            f"<span class=took>{state}</span></div>"
            f"<div class=meta>{detail}</div>"
            + (f"<div class=said>{html.escape(said)}</div>" if said else "")
            + "</a>")

    found = turns()
    run = (STATE / "current-run").read_text().strip() if (STATE / "current-run").exists() else "?"
    model = (STATE / "run-model").read_text().strip() if (STATE / "run-model").exists() else "?"

    body = (f"<header><h1>{html.escape(run)}</h1>"
            f"<span class=meta>{html.escape(model)} · {len(found)} turns</span></header>"
            "<main>" + "".join(cards) + "</main>")

    return page(run, body, refresh=10 if any(e["live"] for e in found) else 30)


def turn(name):
    path = TURNS / f"{name}.transcript.jsonl"

    if not path.exists() or ".." in name or "/" in name:
        return None

    events = render.load(path)
    text = render.header(str(path), events) + "\n" + render.render(events)
    live = not (TURNS / f"{name}.json").exists() and \
        time.time() - path.stat().st_mtime < STALE_AFTER

    banner = '<span class="live"><span class="dot"></span>running</span>' if live else ""
    body = (f"<header><h1>{html.escape(name)}</h1>{banner}</header>"
            f"<main><a class=back href='/'>← all turns</a>"
            f"<pre>{as_html(text)}</pre></main>")

    return page(name, body, refresh=5 if live else 0)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"

        if TOKEN:
            if not path.startswith(f"/{TOKEN}"):
                return self.send_error(404)
            path = path[len(TOKEN) + 1:] or "/"

        if path == "/":
            return self.send_page(index())

        if path.startswith("/turn/"):
            body = turn(path[len("/turn/"):])
            return self.send_page(body) if body else self.send_error(404)

        self.send_error(404)

    def send_page(self, body):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main():
    host = os.environ.get("VIEWER_HOST", "127.0.0.1")
    port = int(os.environ.get("VIEWER_PORT", "5070"))
    where = f"http://{host}:{port}" + (f"/{TOKEN}" if TOKEN else "")
    print(f"turns at {where}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
