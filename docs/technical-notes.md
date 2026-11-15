# Technical notes

My notes on how ForgeSeer is put together and what I've found out about ForgeTax's internals.
If something here turns out to be wrong after a game update, please open an issue.

## Running

```bash
python -m forgeseer             # overlay (attaches to the game if it's running)
python -m forgeseer --no-live   # save file only
python -m forgeseer --once      # print the current state and exit
python -m forgeseer --lang ja   # force a language
python -m forgeseer --no-settings  # skip the start-up settings window
python -m pytest -q
```

Hotkeys: F6 settings, F7 legend, F8 hide/show, F9 drag/lock (position is saved in
`%APPDATA%\ForgeTaxOverlay\config.json`), F10 quit.

## Ground rules

- Read-only. Nothing writes to game memory or the save file. Simulations run on fresh objects
  created with `JsonUtility.FromJson`, never on the live campaign.
- No predictions from the RNG state (`random.s0..s3` in the save). The game has leaderboards and
  that would be cheating, not strategy.
- Every probability comes from the game's own functions.
- UI text goes through `i18n.t()`. New wording means a new key in every file under
  `forgeseer/locales/` (the tests check that the key sets and placeholders match). Use the game's
  own term when its localization table has one. New concepts on the overlay get a legend entry.
- Numbers go through `text_format` (`fmt_int`, `fmt_ratio`, `fmt_pct`), which picks separators
  from the catalog. Lines longer than `LINE_WIDTH` (72 columns, CJK counts double) wrap onto an
  indented continuation line.

## Fitting the panels on screen

