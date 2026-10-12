#!/usr/bin/env python3
"""A day's sales, each figure beside its comparison basis.

  sales_day.py --day yesterday|today [--top 3] < orders.json   (orders of the last 32 days)

`yesterday` is the whole of yesterday. `today` runs from midnight to now, and every
comparison uses the same stretch of its own day, so a morning is never compared with a
whole day.

Comparisons: the day before, the same weekday a week before, and the average of the 30
days before. Gross is what was charged before discounts; net is what was charged less
refunds; discount load is discounts as a share of gross. Money is integer cents.
A figure the store did not return is null and named in `notAvailable`.

Prints {"summary", "day", "current", "priorDay", "sameWeekday", "avg30", "deltaPct",
        "moversUp", "moversDown", "notAvailable"}.
"""

import argparse
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _store import (as_number, emit, lines, now, order_discount, order_placed,  # noqa: E402
                    order_refunded, order_status, order_total, read_stdin_list)

p = argparse.ArgumentParser()
p.add_argument("--day", default="yesterday")
p.add_argument("--top")
a = p.parse_args()
top = max(1, as_number(a.top, 3, "--top", int))

t = now()
midnight = t.replace(hour=0, minute=0, second=0, microsecond=0)
if a.day == "today":
    start, length = midnight, t - midnight
else:
    start, length = midnight - timedelta(days=1), timedelta(days=1)

orders = []
missing = {"total": 0, "date": 0, "refund": 0, "discount": 0}
for o in read_stdin_list():
    if order_status(o) in ("cancelled", "canceled", "voided", "failed"):
        continue
    placed = order_placed(o)
    if placed is None:
        missing["date"] += 1
        continue
    orders.append((placed, o))


def window(offset_days):
    s = start - timedelta(days=offset_days)
    return [o for placed, o in orders if s <= placed < s + length]


def figures(batch, count_missing=False):
    total = refunds = discounts = 0
    have_refunds = have_discounts = True
    n = 0
    for o in batch:
        v = order_total(o)
        if v is None:
            if count_missing:
                missing["total"] += 1
            continue
        n += 1
        total += v
        r, d = order_refunded(o), order_discount(o)
        if r is None:
            have_refunds = False
            if count_missing:
                missing["refund"] += 1
        else:
            refunds += r
        if d is None:
            have_discounts = False
            if count_missing:
                missing["discount"] += 1
        else:
            discounts += d
    gross = total + discounts if have_discounts else None
    return {
        "orders": n,
        "chargedCents": total,
        "grossCents": gross,
        "refundsCents": refunds if have_refunds else None,
        "discountsCents": discounts if have_discounts else None,
        "netCents": total - refunds if have_refunds else None,
        "aovCents": round(total / n) if n else None,
        "discountLoadPct": round(100 * discounts / gross, 1) if have_discounts and gross else None,
    }


def average(days):
    rows = [figures(window(d)) for d in days]
    out = {}
    for k in ("orders", "chargedCents", "grossCents", "refundsCents", "discountsCents", "netCents"):
        vals = [r[k] for r in rows]
        out[k] = None if any(v is None for v in vals) else round(sum(vals) / len(vals))
    out["aovCents"] = round(out["chargedCents"] / out["orders"]) if out["orders"] else None
    return out


def pct(cur, base):
    if cur is None or base in (None, 0):
        return None
    return round(100 * (cur - base) / base, 1)


cur = figures(window(0), count_missing=True)
prior, week, avg30 = figures(window(1)), figures(window(7)), average(range(1, 31))
delta = {basis: {k: pct(cur[k], ref[k]) for k in ("chargedCents", "netCents", "orders", "aovCents")}
         for basis, ref in (("priorDay", prior), ("sameWeekday", week), ("avg30", avg30))}

by_sku_now, by_sku_avg, names = {}, {}, {}
for o in window(0):
    for line in lines(o):
        if line["revenueCents"] is not None and line["sku"]:
            by_sku_now[line["sku"]] = by_sku_now.get(line["sku"], 0) + line["revenueCents"]
            names[line["sku"]] = line["name"]
for d in range(1, 31):
    for o in window(d):
        for line in lines(o):
            if line["revenueCents"] is not None and line["sku"]:
                by_sku_avg[line["sku"]] = by_sku_avg.get(line["sku"], 0) + line["revenueCents"] / 30
                names.setdefault(line["sku"], line["name"])
moves = [{"sku": s, "name": names.get(s, ""), "revenueCents": by_sku_now.get(s, 0),
          "avg30Cents": round(by_sku_avg.get(s, 0)),
          "deltaCents": round(by_sku_now.get(s, 0) - by_sku_avg.get(s, 0))}
         for s in set(by_sku_now) | set(by_sku_avg)]
moves.sort(key=lambda m: m["deltaCents"])
up = [m for m in reversed(moves) if m["deltaCents"] > 0][:top]
down = [m for m in moves if m["deltaCents"] < 0][:top]

not_available = []
if missing["date"]:
    not_available.append(f"{missing['date']} orders carried no placed date")
if missing["total"]:
    not_available.append(f"{missing['total']} orders on the day carried no total")
if missing["refund"]:
    not_available.append("refunds are not available from this store, so net revenue is not available")
if missing["discount"]:
    not_available.append("discounts are not available from this store, so gross and discount load are not available")

emit({
    "summary": f"{a.day} ({start.date().isoformat()}): {cur['orders']} orders, "
               f"{cur['chargedCents']} cents charged",
    "day": start.date().isoformat(),
    "current": cur,
    "priorDay": prior,
    "sameWeekday": week,
    "avg30": avg30,
    "deltaPct": delta,
    "moversUp": up,
    "moversDown": down,
    "notAvailable": not_available,
})
