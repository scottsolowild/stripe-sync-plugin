"""Check offer payment links against Stripe; reconcile metadata drift.

Your offer docs are the source of truth. Stripe follows them. This scans a
folder of markdown offer docs for buy.stripe.com links, reads each one from
the Stripe API, and verifies three things:

  1. the link is active,
  2. the amount Stripe charges matches the price written in the doc,
  3. the link's metadata carries the offer doc's slug (its filename).

--fix reconciles metadata in place. Amounts and active status are never
changed here, by design: an amount change means a NEW link in the doc and
the old one deactivated, so a stale copy (a sent PDF, a cached page) can't
quietly collect the old price.

The price check works when the doc links the price as the anchor text, e.g.
`[$5,000](https://buy.stripe.com/xxxx)`. A link whose text is not a dollar
amount is still checked for active status and metadata; only its amount
check is skipped.

Config (environment variables, all optional):
  OFFERS_DIR    folder scanned for *.md (default: offers). --dir overrides.
  CLOSED_DIRS   comma-separated subfolder names whose links should be
                deactivated, e.g. an offer that is done or declined
                (default: retired,closed). An active link under one of
                these is the drift.
  LOCKED_DIRS   comma-separated subfolder names that are approval-gated:
                drift is reported but never auto-fixed without --fix-gated
                (default: accepted).

Usage:
  STRIPE_API_KEY=sk_live_... python3 stripe_sync.py [--fix] [--fix-gated] [--dir PATH]

Exit code is nonzero when drift is found and --fix was not passed, so it
works as a check in a hook or CI.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.stripe.com/v1"
# Any markdown link to a Stripe payment link. The anchor text is captured so
# a price like [$5,000](...) can be compared against what Stripe charges.
LINK_RE = re.compile(r"\[([^\]]*)\]\((https://buy\.stripe\.com/[A-Za-z0-9]+)\)")
AMOUNT_RE = re.compile(r"^\s*\$?([\d,]+)\s*$")


def _dirs(name: str, default: str) -> set[str]:
    return {p.strip() for p in os.environ.get(name, default).split(",") if p.strip()}


CLOSED_DIRS = _dirs("CLOSED_DIRS", "retired,closed")
LOCKED_DIRS = _dirs("LOCKED_DIRS", "accepted")


def api(path: str, data: dict | None = None) -> dict:
    key = os.environ.get("STRIPE_API_KEY")
    if not key:
        sys.exit("STRIPE_API_KEY not set")
    req = urllib.request.Request(
        f"{API}{path}",
        data=urllib.parse.urlencode(data, doseq=True).encode() if data else None,
        headers={"Authorization": f"Bearer {key}"},
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
                "amount": int(amt.group(1).replace(",", "")) * 100 if amt else None,
                "closed": bool(CLOSED_DIRS & parts),
                "locked": bool(LOCKED_DIRS & parts),
            })
    return found


def main() -> int:
    fix = "--fix" in sys.argv
    fix_gated = "--fix-gated" in sys.argv
    offers_dir = Path("--dir" in sys.argv and sys.argv[sys.argv.index("--dir") + 1]
                      or os.environ.get("OFFERS_DIR", "offers"))
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
                print(f"ACTIVE   {tag}: closed offer's link is still active — deactivate it")
                drift += 1
            continue
        if not link["active"]:
            print(f"INACTIVE {tag}: doc links to a deactivated link")
            drift += 1
        if d["amount"] is not None:
            items = api(f'/payment_links/{link["id"]}/line_items')["data"]
            total = sum(i["amount_total"] for i in items)
            if total != d["amount"]:
                print(f'AMOUNT   {tag}: doc says {d["amount"]}, link charges {total} — needs a new link, not a fix')
                drift += 1
        meta = link.get("metadata") or {}
        if d["slug"] not in meta.get("offer", ""):
            if d["locked"] and not fix_gated:
                print(f'LOCKED   {tag}: metadata drift under a locked folder; fixing needs approval (--fix-gated)')
                drift += 1
            elif fix or fix_gated:
                new_meta = {**meta, "offer": d["slug"]}
                api(f'/payment_links/{link["id"]}',
                    {**{f"metadata[{k}]": v for k, v in new_meta.items()},
                     **{f"payment_intent_data[metadata][{k}]": v for k, v in new_meta.items()}})
                print(f'FIXED    {tag}: metadata offer → {d["slug"]}')
            else:
                print(f'METADATA {tag}: link metadata says offer={meta.get("offer") or "(none)"}')
                drift += 1
    if drift == 0:
        print("All offer payment links in sync.")
    return 1 if (drift and not fix) else 0


if __name__ == "__main__":
    sys.exit(main())
