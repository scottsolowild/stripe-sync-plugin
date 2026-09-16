---
name: stripe-sync
description: >
  Run your Stripe payment links from your offer docs, without the dashboard.
  Create a tagged link, check amounts against the docs, and deactivate an
  offer's links when it closes. Trigger on "/stripe-sync", "new stripe link",
  "create a payment link", "a payment link for an offer", "an offer link for
  <client>", "generate a link for <offer>", "sync stripe", "check the payment
  links", "close the links for <offer>", "credit what they already paid",
  "take their deposit off this one", or after editing amounts or slugs in
  your offers folder.
---

# stripe-sync

The offer docs are the source of truth. Stripe follows them. You work from the
chat you are already in, and the dashboard stays closed.

Four things it does, all of them tagging every link so the Stripe dashboard
tells you which offer (and which customer) each payment belongs to:

- **new** a price and payment link at an amount.
- **check** that every link is live and charges what the doc says.
- **close** an offer's links when it is done.
- **credit** what a client already paid toward a bigger offer, once.

## The one rule

An amount never changes on a live link. Stripe locks a link's price once it is
live, and that is a feature: a copy you already sent keeps pointing at the
right number. So a price change is a new link plus the old one closed, never an
edit in place.

## With a Stripe key (the bundled script)

The key comes from `STRIPE_API_KEY` in the environment, or from the key the
user entered at install (the script also reads `CLAUDE_PLUGIN_OPTION_STRIPE_API_KEY`).
If neither is set, the script says so; ask the user for their key (a test key,
`sk_test_...`, to start) and have them export it, then:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stripe_sync.py" check [--fix] [--dir path/to/offers]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stripe_sync.py" new --offer spring-workshop --amount 5000 --customer jordan
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stripe_sync.py" close --offer spring-workshop
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stripe_sync.py" credit jordan
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stripe_sync.py" new --offer spring-intensive --amount 6000 --credit-client jordan
```

**Anything that writes to Stripe dry-runs first.** `new` and `close` show what
they would do and change nothing until you pass `--yes`. Always run the plan,
show it to the person, get a yes, then re-run with `--yes`. `check` is
read-only unless you pass `--fix`, which only reconciles metadata.

- **new** creates the price and link, tags `offer` (and `customer` when given), sets a plain-words description, and prints the URL. Paste it into the doc, then run `check`. Add any extra metadata with repeatable `--meta key=val` (e.g. `--meta door=all-in --meta client=jordan`) to stamp your own attribution onto the link.
- **close** deactivates every link whose metadata `offer` matches the slug.
- **credit** reads every succeeded payment tagged `client=<slug>` under the crediting offer (`STRIPE_CREDIT_OFFER`, default `design`) and says which are still inside the window and which a link already spent. `--tag <payment id>` files a payment onto a person, for a link that sold to whoever clicked, and `--unfiled` lists those.

## With the Stripe MCP and no key

Do the same work through the MCP tools. Same rule, same gate: for a create or
a deactivate, describe exactly what you are about to do (amount, currency,
metadata, which links), get a yes, then call the tool. Tag every new link with
the offer and customer, and give it a human description.

## Crediting a smaller thing into a bigger one

A paid intro session that comes off a larger container is arithmetic, not a
discount. So `new --credit-client <slug>` reads what that client already paid,
subtracts it, mints the link at the net, and stamps the payment ids it spent
onto the new link as `credit_from`. That stamp is the ledger: it is what stops
the same payment coming off two containers, and it is why no coupon is
involved. A promotion code would show the buyer a discount at the one moment
they are reading the number.

A payment link charges one number and its API takes no pre-applied discount,
only a promotion code the buyer types in, so Stripe's page can only ever show
the net. `new --credit-client` therefore prints three lines to put on the offer
page above the button: the full price, the credit with the date it was paid,
and what is owed today. Show them to the user with the link. The arithmetic
belongs on that page anyway, since it is where the buyer decides and the words
are the seller's rather than Stripe's "Discount" label.

The window is `--credit-window` days (default 30, `0` for none), and
`--credit-force` takes a payment another link already spent, for the case where
that offer was declined and its link closed. Reading payments needs
`payment_intent_read` on a restricted key; without it the command exits naming
the permission Stripe wants.

## The convention check reads

The amount check works when the doc links the price as the anchor text:

```
Pay here: [$5,000](https://buy.stripe.com/xxxx)
```

A link whose text is not a dollar amount is still checked for active status and
metadata. Only its amount check is skipped. Closed folders (`CLOSED_DIRS`,
default `retired,closed`) should hold no active links; locked folders
(`LOCKED_DIRS`, default `accepted`) report drift but are never auto-fixed
without `--fix-gated`, because live money already changed hands there.

## Report

Say what you did. New links with their URL, closed links listed,
drift named per link. Never repriced a live link; that always becomes a new one.
