# Changelog

All notable changes to stripe-sync are recorded here. Versions follow SemVer,
and for this plugin the contract those versions promise is three things: the
natural-language skill behavior, the documented CLI flags, and the metadata
keys written onto a link (`offer`, `customer`, and any `--meta` you rely on). A
**major** bump means one of those changed in a breaking way; a **minor** bump
adds capability; a **patch** fixes without touching the contract. Pre-1.0, the
contract is not yet frozen, so expect the shape to move.

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
