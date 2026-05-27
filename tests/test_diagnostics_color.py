from __future__ import annotations

from unittest.mock import patch
import unittest

from oroboros.diagnostics.color import should_use_color


class _FakeStream:
    def __init__(self, *, is_tty: bool) -> None:
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty


class DiagnosticsColorTest(unittest.TestCase):
    def test_should_use_color_respects_no_color_for_tty_streams(self) -> None:
        with patch.dict("os.environ", {"NO_COLOR": "1", "TERM": "xterm-256color"}, clear=True):
            self.assertFalse(should_use_color(_FakeStream(is_tty=True)))

    def test_should_use_color_respects_clicolor_force_for_non_tty_streams(self) -> None:
        with patch.dict("os.environ", {"CLICOLOR_FORCE": "1", "TERM": "dumb"}, clear=True):
            self.assertTrue(should_use_color(_FakeStream(is_tty=False)))

    def test_should_use_color_disables_plain_non_tty_streams_by_default(self) -> None:
        with patch.dict("os.environ", {"TERM": "xterm-256color"}, clear=True):
            self.assertFalse(should_use_color(_FakeStream(is_tty=False)))

    def test_should_use_color_disables_dumb_term_for_tty_streams(self) -> None:
        with patch.dict("os.environ", {"TERM": "dumb"}, clear=True):
            self.assertFalse(should_use_color(_FakeStream(is_tty=True)))


if __name__ == "__main__":
    unittest.main()