Fonts are in points, so a panel grows with Windows scaling. The detail panel is about 520×1560 px
at 4K 100% with font 10, which is taller than a 1080p screen and than 1440p at 125%. Every render
each panel is fitted to the work area (taskbar excluded) of the monitor it sits on
(`MonitorFromWindow` + `GetMonitorInfoW`, falling back to Tk's screen size), minus a 20 px margin.
`panel_layout.fit_layout` is pure and works from font metrics measured once from Tk:

1. the font size from the settings, then smaller sizes down to 8;
2. compact mode: drop the lines marked low priority (third tuple element `LOW`: sword detail and
   plan sub-lines, the break-reduction ranking incl. the conditional relics line, stats and the run
   summary, shop description rows), at the largest size that fits;
3. two columns, only if both together take at most half the work-area width; it prefers to break
   between sections, then at the start of a block, so a sword is never split across columns;
4. otherwise cut the panel and say how many lines are hidden (`layout.more`), always keeping the
   status and hotkey lines.

`format_state(..., keep_priority=True)` keeps the `LOW` marker; without it the result is the usual
`(text, tag)` pairs. The detail panel is pushed back inside the work area if it would stick out.
To try a small screen on a big one, set `FORGESEER_WORK_AREA=1920x1040`.

## Languages

Catalogs: vi, en, ko, ja, zh-CN, zh-TW, de, es, pt-BR, ru. Language is chosen as
`--lang` > the game's language (live) > Windows UI language > English, and it switches at runtime
when the game's language changes.

The game's localization table (see below) only holds translations: de, es, ja, pt-BR, ru, vi,
zh-CN, zh-TW. Korean and English strings live in code, so for those the official relic names
aren't available and the overlay falls back to the Vietnamese names.

The live script finds the current language by reading the tribute ledger caption
(`GPT6ForgeRoom.ledgerText`, first line, key `ui.quota_caption`) and matching it against each
table. No match plus Hangul means `ko`, plain Latin text means `en`. If the ledger isn't readable
it looks for a static string field on `ForgeLocalization` that holds a language code. I haven't
been able to confirm this against a running game yet (Frida was being blocked by antivirus when
I tested), so treat it as best effort; `--lang` always works.

## Modules (`forgeseer/`)

| File | What it does |
|---|---|
| `save_reader.py` | Parses the save JSON into `RunState`, `Sword`, `Relic`, `Offer`, `MerchantOffer`. `Sword.tag` is "+N position". |
| `live_capture.js` | Frida script inside the game. Hooks `GPT6ForgeRoom.Update` (main thread) and sends state, odds, simulations, relic texts and the current language. |
| `live_relic_rank.js` | Appended after `live_capture.js` into one script (`live_source.load_script_source`) and shares its helpers. Ranks relics by how much they cut the break chance. |
| `live_quota_schedule.js` | Appended after that. `forecastSchedule` sends `quotaSchedule`: tribute for each day from round+1 to min(contractDeadlineRound, round+10). |
| `live_source.py` | Background thread that attaches Frida to `ForgeTax.exe`, receives messages, keeps relic texts per language. |
| `i18n.py` | `t(key, **values)`, language detection and fallback. Catalogs in `locales/<code>.json`. |
| `advisor.py` | `SwordOdds`, one-strike EV, `ShopSimulation`, `GradeOddsTable`. |
| `planner.py` | Optimal-stopping DP over (grade, charge) including Frenzy bursts of `fever_strikes` strikes. `safe_only=True` only allows strikes that can't break (a cautious estimate used for pace). |
| `fever_calibration.py` | Measures how many strikes the player lands per Frenzy; the running average lives in config.json under `fever` (default 7). |
| `reroll_advice.py` | When to reroll the relic shop (free, or gold ≥ 10× the price). |
| `run_log.py` | Appends finished runs to `%APPDATA%\ForgeTaxOverlay\runs.jsonl` (deduped by anonymousRunId) and builds the summary line. |
| `day_log.py` | Appends an end-of-day snapshot to `days.jsonl` (round, quota, delivered, holdings, top grade, missed). Not shown on the overlay yet. |
| `config.py` | Shared config.json (position `x/y`, `fever`, `game_lang`, `settings`). Writes merge keys. |
| `settings.py` | `Settings` (language or `auto`, opacity 40-100, font 8-16, panel flags, live, skip). Pure: clamping, load/save under `settings`, which panels are visible. `--lang` / `--no-live` pre-fill it. |
| `settings_window.py` | Start-up settings screen (ttk). The Tk root itself, so it has a taskbar icon. Only reports changes through callbacks. |
| `app.py` | One Tk root, one mainloop. Start saves the settings, iconifies the window and creates the overlay; F6 / taskbar restore shows it again and every change goes to `Overlay.apply_settings`. X minimizes, Quit / F10 stops everything including `LiveSource`. |
| `tribute.py` | Tribute status, tribute-driven verdicts, and `choose_tribute`: tries every subset (n ≤ 12, greedy above that) and picks the swords that cover the tribute while giving up the least future value (value × `Plan.ratio`, finished swords count as 1; ties go to the smallest overpay). |
| `pace.py` | Contract pace: swords on hand (value × safe-strike expectation) plus 3 fresh +0 swords a day against the cumulative tribute of the next 3 days. `risk_hint` says push the main sword when behind, and don't take ≥10% break risks when ahead by 1.5×. It never overrides a sword held for today's tribute. |
| `sword_section.py` | Sword list and `sword_verdict` (priority: Frenzy > tribute > plan > EV). |
| `shop_advice.py` | Buy / drop / swap advice from the simulations. |
| `merchant_advice.py` | Ghost merchant advice. |
| `relic_rank.py` | Parses `relicRank`, top 8 by break reduction at +12 (ties: +16, then +8), the "★ Buy" step. |
| `action_plan.py` | Right-hand "To do" panel. |
| `formatter.py` | Left-hand detail panel. |
| `text_format.py` | Number formatting and line wrapping shared by every panel. |
| `panel_layout.py` | Fits a panel to the monitor's work area: smaller font, compact mode, two columns, then a "… +N" cut. Pure. |
| `legend.py` | F7 legend. |
| `overlay.py` | The three overlay panels (details, to-do, legend), polling, hotkeys, live settings changes (opacity, font, panels, language, starting/stopping `LiveSource`). |
| `overlay_windows.py` | Win32 bits: borderless topmost click-through Toplevels (WS_EX_TRANSPARENT), each with its own fonts (fitting can shrink one panel without the others), the monitor work area, font metrics, two-column fill. |
| `simulator/` | Monte Carlo of the rest of the run (see below). `model.py` inputs and fallbacks, `strategies.py` the decision rules, `engine.py` the loop. Pure, no Tk. |
| `sim_tab.py` / `stats_tab.py` / `charts.py` | Simulation and Stats tabs of the settings window, drawn on a plain Tk canvas. |
| `stats.py` | Numbers for the Stats tab from `runs.jsonl` and `days.jsonl` (`day_log.load_days`). |
| `update_check.py` | One background GET to the GitHub "latest release" API at start-up (3 s timeout, failures silent); compared with `forgeseer.__version__`. Setting `check_updates`. |
| `relic_names.py/.json` | Fallback relic names (my own Vietnamese translations of the ids); official names come from the game and are cached in `%APPDATA%\ForgeTaxOverlay\relic_texts.json` for every language. |

## What I know about the game

Unity 6000.5, IL2CPP, obfuscated with Obfuz: method names are scrambled, serialized field names
are intact.

- Save file: `%USERPROFILE%\AppData\LocalLow\DefaultCompany\ForgeTax\Save\run_release*_v*.json`,
  shaped `{version, payload: "<JSON>", checksum}`. The payload is a `ForgeSavedRun` (campaign,
  swords, delivered, ...).
- `GameAssembly.dll` exports all the `il2cpp_*` functions, so Frida can call into the runtime.
- `GPT6ForgeRoom` (MonoBehaviour): `campaign` (ForgeCampaign), `quota` (tribute due this round),
  `enhancementBalance` (ScriptableObject: `baseValue` = 320, `gradeMultiplier` @32 float = 1.5,
  `rows` base odds table). Sword lists sit in the `$UB/$ic/$rc` fields (found by type, skipping
  `swordPrefab`). The instance method with no parameters that returns `ForgeSavedRun` (currently
  `$KC`) is the save snapshot, which goes through `JsonUtility.ToJson`.
- `GPT6Sword` offsets: serial@36, strikes@40, value@72 (double), grade@80, effects@96,
  heated@104, broken@105. `ForgeSwordEffects`: charge@244, normalHits@248, feverUntil@236 (float,
  time based), feverDuration@324.
- Odds: `$xA::$PH(GPT6Sword, ForgeCampaign, bool fever)` returns a struct of 5 ints in per-mille:
  [break, damage, hold, success, great]. `$xA::$pH(int grade, ForgeCampaign, double value,
  bool fever)` gives the same by grade. The script checks the two agree; the game's opening phase
  returns fixed odds.
- Localization: `ForgeLocalization` has a static `Dictionary<lang, Dictionary<key, text>>`
  (vi has 902 entries, the others 774). Relics are `item.<id>.name/.description`. Dictionary
  entries are 24 bytes: hash, next, key@8, value@16.
- Sword position (`place`): 0 floor, 3 anvil, 4 rack (slot = `rack` + 1), 5 tribute table (offered,
  so no longer in hand). Other codes aren't pinned down. Over 4 minutes I saw 1 (usually with a
  pointer in `GPT6ForgeRoom.$oc`, probably "held") and 2 (brief, about a second). I never caught
  `heated = true`, so furnace vs hand isn't confirmed and the overlay shows "in hand" for anything
  other than 0/3/4/5. `place` isn't a `GPT6Sword` field; it only exists in `ForgeSavedSword`.
