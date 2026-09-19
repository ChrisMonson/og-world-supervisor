#!/usr/bin/env python3
"""Rejects migrations that remove or narrow anything.

Code can be rolled back. Data cannot. A migration that drops a column and is then
reverted has already destroyed what was in it, so the gate only lets migrations
add. Retiring something means leaving it in place and no longer reading it.
"""

import re
import sys
from pathlib import Path

# Checked against SQL with strings and comments stripped out.
FORBIDDEN = [
    (r"\bDROP\s+(TABLE|INDEX|VIEW|TRIGGER|COLUMN)\b", "drops an object"),
    (r"\bALTER\s+TABLE\s+\S+\s+DROP\b",               "drops a column"),
    (r"\bALTER\s+TABLE\s+\S+\s+RENAME\b",             "renames a table or column"),
    (r"\bDELETE\s+FROM\b",                            "deletes rows"),
    (r"\bTRUNCATE\b",                                 "truncates a table"),
    (r"\bUPDATE\s+\S+\s+SET\b",                       "rewrites existing rows"),
    (r"\bPRAGMA\s+writable_schema\b",                 "edits the schema directly"),
    (r"\bREINDEX\b",                                  "reindexes"),
]

ALLOWED_ALTER = re.compile(r"\bALTER\s+TABLE\s+\S+\s+ADD\s+(COLUMN\b)?", re.IGNORECASE)


def strip_noise(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"'(?:[^']|'')*'", " '' ", sql)
    sql = re.sub(r'"(?:[^"]|"")*"', ' "" ', sql)
    return sql


def check(path: Path) -> list[str]:
    sql = strip_noise(path.read_text())
    problems = []

    for pattern, why in FORBIDDEN:
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            fragment = " ".join(match.group(0).split())
            problems.append(f"{path.name}: {why} ({fragment})")

    for match in re.finditer(r"\bALTER\s+TABLE\b.*?(?=;|$)", sql, re.IGNORECASE | re.DOTALL):
        statement = " ".join(match.group(0).split())
        if not ALLOWED_ALTER.search(statement):
            problems.append(f"{path.name}: ALTER TABLE that is not ADD COLUMN ({statement[:70]})")

    return problems


def main() -> int:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "migrations")

    if not directory.is_dir():
        print(f"no migrations directory at {directory}; nothing to check")
        return 0

    files = sorted(directory.glob("*.sql"))
    problems = [problem for path in files for problem in check(path)]

    for problem in problems:
        print(f"REJECTED  {problem}")

    if problems:
        print(f"\n{len(problems)} problem(s) across {len(files)} migration file(s).")
        print("Migrations may add. They may not remove or narrow.")
        return 1

    print(f"{len(files)} migration file(s) are additive only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
