#!/usr/bin/env python3
"""Rank products over the review window against the equal window before it.

  product_rank.py --products-file <stash> --stock-file <stash> --window-days 30 \
                  [--decline-pct 50] [--top 10] < orders.json   (orders of the last 2 windows)

- performers: by revenue, with units and the change against the prior window.
- byMargin: by contribution (revenue less units times unit cost), only where cost is known.
- decliners: sold in the prior window and fell by --decline-pct or more in this one.
- deadStock: on hand above zero and no sale in the window, with the value tied up where
  cost is known.
Money is integer cents; a figure the store did not return is null.

Prints {"summary", "windowDays", "performers", "byMargin", "decliners", "deadStock",
        "notAvailable"}.
"""

import argparse
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _store import (as_number, cents, emit, lines, now, order_placed, order_status,  # noqa: E402
                    pick, read_file_list, read_stdin_list)

p = argparse.ArgumentParser()
p.add_argument("--products-file", required=True)
p.add_argument("--stock-file", required=True)
p.add_argument("--window-days")
p.add_argument("--decline-pct")
p.add_argument("--top")
a = p.parse_args()
window = max(1, as_number(a.window_days, 30, "--window-days", int))
decline = as_number(a.decline_pct, 50, "--decline-pct", float)
top = max(1, as_number(a.top, 10, "--top", int))

t = now()
cur_start, prior_start = t - timedelta(days=window), t - timedelta(days=2 * window)
cur, prior, names = {}, {}, {}
undated = 0
for o in read_stdin_list():
    if order_status(o) in ("cancelled", "canceled", "voided", "failed"):
        continue
    placed = order_placed(o)
    if placed is None:
        undated += 1
        continue
    bucket = cur if placed >= cur_start else prior if placed >= prior_start else None
    if bucket is None:
        continue
    for line in lines(o):
        if not line["sku"]:
            continue
        row = bucket.setdefault(line["sku"], {"units": 0, "revenueCents": 0, "unpriced": False})
        row["units"] += line["qty"] or 0
        if line["revenueCents"] is None:
            row["unpriced"] = True
        else:
            row["revenueCents"] += line["revenueCents"]
        names.setdefault(line["sku"], line["name"])

cost = {}
for prod in read_file_list(a.products_file):
    sku = str(pick(prod, "sku", "variantSku", "id") or "")
    names.setdefault(sku, str(pick(prod, "name", "title") or ""))
    c = cents(prod, ("unitCostCents", "costCents"), ("unitCost", "cost"))
    if sku and c is not None:
        cost[sku] = c


def change(sku):
    before = prior.get(sku, {}).get("revenueCents", 0)
    now_ = cur.get(sku, {}).get("revenueCents", 0)
    return round(100 * (now_ - before) / before, 1) if before else None


performers = [{"sku": s, "name": names.get(s, ""), "units": r["units"], "revenueCents": r["revenueCents"],
               "revenueIncomplete": r["unpriced"], "changePct": change(s)} for s, r in cur.items()]
performers.sort(key=lambda r: (-r["revenueCents"], -r["units"]))

by_margin = []
for s, r in cur.items():
    if s in cost and not r["unpriced"]:
        by_margin.append({"sku": s, "name": names.get(s, ""), "units": r["units"],
                          "revenueCents": r["revenueCents"],
                          "contributionCents": r["revenueCents"] - r["units"] * cost[s],
                          "marginPct": round(100 * (r["revenueCents"] - r["units"] * cost[s]) / r["revenueCents"], 1)
                          if r["revenueCents"] else None})
by_margin.sort(key=lambda r: -r["contributionCents"])

decliners = []
for s, r in prior.items():
    if r["revenueCents"] <= 0:
        continue
    pc = change(s)
    if pc is not None and pc <= -decline:
        decliners.append({"sku": s, "name": names.get(s, ""), "priorRevenueCents": r["revenueCents"],
                          "revenueCents": cur.get(s, {}).get("revenueCents", 0),
                          "priorUnits": r["units"], "units": cur.get(s, {}).get("units", 0), "changePct": pc})
decliners.sort(key=lambda r: r["revenueCents"] - r["priorRevenueCents"])

dead, no_count = [], 0
for st in read_file_list(a.stock_file):
    sku = str(pick(st, "sku", "variantSku", "productId", "id") or "")
    try:
        on_hand = float(pick(st, "onHand", "available", "quantity", "inventoryQuantity", "qty"))
    except (TypeError, ValueError):
        no_count += 1
        continue
    if on_hand > 0 and cur.get(sku, {}).get("units", 0) == 0:
        dead.append({"sku": sku, "name": names.get(sku, ""), "onHand": on_hand,
                     "valueCents": round(on_hand * cost[sku]) if sku in cost else None})
dead.sort(key=lambda r: -(r["valueCents"] or 0))

not_available = []
if undated:
    not_available.append(f"{undated} orders carried no placed date")
if not cost:
    not_available.append("unit cost is not available from this store, so margin and dead-stock value are not available")
if no_count:
    not_available.append(f"{no_count} stock records carried no on-hand count")
emit({
    "summary": f"{len(cur)} products sold in the last {window} days; {len(decliners)} decliners, "
               f"{len(dead)} dead-stock lines",
    "windowDays": window,
    "performers": performers[:top],
    "byMargin": by_margin[:top],
    "decliners": decliners[:top],
    "deadStock": dead[:top],
    "deadStockValueCents": sum(d["valueCents"] or 0 for d in dead) if cost else None,
    "notAvailable": not_available,
})