- Ghost merchant: `campaign.merchantOffers[{id, price, sold, grade, stock, purchases}]`, present
  when `merchantRound == round`. Ids seen: `sword`, `worldtree`, `ward` (Cracked Dragon Scale),
  `rewind` (Clockwork of Regret).
- The contract is 24 days (`contractDeadlineRound` = 24). `campaign.anonymousRunId` identifies a
  run (32 hex chars).
- Tribute: `ForgeCampaign.$gf()` is the base tribute for `round`; `$Gf()` is the actual amount due
  (after `tributeCredit` and the `lifecontract` relic's −30%; `contractInk` doesn't change it).
  Verified: `$Gf` on a simulated campaign for today equals `GPT6ForgeRoom.quota`. Tribute curve
  (balanceRevision 2): day 1 1800, 2 2100, 3 2600, 4 3350, 5 4350, 6 5700, 7 8700, 8 13200,
  9 20100, 10 29500, 12 65500, 14 140000, 16 290000, 18 534000, 20 824000, 22 1280000,
  24 2000000. Older community numbers are off. `$ef()` = 0.15 × tribute = relic shop reroll price
  (day 7: 1,305 G, matches the machine), `$pf()` = 1.5×, `$Pf()` = 2×. `nextTributeCredit` is the
  discount on the next tribute (`notice.quota_credit`). The overlay calls `$Gf` on a simulated
  campaign at round+1 with tributeCredit = nextTributeCredit; later days use tributeCredit = 0
  (future overpayment is unknown, so it's an upper bound). Checked live on day 7: 13200, 20100,
  29500, 44200, 65500, 96400, 140000, 204000, 290000, 413000.
- `ForgeEnhancementBalance`: baseValue@24 = 320, gradeMultiplier@32 = 1.5, maxGrade@36 = 299,
  openingQuota@40 = 1800.
- Relic shop machine `GPT6ForgeRoom.vending` (ForgeRelicVending): TextMesh `rerollText` shows
  "1,305 G" or the free-reroll text (`rework.free_reroll`), read with `TextMesh.get_text`. The
  campaign has `rerolls`, `paidRerolls`, `freeRerollUsedRound`.
- `GPT6ForgeRoom.ledgerText` (TextMesh) reads like "CỐNG PHẨM PHẢI NỘP\n2,600 G\n\nĐÃ CỐNG
  NẠP\n0 G" in Vietnamese; the first line is `ui.quota_caption`.
- Frenzy (measured twice): the 10th normal strike triggers it, `feverRemaining` starts around
  4.0 s and counts down; I landed 6 strikes (11..16) in that window. The overlay doesn't count the
  triggering strike.
- Two-Faced Altar (`altar`): the campaign has `forcedResultSerial` and `forcedNextResult` (-1 when
  unset). `ForgeCampaign.$UE(id, GPT6Sword, balance, bool)` returns a relic's dynamic description,
  but with a null sword it just says it can't be used right now, so today's face is still unknown.
- Relic ranking (`relicRank` payload, sent only when the relic set changes and the simulation is
  done): `{baseline: {"8"|"12"|"16": [5 per-mille]}, items: {id: {grade: [5]}}, owned: {id:
  {grade: [5]}}, shelfFull}`. `items` = simulated campaign plus a relic you don't have (added even
  when the shelf is full, which is then an estimate and flagged as such); `owned` = simulated
  campaign without a relic you have; `baseline` = unchanged simulated campaign. All numbers come
  from `$pH(grade, fake, baseValue × multiplier^grade, false)`. The cache key is the `relics` JSON,
  so permanent ticket changes (the `knife` item, tickets) that leave the relics alone don't
  trigger a recompute yet.
  It runs 12 simulated campaigns per Update; live it took about 2 seconds for 84 candidates.
  Candidates are every `item.<id>` in the table except merchant goods (`ward, rewind, sword,
  worldtree`), instant/consumable items (`knife, starshard, powder, candle, chalk, oil, steelcore,
  echodust, oblivion, contractink, delivery, creditshelf`), tickets
  (`ticketdamage/hold/success/great`), discontinued items (`ledger, safe`), anything whose
  Vietnamese description says it's used instantly / takes no relic slot / is discontinued, and
  conditional relics (`brace, repair, star, thread, cornerstone, insurance, phoenix, spine,
  eternalseed`), which are listed separately. Note that `mold` and `thread` share the same
  Vietnamese name in the table.

