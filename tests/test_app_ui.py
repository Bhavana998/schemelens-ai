from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def test_streamlit_app_initial_load():
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    assert not at.exception
    assert len(at.sidebar.radio) > 0


def test_streamlit_app_navigation_tabs():
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    radio = at.sidebar.radio[0]
    expected_modes = ["Review Drafts", "Ingest & Extract", "Approved Schemes", "Audit Trail & Evaluation"]

    for mode in expected_modes:
        radio.set_value(mode)
        at.run()
        assert not at.exception, f"Navigation to '{mode}' produced an unexpected exception."


def test_streamlit_app_ingest_sample_download_buttons():
    at = AppTest.from_file(APP_PATH, default_timeout=15)
    at.run()
    radio = at.sidebar.radio[0]
    radio.set_value("Ingest & Extract")
    at.run()
    assert not at.exception
    # Ensure download buttons or buttons are rendered
    assert len(at.button) > 0
