import tomllib
from pathlib import Path

import pytest

from forgeseer import __version__
from forgeseer.update_check import (RELEASES_PAGE, UpdateChecker, UpdateInfo, check_for_update,
                                    is_newer, parse_version)


def test_version_constant_matches_pyproject():
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text("utf-8"))
    assert pyproject["project"]["version"] == __version__


@pytest.mark.parametrize("text, expected", [
    ("v1.2.0", (1, 2, 0)), ("1.10", (1, 10)), (" 2 ", (2,)), ("v1.2.0-beta", None), ("", None),
    (None, None),
])
def test_parse_version(text, expected):
    assert parse_version(text) == expected


def test_is_newer_compares_numerically():
    assert is_newer("v1.10.0", "1.9.9")
    assert is_newer("1.2", "1.1.9")
    assert not is_newer("1.1.1", "1.1.1")
    assert not is_newer("1.1", "1.1.0")
    assert not is_newer("garbage", "1.0.0")


def test_reports_newer_release():
    info = check_for_update(lambda: {"tag_name": "v1.2.0",
                                     "html_url": "https://github.com/x/y/releases/tag/v1.2.0"},
                            current="1.1.1")
    assert info == UpdateInfo("1.2.0", "https://github.com/x/y/releases/tag/v1.2.0")


def test_unexpected_url_falls_back_to_release_page():
    info = check_for_update(lambda: {"tag_name": "2.0.0", "html_url": "http://evil"}, "1.1.1")
    assert info.url == RELEASES_PAGE


@pytest.mark.parametrize("payload", [
    {"tag_name": "v1.1.1"}, {"tag_name": "v1.0.0"}, {"tag_name": "v9.0.0", "prerelease": True},
    {"tag_name": "v9.0.0", "draft": True}, {"message": "API rate limit exceeded"}, [], None,
])
def test_no_notice_when_not_newer_or_odd_payload(payload):
    assert check_for_update(lambda: payload, current="1.1.1") is None


def test_fetch_errors_are_silent():
    def boom():
        raise OSError("offline")
    assert check_for_update(boom, current="1.1.1") is None


def test_checker_runs_in_background():
    checker = UpdateChecker(lambda: {"tag_name": "v3.0.0"}, current="1.1.1").start()
    assert checker.wait(2)
    assert checker.done and checker.result.version == "3.0.0"
