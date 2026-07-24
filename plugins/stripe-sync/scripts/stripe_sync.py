"""Run your Stripe payment links from your offer docs, without the dashboard.

Your offer docs are the source of truth. Stripe follows them. Three commands:

  check   Verify every buy.stripe.com link in your docs against Stripe:
          active, charging what the doc says, tagged to the right offer.
          --fix reconciles metadata. Read-only otherwise.

  new     Create a price and a payment link at an amount, tagged with the
          offer (and customer, if given), and print the URL to drop in the
          doc. Dry-run first; a live create needs --yes.

  close   Deactivate every link tagged to an offer, for when it is done or
          declined. Dry-run first; a live close needs --yes.

An amount never changes on a live link, by design. A price change is a new
link (new) and the old one closed (close), so a copy you already sent keeps
pointing at the right number.

Config (environment variables, all optional):
  STRIPE_API_KEY   required for any Stripe call.
  OFFERS_DIR       folder scanned by check (default: offers). --dir overrides.
  STRIPE_CURRENCY  currency for new links (default: usd).
  STRIPE_PRODUCT   reuse one Stripe product id for new links, instead of
                   creating a product per offer.
  CLOSED_DIRS      subfolders whose links should be off (default: retired,closed).
  LOCKED_DIRS      subfolders that are approval-gated (default: accepted).

Usage:
  stripe_sync.py check [--fix] [--fix-gated] [--dir PATH]
  stripe_sync.py new --offer SLUG --amount DOLLARS [--customer NAME]
                     [--label TEXT] [--dry-run | --yes]
  stripe_sync.py close --offer SLUG [--dir PATH] [--dry-run | --yes]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.stripe.com/v1"
LINK_RE = re.compile(r"\[([^\]]*)\]\((https://buy\.stripe\.com/[A-Za-z0-9]+)\)")
AMOUNT_RE = re.compile(r"^\s*\$?([\d,]+(?:\.\d{1,2})?)\s*$")


def _dirs(name: str, default: str) -> set[str]:
    return {p.strip() for p in os.environ.get(name, default).split(",") if p.strip()}


CLOSED_DIRS = _dirs("CLOSED_DIRS", "retired,closed")
LOCKED_DIRS = _dirs("LOCKED_DIRS", "accepted")


def api(path: str, data: dict | None = None, method: str | None = None) -> dict:
    key = os.environ.get("STRIPE_API_KEY")
    if not key:
        sys.exit("STRIPE_API_KEY not set")
    req = urllib.request.Request(
        f"{API}{path}",
        data=urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None,
        headers={"Authorization": f"Bearer {key}"},
        method=method,
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def all_links() -> dict[str, dict]:
    links, after = {}, None
    while True:
        page = api("/payment_links?limit=100" + (f"&starting_after={after}" if after else ""))
        for l in page["data"]:
            links[l["url"]] = l
        if not page.get("has_more"):
            return links
        after = page["data"][-1]["id"]


def links_for_offer(slug: str) -> list[dict]:
    out, after = [], None
    while True:
        page = api("/payment_links?limit=100" + (f"&starting_after={after}" if after else ""))
        for l in page["data"]:
            if (l.get("metadata") or {}).get("offer", "") == slug:
                out.append(l)
        if not page.get("has_more"):
            return out
        after = page["data"][-1]["id"]


def doc_links(offers_dir: Path) -> list[dict]:
    found = []
    for md in sorted(offers_dir.rglob("*.md")):
        text = md.read_text()
        parts = set(md.parts)
        for m in LINK_RE.finditer(text):
            amt = AMOUNT_RE.match(m.group(1))
            found.append({
                "doc": str(md),
                "slug": md.stem,
                "url": m.group(2),
                "amount": round(float(amt.group(1).replace(",", "")) * 100) if amt else None,
                "closed": bool(CLOSED_DIRS & parts),
                "locked": bool(LOCKED_DIRS & parts),
            })
    return found


def cmd_check(args) -> int:
    offers_dir = Path(args.dir or os.environ.get("OFFERS_DIR", "offers"))
    if not offers_dir.is_dir():
        sys.exit(f"offers dir not found: {offers_dir} (set OFFERS_DIR or --dir)")
    stripe = all_links()
    drift = 0
    for d in doc_links(offers_dir):
        link = stripe.get(d["url"])
        tag = f'{d["doc"]} {d["url"]}'
        if link is None:
            print(f"MISSING  {tag}: no payment link with this URL in Stripe")
            drift += 1
            continue
        if d["closed"]:
            if link["active"]:
                print(f"ACTIVE   {tag}: closed offer's link is still active. run: close --offer {d['slug']}")
                drift += 1
            continue
        if not link["active"]:
            print(f"INACTIVE {tag}: doc links to a deactivated link")
            drift += 1
        if d["amount"] is not None:
            items = api(f'/payment_links/{link["id"]}/line_items')["data"]
            total = sum(i["amount_total"] for i in items)
            if total != d["amount"]:
                print(f'AMOUNT   {tag}: doc says {d["amount"]}, link charges {total}. run: new, then close the old one')
                drift += 1
        meta = link.get("metadata") or {}
        if d["slug"] not in meta.get("offer", ""):
            if d["locked"] and not args.fix_gated:
                print(f'LOCKED   {tag}: metadata drift under a locked folder; fixing needs --fix-gated')
                drift += 1
            elif args.fix or args.fix_gated:
                new_meta = {**meta, "offer": d["slug"]}
                api(f'/payment_links/{link["id"]}',
                    {**{f"metadata[{k}]": v for k, v in new_meta.items()},
                     **{f"payment_intent_data[metadata][{k}]": v for k, v in new_meta.items()}})
                print(f'FIXED    {tag}: metadata offer -> {d["slug"]}')
            else:
                print(f'METADATA {tag}: link metadata says offer={meta.get("offer") or "(none)"}')
                drift += 1
    if drift == 0:
        print("All offer payment links in sync.")
    return 1 if (drift and not args.fix) else 0


def cmd_new(args) -> int:
    cents = round(float(str(args.amount).replace(",", "").lstrip("$")) * 100)
    currency = os.environ.get("STRIPE_CURRENCY", "usd")
    label = args.label or f"Offer: {args.offer}"
    meta = {"offer": args.offer}
    if args.customer:
        meta["customer"] = args.customer
    plan = [
        f'price: ${cents / 100:,.2f} {currency} ({label})',
        f'payment link: metadata {meta}, description "{label}"',
    ]
    if args.dry_run or not args.yes:
        print("DRY RUN, would create:")
        for line in plan:
            print("  " + line)
        if not args.yes:
            print("\nNothing created. Re-run with --yes to create it live.")
        return 0

    price_data = {"unit_amount": cents, "currency": currency}
    if os.environ.get("STRIPE_PRODUCT"):
        price_data["product"] = os.environ["STRIPE_PRODUCT"]
    else:
        price_data["product_data[name]"] = label
    price = api("/prices", price_data)

    link_data = {
        "line_items[0][price]": price["id"],
        "line_items[0][quantity]": 1,
        "payment_intent_data[description]": label,
        **{f"metadata[{k}]": v for k, v in meta.items()},
        **{f"payment_intent_data[metadata][{k}]": v for k, v in meta.items()},
    }
    link = api("/payment_links", link_data)
    print(f'CREATED  {args.offer}: [${cents // 100:,}]({link["url"]})')
    print("Paste that link into the offer doc, then run: check")
    return 0


def cmd_close(args) -> int:
    links = links_for_offer(args.offer)
    active = [l for l in links if l["active"]]
    if not active:
        print(f"No active links tagged offer={args.offer}. Nothing to close.")
        return 0
    if args.dry_run or not args.yes:
        print(f"DRY RUN, would deactivate {len(active)} link(s) for offer={args.offer}:")
        for l in active:
            print(f'  {l["url"]}')
        if not args.yes:
            print("\nNothing changed. Re-run with --yes to deactivate them live.")
        return 0
    for l in active:
        api(f'/payment_links/{l["id"]}', {"active": "false"})
        print(f'CLOSED   {args.offer}: {l["url"]}')
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Run your Stripe links from your offer docs.")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="verify links against the docs")
    c.add_argument("--fix", action="store_true")
    c.add_argument("--fix-gated", dest="fix_gated", action="store_true")
    c.add_argument("--dir")
    c.set_defaults(func=cmd_check)

    n = sub.add_parser("new", help="create a tagged price + payment link")
    n.add_argument("--offer", required=True)
    n.add_argument("--amount", required=True, help="dollars, e.g. 5000 or 5000.00")
    n.add_argument("--customer")
    n.add_argument("--label")
    n.add_argument("--dry-run", dest="dry_run", action="store_true")
    n.add_argument("--yes", action="store_true", help="create it live")
    n.set_defaults(func=cmd_new)

    x = sub.add_parser("close", help="deactivate an offer's links")
    x.add_argument("--offer", required=True)
    x.add_argument("--dir")
    x.add_argument("--dry-run", dest="dry_run", action="store_true")
    x.add_argument("--yes", action="store_true", help="deactivate live")
    x.set_defaults(func=cmd_close)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
