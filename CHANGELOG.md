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
- New look for the panels: rounded dark cards with a thin border, a small icon next to each
  section, a five-colour bar under every sword's odds (break, damage, no change, success, great),
  bars for today's tribute (delivered, what you hold, the quota mark) and for the contract pace,
  and the strike / stop call drawn as a coloured pill. The text is the same as before, and the
  bars are the first thing to go when a panel has to shrink to fit the screen.
- Alerts: when a Frenzy starts the to-do panel's border flashes and Windows plays its short
  "exclamation" sound; when today's tribute can't be covered with the swords you hold, the detail
  panel flashes once that day; when a ★ relic shows up for sale, the to-do panel flashes once.
  To turn the sound off set `"sound_alerts": false` under `settings` in config.json.
- Per-monitor DPI: the overlay is now per-monitor DPI aware, so on setups that mix scaling levels
  (say a 4K at 150% next to a 1440p at 100%) the panels are no longer blurry or oddly sized after
  you move them to the other screen. Fonts are re-measured for the monitor each panel is on.

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
