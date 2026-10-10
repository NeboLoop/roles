#!/usr/bin/env python3
"""Stuck, failed and unfulfilled paid orders, with their age computed rather than read.

  order_issues.py --stuck-hours 48 --hold-hours 72 --recent-hours 24 [--top 40] < orders.json

- stuck: processing or pending past --stuck-hours; on hold past --hold-hours.
- unfulfilled-paid: paid, with no fulfillment and no tracking, past --stuck-hours.
- failed-payment: payment failed, or authorized and still not captured.
- refund / chargeback: refunded or disputed inside --recent-hours.
- repeat-failures: one customer with two or more failed payments inside --recent-hours.

Tier rises with each further multiple of the window an order sits, so a stuck order is
alerted again only when it is worse, not merely still there.

Prints {"summary", "count", "issues", "notAvailable"}.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _store import (as_number, customer, emit, fulfillment_status, now, order_id,  # noqa: E402
                    order_placed, order_status, order_total, payment_status, pick,
                    read_stdin_list)

p = argparse.ArgumentParser()
p.add_argument("--stuck-hours")
p.add_argument("--hold-hours")
p.add_argument("--recent-hours")
p.add_argument("--top")
a = p.parse_args()

stuck_h = max(1.0, as_number(a.stuck_hours, 48, "--stuck-hours", float))
hold_h = max(1.0, as_number(a.hold_hours, 72, "--hold-hours", float))
recent_h = max(1.0, as_number(a.recent_hours, 24, "--recent-hours", float))
top = max(1, as_number(a.top, 40, "--top", int))

orders = read_stdin_list()
t = now()
issues, failed_by_customer = [], {}
no_state, no_date, no_fulfillment = 0, 0, 0

STUCK = ("processing", "pending", "unfulfilled", "awaiting")
HOLD = ("on-hold", "on_hold", "onhold", "held")
PAID = ("paid", "captured", "succeeded", "completed")
FAILED = ("failed", "declined", "voided")
UNCAPTURED = ("authorized", "pending", "pending_capture", "pending-capture")


def add(o, kind, age_h, window_h, why):
    tier = max(1, int(age_h // window_h)) if window_h else 1
    issues.append({
        "key": f"{order_id(o)}:{kind}",
        "tier": tier,
        "orderId": order_id(o),
        "type": kind,
        "state": order_status(o) or payment_status(o),
        "ageHours": round(age_h, 1),
        "customer": customer(o),
        "amountCents": order_total(o),
        "why": why,
    })


for o in orders:
    status, pay, ful = order_status(o), payment_status(o), fulfillment_status(o)
    if not status and not pay:
        no_state += 1
        continue
    placed = order_placed(o)
    if placed is None:
        no_date += 1
        continue
    age = (t - placed).total_seconds() / 3600
    updated = order_placed({"placedAt": pick(o, "updatedAt", "updated_at")}) or placed
    since_update = (t - updated).total_seconds() / 3600

    if status in HOLD and age > hold_h:
        add(o, "on-hold", age, hold_h, f"on hold {age:.0f}h, past {hold_h:.0f}h")
    elif status in STUCK and age > stuck_h:
        add(o, "stuck", age, stuck_h, f"{status} {age:.0f}h, past {stuck_h:.0f}h")

    if pay in PAID and status not in ("cancelled", "canceled", "refunded", "completed", "shipped", "delivered", "closed"):
        tracking = pick(o, "trackingNumber", "tracking", "trackingNumbers", "fulfillment.tracking")
        if not ful and tracking is None:
            no_fulfillment += 1
        elif ful in ("", "unfulfilled", "none", "pending") and not tracking and age > stuck_h:
            add(o, "unfulfilled-paid", age, stuck_h, f"paid {age:.0f}h ago, nothing shipped")

    if pay in FAILED or status in FAILED:
        if since_update <= recent_h:
            add(o, "failed-payment", 0, 0, "payment failed")
        c = customer(o)
        if c and since_update <= recent_h:
            failed_by_customer.setdefault(c, []).append(order_id(o))
    elif pay in UNCAPTURED and age > stuck_h:
        add(o, "uncaptured-payment", age, stuck_h, f"authorized {age:.0f}h, not captured")

    if since_update <= recent_h:
        if pay in ("refunded", "partially_refunded", "partially-refunded") or status == "refunded":
            add(o, "refund", 0, 0, "refunded recently")
        if pick(o, "disputed", "chargeback", "dispute") or pay in ("disputed", "chargeback"):
            add(o, "chargeback", 0, 0, "disputed recently")

for c, ids in failed_by_customer.items():
    if len(ids) >= 2:
        issues.append({"key": f"{c}:repeat-failures", "tier": len(ids) - 1, "orderId": ",".join(ids),
                       "type": "repeat-failures", "state": "failed", "ageHours": None, "customer": c,
                       "amountCents": None, "why": f"{len(ids)} failed payments from one customer"})

issues.sort(key=lambda i: (-(i["ageHours"] or 0), -(i["amountCents"] or 0)))
issues = issues[:top]
not_available = []
if no_state:
    not_available.append(f"{no_state} orders carried no order or payment state")
if no_date:
    not_available.append(f"{no_date} orders carried no placed date")
if no_fulfillment:
    not_available.append(f"{no_fulfillment} paid orders carried no fulfillment state or tracking, so shipping could not be confirmed")
emit({
    "summary": f"{len(issues)} order issues in {len(orders)} orders",
    "count": len(issues),
    "issues": issues,
    "notAvailable": not_available,
})
