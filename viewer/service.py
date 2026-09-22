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
       font:14px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace; }
header { position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line);
         padding:14px 20px; display:flex; gap:18px; align-items:baseline; flex-wrap:wrap; }
h1 { font-size:15px; margin:0; font-weight:600; }
.meta { color:var(--dim); font-size:12px; }
main { padding:18px 20px 60px; max-width:900px; }
a { color:var(--link); text-decoration:none; }
a:hover { text-decoration:underline; }
table { border-collapse:collapse; width:100%; }
td, th { padding:6px 12px 6px 0; text-align:left; vertical-align:top;
         border-bottom:1px solid var(--line); white-space:nowrap; }
th { color:var(--dim); font-weight:500; font-size:12px; }
td.wide { white-space:normal; color:var(--dim); }
.live { color:var(--live); }
.dot { display:inline-block; width:7px; height:7px; border-radius:50%;
       background:var(--live); margin-right:6px; animation:p 1.4s infinite; }
@keyframes p { 50% { opacity:.25 } }
pre { white-space:pre-wrap; word-wrap:break-word; margin:0; }
code { color:#c3e88d; }
b { color:#fff; font-weight:600; }
.h { display:block; color:#fff; font-weight:600; margin:18px 0 4px; }
.back { margin-bottom:14px; display:inline-block; }
"""


def page(title, body, refresh=0):
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{meta}<title>{html.escape(title)}</title><style>{STYLE}</style></head>
<body>{body}</body></html>"""


def index():
    rows = []

    for t in turns():
        if t["live"]:
            state = '<span class="live"><span class="dot"></span>running</span>'
            detail = f"{t['bytes'] // 1024} KB so far"
        elif t["abandoned"]:
            state = "<span class=meta>unfinished</span>"
            detail = ""
        else:
            state = f"{t.get('elapsed', '?')}s"
            rate = t.get("tokensPerSecond")
            detail = f"{t.get('turns', '?')} steps"
            if rate:
                detail += f" · {rate} tok/s"
            if t.get("cost"):
                detail += f" · ${t['cost']:.2f}"

        said = (t.get("text") or "").strip().split("\n")[0][:110]

        rows.append(
            f"<tr><td><a href='/turn/{t['name']}'>{when_reads(t['when'])}</a></td>"
            f"<td>{t['kind']}</td><td>{state}</td><td class=meta>{detail}</td>"
            f"<td class=wide>{html.escape(said)}</td></tr>")

    run = (STATE / "current-run").read_text().strip() if (STATE / "current-run").exists() else "?"
    model = (STATE / "run-model").read_text().strip() if (STATE / "run-model").exists() else "?"
    living = any(t["live"] for t in turns())

    body = (f"<header><h1>{html.escape(run)}</h1>"
            f"<span class=meta>{html.escape(model)} · {len(rows)} turns</span></header>"
            "<main><table><tr><th>when</th><th>kind</th><th>took</th><th></th>"
            "<th>what it said</th></tr>" + "".join(rows) + "</table></main>")

    return page(run, body, refresh=10 if living else 30)


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
