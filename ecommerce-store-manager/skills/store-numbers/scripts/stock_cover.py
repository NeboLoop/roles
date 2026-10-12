#!/usr/bin/env python3
"""Days of stock left per SKU, and which SKUs cross a line.

Sell-through is units sold over the trailing window divided by the days in it. Days left
is on hand divided by sell-through. A SKU is flagged when it will reach zero before a
restock can land (the lead time), or when its days left fall under the low-stock line.

  stock_cover.py --stock-file <stash file> --low-days 7 --lead-days 10 --window-days 30 \
                 [--top 25] < orders.json

Tier says how bad it is, so a repeat alert can be told from a worse one:
  1 under the low-stock line, 2 out before a restock lands, 3 at zero and still selling.

Prints {"summary", "count", "flagged", "notAvailable"}.
"""

import argparse
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _store import (as_number, emit, lines, now, order_placed, order_status,  # noqa: E402
                    pick, read_file_list, read_stdin_list)

p = argparse.ArgumentParser()
p.add_argument("--stock-file", required=True)
p.add_argument("--low-days")
p.add_argument("--lead-days")
p.add_argument("--window-days")
p.add_argument("--top")
a = p.parse_args()

low_days = as_number(a.low_days, 7, "--low-days", float)
lead_days = as_number(a.lead_days, 10, "--lead-days", float)
window = max(1, as_number(a.window_days, 30, "--window-days", int))
top = max(1, as_number(a.top, 25, "--top", int))

orders = read_stdin_list()
stock = read_file_list(a.stock_file)
since = now() - timedelta(days=window)

sold, undated, unsized = {}, 0, 0
for o in orders:
    if order_status(o) in ("cancelled", "canceled", "voided", "failed"):
        continue
    placed = order_placed(o)
    if placed is None:
        undated += 1
        continue
    if placed < since:
        continue
    for line in lines(o):
        if line["qty"] is None or not line["sku"]:
            unsized += 1
            continue
        sold[line["sku"]] = sold.get(line["sku"], 0) + line["qty"]

flagged, no_count = [], 0
for s in stock:
    sku = str(pick(s, "sku", "variantSku", "productId", "id") or "")
    on_hand = pick(s, "onHand", "available", "quantity", "inventoryQuantity", "qty")
    try:
        on_hand = float(on_hand)
    except (TypeError, ValueError):
        no_count += 1
        continue
    rate = sold.get(sku, 0) / window
    if rate <= 0:
        continue
    days_left = max(on_hand, 0) / rate
    tier = 0
    if on_hand <= 0:
        tier = 3
    elif days_left < lead_days:
        tier = 2
    elif days_left < low_days:
        tier = 1
    if not tier:
        continue
    flagged.append({
        "key": sku,
        "tier": tier,
        "sku": sku,
        "name": str(pick(s, "name", "title", "productName") or ""),
        "onHand": int(on_hand) if on_hand == int(on_hand) else on_hand,
        "unitsPerDay": round(rate, 2),
        "daysLeft": round(days_left, 1),
        "reorderNow": tier >= 2,
        "urgency": round(rate / max(days_left, 0.1), 3),
    })

flagged.sort(key=lambda f: (-f["tier"], -f["urgency"]))
flagged = flagged[:top]
not_available = []
if undated:
    not_available.append(f"{undated} orders carried no placed date and were left out of sell-through")
if unsized:
    not_available.append(f"{unsized} order lines carried no SKU or quantity and were left out")
if no_count:
    not_available.append(f"{no_count} stock records carried no on-hand count")
emit({
    "summary": f"{len(flagged)} SKUs under the line ({sum(1 for f in flagged if f['reorderNow'])} reorder-now) "
               f"from {len(stock)} stock records and {window} days of sales",
    "count": len(flagged),
    "flagged": flagged,
    "notAvailable": not_available,
})
