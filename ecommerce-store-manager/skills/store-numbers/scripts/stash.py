#!/usr/bin/env python3
"""Keep a list read on standard input in a fresh per-run file, so a later step can join it
with a second list it reads on its own standard input.

  stash.py < records.json

Prints {"summary", "file", "count"}.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _store import emit, read_stdin_list  # noqa: E402

records = read_stdin_list()
fd, path = tempfile.mkstemp(prefix="store-", suffix=".json")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    json.dump(records, f)
emit({"summary": f"{len(records)} records kept for the next step", "file": path, "count": len(records)})
