#!/usr/bin/env python3
"""The review window in days, read once, and the span of orders to fetch for it: the window
and the equal window before it.

  window.py --days 30

Prints {"summary", "days", "fetchDays"}.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _store import as_number, emit  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--days")
days = max(1, as_number(p.parse_args().days, 30, "--days", int))
emit({"summary": f"{days}-day review window", "days": days, "fetchDays": 2 * days})
