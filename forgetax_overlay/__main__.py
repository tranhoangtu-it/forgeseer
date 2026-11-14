"""Điểm vào: ``python -m forgetax_overlay [--once] [--x 20 --y 20]``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_position
from .formatter import format_state
from .relic_names import BUNDLED_NAMES_FILE, load_relic_names, load_relic_texts
from .save_reader import DEFAULT_SAVE_DIR, SaveReadError, find_run_save, load_run_state

DEFAULT_POLL_MS = 500
DEFAULT_POSITION = (20, 20)


def _print_once(save_dir: Path, names: dict[str, str]) -> int:
    """In trạng thái hiện tại ra console (không mở cửa sổ) - tiện để kiểm tra nhanh."""
    path = find_run_save(save_dir)
    if path is None:
        sys.stderr.write(f"Không thấy file save trong {save_dir}\n")
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
    parser = argparse.ArgumentParser(prog="forgetax_overlay", description=__doc__)
    parser.add_argument("--save-dir", type=Path, default=DEFAULT_SAVE_DIR,
                        help="Thư mục Save của ForgeTax")
    parser.add_argument("--x", type=int, help="Vị trí ngang overlay (px); mặc định: vị trí đã lưu")
    parser.add_argument("--y", type=int, help="Vị trí dọc overlay (px); mặc định: vị trí đã lưu")
    parser.add_argument("--relic-names", type=Path, default=BUNDLED_NAMES_FILE,
                        help="File JSON dịch id relic -> tên")
    parser.add_argument("--poll-ms", type=int, default=DEFAULT_POLL_MS,
                        help="Chu kỳ kiểm tra file save (ms)")
    parser.add_argument("--no-live", action="store_true",
                        help="Không đọc trực tiếp từ game (chỉ dùng file save)")
    parser.add_argument("--once", action="store_true",
                        help="Chỉ in trạng thái ra console rồi thoát")
    args = parser.parse_args(argv)

    # Tên tự dịch làm nền, đè bằng tên chính thức đã cache từ game (nếu có).
    names = {**load_relic_names(args.relic_names),
             **{k: t.name for k, t in load_relic_texts().items()}}
    if args.once:
        return _print_once(args.save_dir, names)

    from .overlay import run_overlay  # import trễ: --once không cần tkinter/Win32

    saved_x, saved_y = load_position() or DEFAULT_POSITION
    x = saved_x if args.x is None else args.x
    y = saved_y if args.y is None else args.y
    run_overlay(args.save_dir, max(args.poll_ms, 100), x, y, names, use_live=not args.no_live)
    return 0


if __name__ == "__main__":
    sys.exit(main())
