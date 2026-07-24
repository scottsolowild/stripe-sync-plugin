---
description: Check offer payment links against Stripe and report drift.
---

Run the stripe-sync skill. Check every `buy.stripe.com` link in the offers
folder against the Stripe API: active status, amount matches the doc, and
metadata carries the offer slug.

- Default to a check (read-only). Only reconcile metadata with `--fix` when the user asks, or when they clearly want the drift fixed.
- Never auto-fix an amount change. Flag it: a new price and link, swap the URL, deactivate the old one.
- Report what drifted and what changed, per link.

Arguments after the command (a folder path, `--fix`, `--fix-gated`) pass through: $ARGUMENTS
