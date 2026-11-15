import pytest

from forgeseer.i18n import set_language


@pytest.fixture(autouse=True)
def vietnamese_ui():
    """Most tests check the exact Vietnamese wording, so pin the overlay language to vi."""
    set_language("vi")
    yield
    set_language("vi")
