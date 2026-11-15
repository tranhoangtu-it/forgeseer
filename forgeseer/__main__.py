"""ForgeSeer: python -m forgeseer [--once] [--no-live] [--lang vi] [--x 20 --y 20]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config, load_position
from .formatter import format_state
from .i18n import SUPPORTED, choose_language, get_language, set_language, t, windows_ui_language
from .relic_names import BUNDLED_NAMES_FILE, load_relic_names, load_relic_texts
from .save_reader import DEFAULT_SAVE_DIR, SaveReadError, find_run_save, load_run_state

DEFAULT_POLL_MS = 500
DEFAULT_POSITION = (20, 20)


def _print_once(save_dir: Path, names: dict[str, str]) -> int:
    """In trạng thái hiện tại ra console (không mở cửa sổ) - tiện để kiểm tra nhanh."""
    path = find_run_save(save_dir)
    if path is None:
        sys.stderr.write(t("status.no_save", folder=save_dir) + "\n")
        return 1
    try:
        state = load_run_state(path)
    except SaveReadError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write(f"[{path.name}]\n")
    sys.stdout.write("\n".join(text for text, _ in format_state(state, names)) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forgeseer", description=__doc__)
    parser.add_argument("--save-dir", type=Path, default=DEFAULT_SAVE_DIR,
                        help="ForgeTax Save folder")
    parser.add_argument("--x", type=int, help="Overlay x position in px (default: last saved)")
    parser.add_argument("--y", type=int, help="Overlay y position in px (default: last saved)")
    parser.add_argument("--relic-names", type=Path, default=BUNDLED_NAMES_FILE,
                        help="JSON file mapping relic id -> name (fallback names)")
    parser.add_argument("--poll-ms", type=int, default=DEFAULT_POLL_MS,
                        help="How often to check the save file (ms)")
    parser.add_argument("--no-live", action="store_true",
                        help="Do not attach to the game, read the save file only")
    parser.add_argument("--once", action="store_true",
                        help="Print the current state to the console and exit")
    parser.add_argument("--lang", choices=SUPPORTED,
                        help="Overlay language (default: follow the game, then Windows)")
    args = parser.parse_args(argv)

    # --once không gắn vào game nên chỉ có --lang hoặc ngôn ngữ Windows.
    set_language(choose_language(args.lang, load_config().get("game_lang"), windows_ui_language()))
    # Tên tự dịch làm nền, đè bằng tên chính thức đã cache từ game (nếu có).
    names = {**load_relic_names(args.relic_names),
             **{k: text.name for k, text in load_relic_texts(lang=get_language()).items()}}
    if args.once:
        return _print_once(args.save_dir, names)

    from .overlay import run_overlay  # import trễ: --once không cần tkinter/Win32

    saved_x, saved_y = load_position() or DEFAULT_POSITION
    x = saved_x if args.x is None else args.x
    y = saved_y if args.y is None else args.y
    run_overlay(args.save_dir, max(args.poll_ms, 100), x, y, names, use_live=not args.no_live,
                lang=args.lang)
    return 0


if __name__ == "__main__":
    sys.exit(main())