## Assumptions I haven't nailed down

- Pace assumes 3 fresh +0 swords per day (`pace.FRESH_SWORDS_PER_DAY`, value 320). It uses the
  safe-strike expectation because with the real odds the optimal plan for a +0 sword has an
  expectation around ×81 (+3: ×14.6, +6: ×2.5) driven by rare huge outcomes while the median is 0,
  so neither is useful for pace. The current estimate is cautious and tends to say "behind".
- Tribute after tomorrow can drop thanks to overpaying (tributeCredit); the overlay shows the
  upper bound.
- The planner treats a Frenzy as `fever_strikes` strikes at Frenzy odds right after 10 normal
  strikes (calibrated per player, default 7 from community guides).
- Reroll advice: "gold to spare" means wallet ≥ 10 × price. That's a guess; gold is also needed
  for the ghost merchant.
- Damage = −1 grade, great success = +2, value per grade × gradeMultiplier.
- From community guides: missing the tribute a third time ends the run; offered swords turn into
  gold; the relic shop charges 1 credit per sword (paid with +0 swords); Royal Change takes 30% of
  the overpayment off the next tribute (up to −30%).

## Simulating the rest of the run

The Simulation tab (`forgeseer/simulator/`) plays the remaining days many times. It starts from
the latest snapshot the overlay holds (live state, quota, schedule, odds table and multiplier from
`LiveSource`), or from the newest save when there's no live data. Each simulated day: 3 fresh +0
swords arrive (not on the current day), every sword is struck while the strategy says so (best
sword first, at most 30 decisions per sword per day, a Frenzy burst of `fever_strikes` strikes
counts as one), then the tribute is paid with the smallest sword that covers it alone, else the
biggest ones until it's covered. Not enough means a missed tribute; the third ends the run.
Outcomes follow the planner's model (break / −1 / hold / +1 / +2, value × multiplier per grade).

Strategies: `advisor` (planner decision per grade and charge, plus the tribute rules: never risk
the sword today's tribute rests on, push when one strike can close the gap), `conservative` (same,
but no normal strike with ≥10 % break), `aggressive` (the best sword keeps going while one strike
has EV > 1, ignoring the tribute lock), `safe_only` (only strikes that can't break, plus Frenzy).
The planner's choice doesn't depend on the value scale, so one DP relative to +0 gives the
decision table for every grade.

What's not from the game: tribute past the live schedule comes from the curve above (19, 21 and
23 are geometric means of their neighbours); without the live odds table a rough stand-in curve is
used (`assumed_odds`) and the tab says so; overpay credit, relic shop and merchant are ignored.
It runs up to 2,000 runs per strategy, interleaved, and stops after about 0.9 s on a worker
thread; with a seed it's deterministic. It never reads the RNG state.

Settings-window texts live in `locales/<code>.extra.json`, merged over `<code>.json` by
`i18n.catalog`; the key-set tests cover the merged catalogs.

## Poking at the game

I explore with throwaway Frida scripts kept outside the repo. Only call pure functions and
getters, and only on the main thread (inside the `Update` hook). If a campaign method might have
side effects, call it on a simulated campaign from `JsonUtility.FromJson`, never on the real one.
