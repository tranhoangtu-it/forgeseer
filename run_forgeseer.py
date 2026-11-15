"""Điểm vào khi đóng gói ForgeSeer.exe bằng PyInstaller (tương đương `python -m forgeseer`)."""
from forgeseer.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
