"""Regression tests for the native desktop status widget geometry/state."""

import json
from pathlib import Path

from lanhu_mcp.gui.floating import (
    clamp_floating_position,
    load_floating_position,
    save_floating_position,
)


def test_floating_position_round_trip_preserves_other_preferences(tmp_path: Path) -> None:
    preferences = tmp_path / "window_preferences.json"
    preferences.write_text(json.dumps({"close_behavior": "window"}), encoding="utf-8")

    save_floating_position(123, 456, preferences)

    assert load_floating_position(preferences) == (123, 456)
    assert json.loads(preferences.read_text(encoding="utf-8")) == {
        "close_behavior": "window",
        "floating_position": {"x": 123, "y": 456},
    }


def test_floating_position_is_clamped_to_virtual_desktop() -> None:
    assert clamp_floating_position(
        -100,
        9999,
        screen_left=-1920,
        screen_top=-200,
        screen_width=3840,
        screen_height=2160,
        width=68,
        height=68,
    ) == (-100, 1892)
