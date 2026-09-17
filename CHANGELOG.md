# Changelog

All notable changes to stripe-sync are recorded here. Versions follow SemVer,
and for this plugin the contract those versions promise is three things: the
natural-language skill behavior, the documented CLI flags, and the metadata
keys written onto a link (`offer`, `customer`, and any `--meta` you rely on). A
**major** bump means one of those changed in a breaking way; a **minor** bump
adds capability; a **patch** fixes without touching the contract. Pre-1.0, the
contract is not yet frozen, so expect the shape to move.

## [0.5.3] - 2026-09-17

### Fixed
- The docs now say `STRIPE_CREDIT_OFFER` defaults to `plan`. The default moved to `plan` in 0.5.2 and three places still said `design`: the README config table, the module docstring, and the skill's `credit` line. The skill line is the one that reached you, since Claude reads it while the skill runs and would state the old default back as fact.

## [0.5.2] - 2026-09-17

### Changed
- `STRIPE_CREDIT_OFFER` now defaults to `plan` instead of `design`, following a rename in the offer it was written for. Set the variable to your own crediting offer's slug either way: the default is one person's name for the thing, and the credit lookup matches payments on it, so a payment stamped with the old slug is invisible to a lookup for the new one.

## [0.5.1] - 2026-09-17

### Changed
- `new --redirect URL` says so when the URL carries no `{CHECKOUT_SESSION_ID}`. Stripe swaps that template for the checkout session id on the way out, and a landing page that opens only for a paid arrival reads it. Without it, a buyer who has just paid arrives at a page that asks him to pay. The note prints on the dry run and on the live create, and a URL that carries the template stays quiet.

## [0.5.0] - 2026-09-16

### Added
- `credit <client>`: read every succeeded payment tagged to a client under the crediting offer, with whether each is still inside its window and whether a link already spent it. `--unfiled` lists payments carrying no client slug, for a link that sold to whoever clicked, and `--tag <payment id>` files one onto a person.
- `new --credit-client <slug>`: subtract what that client already paid, mint the link at the net, and stamp the payment ids it spent onto the new link as `credit_from`. That stamp is what stops one payment coming off two offers. `--credit-window`, `--credit-offer`, and `--credit-force` tune it.
- `new --redirect URL`: send the buyer to a page of your own after payment (a booking calendar, a welcome page), through the link's `after_completion`.
- A credited `new` prints the three lines to show on the offer page: the full price, the credit with the date it was paid, and what is owed today. A payment link charges one number and the API takes no pre-applied discount, only a promotion code the buyer types, so the arithmetic has to live on the page.
- `STRIPE_CREDIT_OFFER` and `STRIPE_CREDIT_WINDOW_DAYS`.

### Changed
- A Stripe error now exits with the message Stripe sent instead of a traceback. A restricted key missing a permission says which permission and where to add it, since reading payments needs `payment_intent_read`.

## [0.4.0] - 2026-07-24

### Added
- `new --meta key=val` (repeatable) stamps arbitrary metadata onto the link and its payment intent, so a setup can carry its own attribution (a client slug, an all-in vs stretch door).
- README links to Stripe's test and live API key pages, and its examples reflect real offer work.

## [0.3.0] - 2026-07-24

### Added
- Install-time key prompt (`userConfig`, marked sensitive): the plugin can ask for your Stripe key at install. The script reads `STRIPE_API_KEY`, or `CLAUDE_PLUGIN_OPTION_STRIPE_API_KEY` if the platform passes it through.
- Broader skill triggers, so natural phrasing ("create a payment link", "an offer link for &lt;client&gt;") fires it.

### Changed
- README leads with the real flow (install, set the key, talk to it in plain English) and clarifies the plugin makes the payment link, not the offer copy.

## [0.2.0] - 2026-07-24

### Added
- `new`: create a tagged price and payment link at an amount.
- `close`: deactivate every link tagged to an offer.

### Changed
- Writes to Stripe dry-run first and require `--yes`; a live link is never repriced (a price change is a new link plus the old one closed).

## [0.1.0] - 2026-07-24

### Added
- First release: the `stripe-sync` skill and `/stripe-sync` command.
- `check`: verify every `buy.stripe.com` link in your offer docs against Stripe (active, amount matches the doc, tagged with the offer); `--fix` reconciles metadata.
- Configurable offers folder, closed and locked folders, currency, and a shared Stripe product.
