# stripe-sync

Your offer docs are the source of truth. Stripe follows them.

If you keep your offers as markdown and drop a Stripe payment link in each one,
this plugin keeps the two honest: every link active, every price matching the
doc, every link tagged with the offer it belongs to. It catches the quiet
failure where you change a price in the doc but the old link keeps charging the
old amount.

## Install

In Claude Code:

```
/plugin marketplace add scottsolowild/stripe-sync-plugin
/plugin install stripe-sync@solo-plugins
```

Then just say `/stripe-sync`, or "check my payment links."

## What it checks

For every `buy.stripe.com` link found in your offer docs:

1. **Active.** The link still works, and a closed offer's link is turned off.
2. **Amount.** Stripe charges what the doc says. This works when you link the price as the anchor text, like `[$5,000](https://buy.stripe.com/xxxx)`.
3. **Metadata.** The link carries the offer's slug, so the Stripe dashboard tells you whose money each payment is.

## The one rule worth internalizing

**An amount change means a new link, never an edit.** Stripe payment links do
not let you change a price after the fact, and that is a feature. If you could,
a PDF or a page you sent last month would silently start collecting the wrong
number. So when a price changes: mint a new link, swap the URL in the doc,
deactivate the old one. The plugin flags amount drift and refuses to auto-fix
it, on purpose.

## Running it directly

The skill runs the bundled script for you. To run it by hand:

```
STRIPE_API_KEY=sk_live_... python3 scripts/stripe_sync.py            # check
STRIPE_API_KEY=sk_live_... python3 scripts/stripe_sync.py --fix      # reconcile metadata
```

Config, all optional:

| Variable | Default | Meaning |
| --- | --- | --- |
| `OFFERS_DIR` (or `--dir`) | `offers` | Folder scanned for `*.md`. |
| `CLOSED_DIRS` | `retired,closed` | Subfolders whose links should be off. An active one is drift. |
| `LOCKED_DIRS` | `accepted` | Subfolders where drift is reported but never auto-fixed without `--fix-gated`. |

It exits nonzero when it finds drift and you did not pass `--fix`, so it also
works as a pre-commit hook or a CI check.

No key on hand? With the Stripe MCP connected, the skill does the same work
through the API tools.

## License

MIT. Take it, change it, ship your own.
