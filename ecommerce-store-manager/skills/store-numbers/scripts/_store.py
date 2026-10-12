"""Shared readers for store records: the store connection's answer, in whatever field
names the bound platform uses, turned into numbers the seat can stand behind.

A figure the record does not carry is None, never a guess. Money is integer cents.
"""

import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

UNREADABLE = []


def as_number(value, default, flag, kind=int):
    """Read a numeric argument as text, never through argparse."""
    text = str(value if value is not None else "").strip()
    if not text or "{{" in text:
        if text:
            UNREADABLE.append({"flag": flag, "received": text, "usedInstead": default})
        return default
    try:
        return kind(text.replace(",", "").replace("_", ""))
    except ValueError:
        UNREADABLE.append({"flag": flag, "received": text, "usedInstead": default})
        return default


def read_stdin_list():
    """The records on standard input: a bare list, or an object holding one list."""
    raw = sys.stdin.read().strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        data = lists[0] if len(lists) == 1 else data.get("records", [])
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def read_file_list(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def pick(rec, *names):
    for n in names:
        cur = rec
        for part in n.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur not in (None, ""):
            return cur
    return None


def cents(rec, cent_names, unit_names):
    """Integer cents from a cents field, or from a decimal amount field. None if neither."""
    v = pick(rec, *cent_names)
    if v is not None:
        try:
            return int(Decimal(str(v)))
        except (InvalidOperation, ValueError):
            return None
    v = pick(rec, *unit_names)
    if isinstance(v, dict):
        v = pick(v, "amount", "value")
    if v is None:
        return None
    try:
        return int((Decimal(str(v)) * 100).quantize(Decimal("1")))
    except (InvalidOperation, ValueError):
        return None


def moment(value):
    """A timestamp as an aware datetime in this machine's local zone, or None."""
    if value in (None, ""):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.fromtimestamp(float(text), tz=timezone.utc)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def now():
    return datetime.now().astimezone()


# ── an order ─────────────────────────────────────────────────────────────────

def order_id(o):
    return str(pick(o, "id", "orderId", "number", "name", "orderNumber") or "")


def order_placed(o):
    return moment(pick(o, "placedAt", "createdAt", "created_at", "processedAt", "date_created", "date"))


def order_total(o):
    return cents(o, ("totalCents", "totalPriceCents", "amountCents"),
                 ("total", "totalPrice", "total_price", "amount", "grandTotal"))


def order_refunded(o):
    v = cents(o, ("refundedCents", "totalRefundedCents"), ("totalRefunded", "total_refunded", "refunded"))
    if v is not None:
        return v
    refunds = pick(o, "refunds")
    if isinstance(refunds, list):
        total = 0
        for r in refunds:
            c = cents(r, ("amountCents",), ("amount", "total"))
            if c is None:
                return None
            total += c
        return total
    return None


def order_discount(o):
    return cents(o, ("discountCents", "totalDiscountCents"), ("totalDiscounts", "total_discounts", "discount", "discountTotal"))


def order_status(o):
    return str(pick(o, "status", "state") or "").lower()


def payment_status(o):
    return str(pick(o, "financialStatus", "paymentStatus", "financial_status", "payment.status") or "").lower()


def fulfillment_status(o):
    return str(pick(o, "fulfillmentStatus", "fulfillment_status", "fulfillment.status") or "").lower()


def customer(o):
    return str(pick(o, "customer.email", "email", "customerEmail", "customer.id", "customerId", "customer") or "")


def lines(o):
    ls = pick(o, "lines", "lineItems", "line_items", "items")
    out = []
    for line in ls if isinstance(ls, list) else []:
        if not isinstance(line, dict):
            continue
        qty = pick(line, "quantity", "qty")
        try:
            qty = int(Decimal(str(qty))) if qty is not None else None
        except (InvalidOperation, ValueError):
            qty = None
        line_total = cents(line, ("totalCents", "lineTotalCents"), ("total", "lineTotal"))
        if line_total is None:
            unit = cents(line, ("priceCents", "unitPriceCents"), ("price", "unitPrice"))
            line_total = unit * qty if unit is not None and qty is not None else None
        out.append({
            "sku": str(pick(line, "sku", "variantSku") or pick(line, "productId", "product_id", "variantId") or ""),
            "productId": str(pick(line, "productId", "product_id") or ""),
            "name": str(pick(line, "name", "title") or ""),
            "qty": qty,
            "revenueCents": line_total,
        })
    return out


def emit(out):
    if UNREADABLE:
        out["unreadableArguments"] = UNREADABLE
    print(json.dumps(out, ensure_ascii=False))
