# Changelog

## 1.1.0 (2026-11-16)

- Settings window at start-up: language (or follow the game), opacity, font size, which panels
  to show, live reading on/off, reset the overlay position, skip it next time. Start sends it to
  the taskbar; click it there or press F6 to change things while playing, they apply right away.
  `--no-settings` skips it for one launch.
- The overlay follows the game's language. Catalogs for English, Korean, Japanese, Simplified and
  Traditional Chinese, German, Spanish, Brazilian Portuguese, Russian and Vietnamese.
- Relic names and descriptions come from the game's table for the current language.
- `--lang` to pick a language by hand.
- Numbers use the separators of the selected language.

## 1.0.0 (2026-11-15)

First release.

- Real odds for the next strike, read from the game's odds function, with a strike / stop call.
- Multi-strike plan that accounts for Frenzy, calibrated to how fast you hit.
- Today's tribute, the next days' schedule, a pace estimate and the best swords to offer.
- Buy / drop / swap simulation for relics, a break-reduction ranking at +8/+12/+16, ★ for the
  ones worth hunting.
- Ghost merchant and relic shop reroll advice.
- "To do" panel, F7 legend, official Vietnamese relic names, sword on the anvil always listed first.
- Run and per-day logs.
