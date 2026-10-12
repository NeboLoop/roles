---
name: store-numbers
description: The store's arithmetic, done in code — days of stock left, order ageing, a day's sales against its comparisons, product ranking — and the alert cooldown, so every figure in a report is computed, never estimated.
---

# Store numbers

Every number the Ecommerce Store Manager reports is computed by a script here from what the
store connection returned. A figure the store did not return is null and named in
`notAvailable`; it is never estimated. Money is integer cents.

| script | reads on standard input | answers |
|---|---|---|
| `stash.py` | any list | keeps it in a fresh per-run file, so the next step can join it with a second list (`file`) |
| `stock_cover.py` | recent orders (+ `--stock-file`) | sell-through, days of stock left, and the SKUs under the low-stock line or inside the restock lead time (`flagged`, `count`) |
| `order_issues.py` | recent orders | stuck, on-hold, failed, uncaptured, unfulfilled-paid, refunded and disputed orders with their age (`issues`, `count`) |
| `cooldown.py` | flagged items (`key`, `tier`) | which are new or worse than last alerted (`alerts`, `count`) and the log to keep (`log`) |
| `sales_day.py` | the last 32 days of orders | the day's charged, gross, net, refunds, discounts, orders and AOV beside the prior day, the same weekday last week and the 30-day average, plus the top movers |
| `product_rank.py` | two review windows of orders (+ `--products-file`, `--stock-file`) | performers, contribution margin, decliners and dead stock |

## The cooldown

An issue already alerted is not alerted again while it stays open, unless it crosses a worse
threshold (a higher tier). Stock tiers: 1 under the low-stock line, 2 out before a restock
can land, 3 at zero and still selling. An order's tier is how many multiples of its window it
has sat. The log of what was alerted is kept in memory under **store alert log: stock** and
**store alert log: orders**, as `key=tier` pairs separated by commas; an issue that clears
leaves the log, so if it returns it is new.
