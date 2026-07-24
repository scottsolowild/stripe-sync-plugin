---
name: stripe-sync
description: >
  Keep Stripe payment links true to your offer docs. Run after any edit that
  renames an offer doc, changes a price, or closes an offer. Trigger on
  "/stripe-sync", "sync stripe", "check the payment links", or automatically
  after editing amounts or slugs in your offers folder.
---

# stripe-sync

The docs are the source of truth. Stripe follows them. One link per offer, an
amount that matches the doc, and metadata that says which offer each link
belongs to.

## Run it

- **With an API key:** `STRIPE_API_KEY=sk_live_... python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stripe_sync.py"` to check, add `--fix` to reconcile metadata. Point it at your offers with `--dir path/to/offers` or `OFFERS_DIR`. The script pages every payment link, matches each `buy.stripe.com` URL found in your `*.md` docs, and reports drift. Nonzero exit on drift, so it also works as a pre-commit hook or a CI gate.
- **With the Stripe MCP and no key:** do the same work through the API tools. List the payment links, match each `buy.stripe.com` URL found in your offer docs, and compare active status, amount, and metadata by hand.

## The convention

The amount check works when the doc links the price as the anchor text:

```
Pay here: [$5,000](https://buy.stripe.com/xxxx)
```

A link whose text is not a dollar amount is still checked for active status
and metadata. Only its amount check is skipped.

## The rules

- **Rename or re-slug an offer doc** → update the link's `metadata.offer` (and `payment_intent_data.metadata.offer`) in place. The URL stays, so any PDF or page already sent keeps working.
- **Amount changed** → never edit the existing link. Stripe payment links are immutable on price for a reason. Create a new price and a new payment link at the new amount, swap the URL in the doc, and deactivate the old link so a stale copy can't collect the old price. The script flags this and refuses to auto-fix it; the human (or the session making the edit) does the swap.
- **Offer closed, declined, or dead** → deactivate that offer's links. Move the doc into a closed folder (`CLOSED_DIRS`, default `retired,closed`). An active link under a closed folder is drift.
- **Locked folders** (`LOCKED_DIRS`, default `accepted`) → report drift there, change nothing until the human says yes, then `--fix-gated`. Live money already changed hands under these; do not touch them on a whim.
- Give each generated link a plain-words `payment_intent_data.description` ("Offer: spring-workshop") so payments read human in the Stripe dashboard.

## Report

Say what drifted and what you did, straight. Fixed metadata listed per link;
amount drift flagged for the new-link treatment, never auto-fixed.
