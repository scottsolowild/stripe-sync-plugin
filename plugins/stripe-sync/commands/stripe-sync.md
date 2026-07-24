---
description: Create, check, or close Stripe payment links from your offer docs.
---

Run the stripe-sync skill. Work Stripe payment links from the offer docs
without opening the dashboard:

- **new** a tagged price and link at an amount (`new --offer <slug> --amount <dollars> [--customer <name>] [--meta key=val ...]`).
- **check** every link against the docs: active, amount matches, tagged right.
- **close** an offer's links when it is done (`close --offer <slug>`).

Rules:
- Anything that writes to Stripe dry-runs first. Show the plan, get a yes, then run with `--yes`.
- Never reprice a live link. A price change is a new link and the old one closed.
- Tag every new link with the offer, and the customer when known.

Arguments pass through: $ARGUMENTS
