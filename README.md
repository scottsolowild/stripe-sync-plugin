# stripe-sync

Run your Stripe payment links from Claude Code, without the dashboard.

If you sell through Stripe payment links, this plugin moves the link work into
a conversation. You ask for a link, it creates the price and the link, tags it
with the offer and the customer, and hands you the URL to drop in your doc. It
keeps every link charging what its doc says, and turns an offer's links off
when it closes. The Stripe tab stays shut.

It makes and manages the payment **link**. It does not write your offer copy;
that stays yours.

## Setup (once)

**1. Install it**, in Claude Code:

```
/plugin marketplace add scottsolowild/stripe-sync-plugin
/plugin install stripe-sync@solo-plugins
```

**2. Give it your Stripe secret key.** Two ways, either works:

- **At install:** Claude Code prompts for your key and stores it (it is marked sensitive). Nothing to configure.
- **By hand:** export it where Claude Code's shell can see it, in the shell you launch `claude` from, your shell profile, or a project `.env`:
  ```
  export STRIPE_API_KEY=sk_live_...
  ```

Grab the key from your Stripe dashboard:

- **[Test keys](https://dashboard.stripe.com/test/apikeys)** (`sk_test_...`) run in Stripe's sandbox, no real money, nothing touching your live account. Start here.
- **[Live keys](https://dashboard.stripe.com/apikeys)** (`sk_live_...`) create real charges. Switch to one once you have seen the flow.

## Use it

Say what you want in plain English. No commands to memorize:

- "create a payment link for $5,000 for Jordan on the crossroads offer"
- "check my payment links"
- "close the links for crossroads"

Claude runs the plugin for you. Anything that writes to Stripe (creating a
link, closing links) shows you the plan first and waits for your yes. Checking
is read-only. You paste the URL it gives you into your offer doc.

## What it does

- **Makes links.** A price and a payment link at the amount you name, tagged with the offer and the customer, described in plain words.
- **Tags every link.** The offer and customer ride in the link's metadata, so a payment in your Stripe dashboard reads as a person and an offer, not a bare number.
- **Checks the amount.** Every link should charge what its doc says, and it flags any that drifted.
- **Closes links.** When an offer is done or declined, one word turns off all of its links.

## The one rule

**A price change is a new link, never an edit.** Stripe locks a link's price
once it is live, and that is a feature. So when a price moves: mint a new link,
swap the URL in the doc, close the old one. Anything you already sent keeps
pointing at the right number. The plugin will not reprice a live link, on purpose.

## Run it by hand (optional)

The skill runs the bundled script for you, so you never have to. To run it
directly, or to wire `check` into a pre-commit hook or CI:

```
STRIPE_API_KEY=sk_test_... python3 scripts/stripe_sync.py check
STRIPE_API_KEY=sk_test_... python3 scripts/stripe_sync.py new --offer crossroads --amount 5000 --customer jordan --meta door=all-in
STRIPE_API_KEY=sk_test_... python3 scripts/stripe_sync.py close --offer crossroads
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

## Changelog

Version history and the versioning contract are in [CHANGELOG.md](CHANGELOG.md).

## License

MIT. Take it, change it, ship your own.
