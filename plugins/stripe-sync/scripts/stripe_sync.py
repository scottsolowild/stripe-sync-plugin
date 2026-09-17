"""Run your Stripe payment links from your offer docs, without the dashboard.

Your offer docs are the source of truth. Stripe follows them. Four commands:

  check   Verify every buy.stripe.com link in your docs against Stripe:
          active, charging what the doc says, tagged to the right offer.
          --fix reconciles metadata. Read-only otherwise.

  new     Create a price and a payment link at an amount, tagged with the
          offer (and customer, if given), and print the URL to drop in the
          doc. Dry-run first; a live create needs --yes.

  close   Deactivate every link tagged to an offer, for when it is done or
          declined. Dry-run first; a live close needs --yes.

  credit  Show what a client has already paid toward a container: every
          succeeded design-session payment tagged to them, whether it is
          still inside the window, and whether another link already spent
          it. Read-only, except --tag. The open page sells to whoever
          clicks, so its payment lands with no client slug: --unfiled lists
          those, and `credit <slug> --tag <payment id>` files one onto a
          person so the container can credit it.

The credit is arithmetic, never a coupon (business/the-close.md). A rung that
is a piece of the container credits in full, so the container link is minted at
the net: `new --offer three-months --amount 6000 --credit-client <slug>` finds
the paid design sessions, subtracts them, and tags the new link with
credit_from=<payment intent ids>. That tag is the ledger. It is what stops the
same $250 being credited twice, and it is why no promotion code is involved:
the buyer sees one number rather than a discount.

An amount never changes on a live link, by design. A price change is a new
link (new) and the old one closed (close), so a copy you already sent keeps
pointing at the right number.

Config (environment variables, all optional):
  STRIPE_API_KEY   required for any Stripe call.
  OFFERS_DIR       folder scanned by check (default: offers). --dir overrides.
  STRIPE_CURRENCY  currency for new links (default: usd).
  STRIPE_PRODUCT   reuse one Stripe product id for new links, instead of
                   creating a product per offer.
  STRIPE_CREDIT_OFFER        offer slug that credits toward a container
                             (default: design).
  STRIPE_CREDIT_WINDOW_DAYS  how long a payment stays creditable
                             (default: 30; 0 means no window).
  CLOSED_DIRS      subfolders whose links should be off (default: retired,closed).
  LOCKED_DIRS      subfolders that are approval-gated (default: accepted).

Usage:
  stripe_sync.py check [--fix] [--fix-gated] [--dir PATH]
  stripe_sync.py new --offer SLUG --amount DOLLARS [--customer NAME]
                     [--meta KEY=VAL ...] [--label TEXT] [--redirect URL]
                     [--credit-client SLUG] [--credit-offer SLUG]
                     [--credit-window DAYS] [--credit-force]
                     [--dry-run | --yes]
  stripe_sync.py close --offer SLUG [--dir PATH] [--dry-run | --yes]
  stripe_sync.py credit [CLIENT] [--unfiled] [--tag PAYMENT_ID]
                        [--credit-offer SLUG] [--credit-window DAYS]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.stripe.com/v1"
LINK_RE = re.compile(r"\[([^\]]*)\]\((https://buy\.stripe\.com/[A-Za-z0-9]+)\)")
AMOUNT_RE = re.compile(r"^\s*\$?([\d,]+(?:\.\d{1,2})?)\s*$")
# A slug goes straight into a Stripe search query, so it is validated rather
# than escaped: anything outside this shape is refused before the call.
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# Stripe swaps this for the checkout session id on the way out. A booking page
# that opens only for a paid arrival reads it, so a redirect without it lands
# a man who has just paid back on the page that asks him to pay.
SESSION_VAR = "{CHECKOUT_SESSION_ID}"


def _dirs(name: str, default: str) -> set[str]:
    return {p.strip() for p in os.environ.get(name, default).split(",") if p.strip()}


CLOSED_DIRS = _dirs("CLOSED_DIRS", "retired,closed")
LOCKED_DIRS = _dirs("LOCKED_DIRS", "accepted")


def api(path: str, data: dict | None = None, method: str | None = None) -> dict:
    key = os.environ.get("STRIPE_API_KEY") or os.environ.get("CLAUDE_PLUGIN_OPTION_STRIPE_API_KEY")
    if not key:
        sys.exit("No Stripe key found. Set STRIPE_API_KEY, or enter your key when Claude Code prompts at install.")
    req = urllib.request.Request(
        f"{API}{path}",
        data=urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None,
        headers={"Authorization": f"Bearer {key}"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            err = json.loads(raw).get("error", {})
        except ValueError:
            err = {}
        msg = err.get("message") or raw[:400]
        if err.get("code") == "more_permissions_required":
            sys.exit(
                "This Stripe key is missing a permission this command needs.\n"
                "Edit the restricted key at https://dashboard.stripe.com/apikeys,\n"
                "turn on the permission Stripe names below, then re-run.\n\n"
                f"  {msg}"
            )
        sys.exit(f"Stripe {method or 'GET'} {path} failed ({e.code}): {msg}")


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


def credit_offer() -> str:
    return os.environ.get("STRIPE_CREDIT_OFFER", "design")


def credit_window_days() -> int:
    return int(os.environ.get("STRIPE_CREDIT_WINDOW_DAYS", "30"))


def search(resource: str, query: str) -> list[dict]:
    out, page = [], None
    while True:
        qs = {"query": query, "limit": 100}
        if page:
            qs["page"] = page
        res = api(f"/{resource}/search?{urllib.parse.urlencode(qs)}")
        out.extend(res["data"])
        if not res.get("has_more"):
            return out
        page = res["next_page"]


def paid_for(client: str, offer: str) -> list[dict]:
    """Every succeeded payment tagged to this client under this offer."""
    for name, value in (("client", client), ("offer", offer)):
        if not SLUG_RE.match(value):
            sys.exit(f"--credit-{name} must be a plain slug, got: {value}")
    q = f'status:"succeeded" AND metadata["offer"]:"{offer}" AND metadata["client"]:"{client}"'
    return sorted(search("payment_intents", q), key=lambda pi: pi["created"], reverse=True)


def spent_credits() -> dict[str, str]:
    """Payment intent id -> the link url that already credited it."""
    spent = {}
    for url, link in all_links().items():
        for pid in ((link.get("metadata") or {}).get("credit_from", "")).split():
            spent.setdefault(pid, url)
    return spent


def credit_ledger(client: str, offer: str, window_days: int) -> list[dict]:
    """Each payment with why it does or does not count, newest first."""
    spent = spent_credits()
    now = int(datetime.now(timezone.utc).timestamp())
    rows = []
    for pi in paid_for(client, offer):
        age_days = (now - pi["created"]) // 86400
        expired = bool(window_days) and age_days >= window_days
        rows.append({
            "id": pi["id"],
            "amount": pi["amount_received"] or pi["amount"],
            "created": pi["created"],
            "age_days": age_days,
            "expired": expired,
            "spent_on": spent.get(pi["id"]),
        })
    return rows


def unfiled(offer: str) -> list[dict]:
    """Paid sessions with no client tag: the open page sells to whoever clicks."""
    if not SLUG_RE.match(offer):
        sys.exit(f"--credit-offer must be a plain slug, got: {offer}")
    # Stripe search has no "field is absent" operator, so the offer narrows it
    # and the missing tag is decided here.
    q = f'status:"succeeded" AND metadata["offer"]:"{offer}"'
    rows = [pi for pi in search("payment_intents", q) if not (pi.get("metadata") or {}).get("client")]
    return sorted(rows, key=lambda pi: pi["created"], reverse=True)


def tag_client(payment_id: str, client: str) -> dict:
    if not SLUG_RE.match(client):
        sys.exit(f"client must be a plain slug, got: {client}")
    return api(f"/payment_intents/{payment_id}", {"metadata[client]": client})


def credit_lines(gross: int, taken: list[dict], net: int) -> list[str]:
    """The three lines for the page, so the buyer reads the credit coming off.

    A Payment Link charges one number and cannot carry a pre-applied coupon
    (the API takes allow_promotion_codes, a code the buyer types, and nothing
    else), so Stripe's own page can only ever show the net. The arithmetic
    belongs on the offer page anyway: that is where he decides, it is in our
    words rather than Stripe's "Discount" label, and it is the only surface
    that can say what the credit was for.
    """
    lines = [f"**{money(gross)}** in full to begin."]
    for r in taken:
        lines.append(
            f'Less the **{money(r["amount"])}** you already paid, on {day(r["created"])}.'
        )
    lines.append(f"**{money(net)}** to pay today:")
    return lines


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def day(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


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
    for kv in args.meta or []:
        k, _, v = kv.partition("=")
        if k.strip() and v.strip():
            meta[k.strip()] = v.strip()
        else:
            sys.exit(f"--meta expects KEY=VAL, got: {kv}")
    plan, credited = [], None
    if args.credit_client:
        offer = args.credit_offer or credit_offer()
        window = credit_window_days() if args.credit_window is None else args.credit_window
        rows = credit_ledger(args.credit_client, offer, window)
        take = [r for r in rows if not r["expired"] and (args.credit_force or not r["spent_on"])]
        if not take:
            held = [r for r in rows if r["expired"] or r["spent_on"]]
            sys.exit(
                f"No creditable {offer} payment for client={args.credit_client}.\n"
                + (f"{len(held)} payment(s) held back. Run: credit {args.credit_client}\n" if held else "")
                + "Mint it without --credit-client, or fix the client tag on the payment."
            )
        credit = sum(r["amount"] for r in take)
        if credit >= cents:
            sys.exit(
                f"Credit {money(credit)} is not smaller than the container at {money(cents)}. "
                "Nothing to charge, so no link was created."
            )
        gross, cents = cents, cents - credit
        credited = {"gross": gross, "taken": take}
        meta.setdefault("client", args.credit_client)
        meta["credit_from"] = " ".join(r["id"] for r in take)
        meta["credit_amount"] = f"{credit / 100:.2f}"
        meta["gross"] = f"{gross / 100:.2f}"
        for r in take:
            plan.append(f'credit: {money(r["amount"])} from {r["id"]} paid {day(r["created"])}')
        plan.append(f'net: {money(gross)} gross - {money(credit)} credit = {money(cents)}')
    plan += [
        f'price: ${cents / 100:,.2f} {currency} ({label})',
        f'payment link: metadata {meta}, description "{label}"',
    ]
    if args.redirect:
        plan.append(f'after payment: redirect to {args.redirect}')
        if SESSION_VAR not in args.redirect:
            # --yes skips the plan, so this one goes to stderr on both paths.
            print(
                f"NOTE: the redirect URL carries no {SESSION_VAR}. A booking page "
                "that opens only for a paid arrival reads it, so this sends him "
                "back to the offer page after he pays.",
                file=sys.stderr,
            )
    if credited:
        plan.append("page copy: " + " ".join(credit_lines(credited["gross"], credited["taken"], cents)))
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
    if args.redirect:
        link_data["after_completion[type]"] = "redirect"
        link_data["after_completion[redirect][url]"] = args.redirect
    link = api("/payment_links", link_data)
    print(f'CREATED  {args.offer}: [${cents // 100:,}]({link["url"]})')
    if credited:
        print("\nFor the page, above the button, so he reads the credit come off:\n")
        for line in credit_lines(credited["gross"], credited["taken"], cents):
            print(f"  {line}")
        print(f'  [Pay and begin]({link["url"]})')
    print("\nPaste that link into the offer doc, then run: check")
    return 0


def cmd_credit(args) -> int:
    offer = args.credit_offer or credit_offer()
    window = credit_window_days() if args.credit_window is None else args.credit_window
    if args.unfiled:
        rows = unfiled(offer)
        if not rows:
            print(f"Every succeeded {offer} payment carries a client tag.")
            return 0
        print(f"{offer} payments with no client tag (the open page sold them):")
        for pi in rows:
            email = (pi.get("receipt_email") or "").strip()
            print(f'  {pi["id"]}  {money(pi["amount_received"] or pi["amount"]):>10}  '
                  f'{day(pi["created"])}  {email or "(no email on file)"}')
        print(f"\nFile one onto a person: credit <slug> --tag <payment id>")
        return 0
    if not args.client:
        sys.exit("credit needs a person slug, or --unfiled to list the untagged payments.")
    if args.tag:
        tag_client(args.tag, args.client)
        print(f"TAGGED   {args.tag} -> client={args.client}")
    rows = credit_ledger(args.client, offer, window)
    if not rows:
        print(f"No {offer} payments tagged client={args.client}.")
        return 0
    span = f"{window}-day window" if window else "no window"
    print(f"{offer} payments for client={args.client} ({span}):")
    available = 0
    for r in rows:
        if r["expired"]:
            state = f'expired, paid {r["age_days"]} days ago'
        elif r["spent_on"]:
            state = f'already credited on {r["spent_on"]}'
        else:
            available += r["amount"]
            left = window - r["age_days"] if window else None
            state = "available" + (f", {left} day(s) left" if left is not None else "")
        print(f'  {r["id"]}  {money(r["amount"]):>10}  {day(r["created"])}  {state}')
    print(f"\nCreditable now: {money(available)}")
    if available:
        print(f"Next: new --offer <container> --amount <gross> --credit-client {args.client}")
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
    n.add_argument("--meta", action="append", metavar="KEY=VAL",
                   help="extra metadata to tag the link, repeatable (e.g. --meta door=all-in)")
    n.add_argument("--redirect", metavar="URL",
                   help="send the buyer here after payment (the booking page)")
    n.add_argument("--credit-client", dest="credit_client", metavar="SLUG",
                   help="subtract what this client already paid toward the container")
    n.add_argument("--credit-offer", dest="credit_offer", metavar="SLUG",
                   help=f"offer slug that credits (default: {credit_offer()})")
    n.add_argument("--credit-window", dest="credit_window", type=int, metavar="DAYS",
                   help=f"days a payment stays creditable (default: {credit_window_days()}; 0 for no window)")
    n.add_argument("--credit-force", dest="credit_force", action="store_true",
                   help="credit a payment another link already spent (a declined offer whose link you closed)")
    n.add_argument("--dry-run", dest="dry_run", action="store_true")
    n.add_argument("--yes", action="store_true", help="create it live")
    n.set_defaults(func=cmd_new)

    x = sub.add_parser("close", help="deactivate an offer's links")
    x.add_argument("--offer", required=True)
    x.add_argument("--dir")
    x.add_argument("--dry-run", dest="dry_run", action="store_true")
    x.add_argument("--yes", action="store_true", help="deactivate live")
    x.set_defaults(func=cmd_close)

    r = sub.add_parser("credit", help="what a client has already paid toward a container")
    r.add_argument("client", nargs="?", help="person slug, as tagged on the payment (e.g. robert-farrior)")
    r.add_argument("--unfiled", action="store_true",
                   help="list succeeded payments carrying no client tag")
    r.add_argument("--tag", metavar="PAYMENT_ID",
                   help="file that payment onto this client, then show the ledger")
    r.add_argument("--credit-offer", dest="credit_offer", metavar="SLUG",
                   help=f"offer slug that credits (default: {credit_offer()})")
    r.add_argument("--credit-window", dest="credit_window", type=int, metavar="DAYS",
                   help=f"days a payment stays creditable (default: {credit_window_days()}; 0 for no window)")
    r.set_defaults(func=cmd_credit)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
