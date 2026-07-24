---
name: stripe-sync
description: >
  Run your Stripe payment links from your offer docs, without the dashboard.
  Create a tagged link, check amounts against the docs, and deactivate an
  offer's links when it closes. Trigger on "/stripe-sync", "new stripe link",
  "sync stripe", "check the payment links", "close the links for <offer>", or
  after editing amounts or slugs in your offers folder.
---

# stripe-sync

The offer docs are the source of truth. Stripe follows them. You work from the
chat you are already in, and the dashboard stays closed.

Three things it does, all of them tagging every link so the Stripe dashboard
tells you which offer (and which customer) each payment belongs to:

- **new** a price and payment link at an amount.
- **check** that every link is live and charges what the doc says.
- **close** an offer's links when it is done.

## The one rule

An amount never changes on a live link. Stripe locks a link's price once it is
live, and that is a feature: a copy you already sent keeps pointing at the
right number. So a price change is a new link plus the old one closed, never an
edit in place.

## With a Stripe key (the bundled script)

`STRIPE_API_KEY` in the environment, then:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stripe_sync.py" check [--fix] [--dir path/to/offers]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stripe_sync.py" new --offer spring-workshop --amount 5000 --customer jordan
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stripe_sync.py" close --offer spring-workshop
```

**Anything that writes to Stripe dry-runs first.** `new` and `close` show what
they would do and change nothing until you pass `--yes`. Always run the plan,
show it to the person, get a yes, then re-run with `--yes`. `check` is
read-only unless you pass `--fix`, which only reconciles metadata.

- **new** creates the price and link, tags `offer` (and `customer` when given), sets a plain-words description, and prints the URL. Paste it into the doc, then run `check`.
- **close** deactivates every link whose metadata `offer` matches the slug.

## With the Stripe MCP and no key

Do the same work through the MCP tools. Same rule, same gate: for a create or
a deactivate, describe exactly what you are about to do (amount, currency,
metadata, which links), get a yes, then call the tool. Tag every new link with
the offer and customer, and give it a human description.

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
