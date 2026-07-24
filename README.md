# stripe-sync

Run your Stripe payment links from your offer docs, without the dashboard.

If you keep your offers as markdown and pay through Stripe payment links, this
plugin moves the link work into Claude Code. Make a link by asking for it,
tagged so the Stripe dashboard tells you which offer and which customer each
payment belongs to. Keep every link true to the doc that sells it. Turn an
offer's links off when it closes. The Stripe tab stays shut.

## Install

In Claude Code:

```
/plugin marketplace add scottsolowild/stripe-sync-plugin
/plugin install stripe-sync@solo-plugins
```

Then talk to it: "new stripe link for the spring workshop at $5,000 for Jordan,"
or "check my payment links," or "close the links for spring-workshop."

## What it does

- **Makes links.** A price and a payment link at the amount you name, tagged with the offer and the customer, described in plain words. It prints the URL to drop in the doc.
- **Tags every link.** The offer and customer ride in the link's metadata, so a payment in your Stripe dashboard reads as a person and an offer, not a bare number.
- **Keeps amounts true.** It checks that every link charges what its doc says, and flags any that drifted.
- **Closes links.** When an offer is done or declined, one word turns off all of its links.

## The one rule

**A price change is a new link, never an edit.** Stripe locks a link's price
once it is live, and that is a feature. So when a price moves: mint a new link,
swap the URL in the doc, close the old one. Anything you already sent keeps
pointing at the right number. The plugin will not reprice a live link, on purpose.

## Anything that writes to Stripe asks first

Creating a link and closing links both dry-run first. They show you exactly
what they will do and change nothing until you confirm. Checking is read-only.

## Running it directly

The skill runs the bundled script for you. By hand:

```
STRIPE_API_KEY=sk_live_... python3 scripts/stripe_sync.py check
STRIPE_API_KEY=sk_live_... python3 scripts/stripe_sync.py new --offer spring-workshop --amount 5000 --customer jordan
STRIPE_API_KEY=sk_live_... python3 scripts/stripe_sync.py close --offer spring-workshop
```

`new` and `close` show a dry-run plan; add `--yes` to run it live. `check`
reconciles metadata with `--fix`.

Config, all optional:

| Variable | Default | Meaning |
| --- | --- | --- |
| `OFFERS_DIR` (or `--dir`) | `offers` | Folder `check` scans for `*.md`. |
| `STRIPE_CURRENCY` | `usd` | Currency for new links. |
| `STRIPE_PRODUCT` | (per-offer) | Reuse one Stripe product id instead of creating one per offer. |
| `CLOSED_DIRS` | `retired,closed` | Subfolders whose links should be off. An active one is drift. |
| `LOCKED_DIRS` | `accepted` | Subfolders where drift is reported but never auto-fixed without `--fix-gated`. |

No key on hand? With the Stripe MCP connected, the skill does the same work
through the API tools, with the same ask-first gate.

## License

MIT. Take it, change it, ship your own.
