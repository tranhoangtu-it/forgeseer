## ForgeSeer 1.2.0

A bigger one.

**New look.** The panels are drawn properly now: rounded dark cards, a small icon per section,
a five-colour bar under each sword's odds (break, damage, no change, success, great), bars for
today's tribute and the contract pace, and the strike / stop call as a coloured pill.

**Alerts.** When a Frenzy starts the to-do panel flashes and Windows plays a short sound. You also
get one flash when today's tribute can't be covered, and one when a ★ relic is for sale.
Sound can be turned off with `"sound_alerts": false` under `settings` in config.json.

**Simulation tab.** In the settings window (F6), "Run simulation" replays the rest of your run a
couple of thousand times with the game's own odds and tribute schedule, and compares four ways of
playing. You see the chance of still being alive after each day and which approach goes furthest.
It only works with probabilities; the game's RNG is never read.

**Stats tab.** Runs played, wins, furthest and average day, which day runs usually end on, highest
grade per run.

**Update notice.** ForgeSeer checks GitHub once at start-up and tells you when there's a newer
version. You can switch that off in the settings.

**Mixed-DPI setups.** Panels stay sharp and correctly sized when you drag them to a monitor with a
different scaling level.

---

**Tiếng Việt:** giao diện mới (thanh màu tỉ lệ, thanh cống, biểu tượng), cảnh báo khi Xuất Thần /
thiếu cống / có món ★, tab Mô phỏng (chạy thử hàng nghìn ván với tỉ lệ thật để so cách chơi),
tab Thống kê, báo khi có bản mới, và hiển thị đúng khi dùng nhiều màn hình khác scaling.
