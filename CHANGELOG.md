# Changelog

## Unreleased

- Simulation tab in the settings window. It replays the rest of your run 2,000 times (or as many
  as fit in about a second) with the game's own odds and tribute schedule and compares four ways
  of playing: follow the overlay, careful (no 10 %+ break risks), bold (keep pushing your best
  sword), safe strikes only. You get the chance of still being in the run after each day, the
  average day each one gets to, and which one comes out ahead. Without a live connection it falls
  back to the save file and rough odds, and says so. It only uses probabilities; the game's RNG is
  never read.
- Stats tab: runs played, wins, furthest and average day, which day lost runs ended on, highest
  grade per run, and when you usually miss your first tribute.
- New version notice: at start-up ForgeSeer asks GitHub once whether there's a newer release and
  shows a link at the top of the settings window. Offline or rate limited, it just stays quiet.
  "Check for a new version at start-up" turns it off.

## 1.1.1 (2026-11-16)

- The panels now fit on any screen. On 1080p, 1440p or with Windows scaling above 100% the detail
  panel used to run off the bottom; now it picks a smaller font, then hides the less important
  lines (stats, relic ranking, shop descriptions, plan details), then uses two columns if there's
  room, and as a last resort shows how many lines didn't fit. It follows the monitor the panel is
  on, so moving it with F9 to another screen works too.

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
