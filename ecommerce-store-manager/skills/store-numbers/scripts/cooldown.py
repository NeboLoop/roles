#!/usr/bin/env python3
"""The alert cooldown. An issue already alerted is not alerted again while it stays open,
unless it has crossed a worse threshold (a higher tier). An issue that is no longer
flagged leaves the log, so if it comes back it is new again.

  cooldown.py --alerted "<key>=<tier>,<key>=<tier>" < flagged.json

--alerted is the log kept from the last alert (empty on a first run). Each flagged item on
standard input carries `key` and `tier`.

Prints {"summary", "count", "alerts", "suppressed", "log"}: `log` is the new log to keep.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _store import emit, read_stdin_list  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--alerted", default="")
a = p.parse_args()

prior = {}
text = "" if "{{" in (a.alerted or "") else (a.alerted or "")
for part in text.split(","):
    key, sep, tier = part.strip().rpartition("=")
    if sep and key:
        try:
            prior[key] = int(tier)
        except ValueError:
            continue

alerts, suppressed, log = [], 0, {}
for item in read_stdin_list():
    key, tier = str(item.get("key") or ""), int(item.get("tier") or 1)
    if not key:
        continue
    if key in prior and tier <= prior[key]:
        suppressed += 1
        log[key] = prior[key]
        continue
    alerts.append(item)
    log[key] = tier

emit({
    "summary": f"{len(alerts)} new or worse, {suppressed} already alerted and unchanged",
    "count": len(alerts),
    "alerts": alerts,
    "suppressed": suppressed,
    "log": ",".join(f"{k}={v}" for k, v in log.items()),
})
