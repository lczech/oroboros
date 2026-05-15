from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import unittest

from oroboros.__main__ import main


REPO_ROOT = Path(__file__).resolve().parents[1]


class MainTest(unittest.TestCase):
    def test_find_headers_subcommand_lists_included_headers(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "find-headers",
                    "--header-dir",
                    str(REPO_ROOT / "example" / "inc"),
                    "--header-file",
                    str(REPO_ROOT / "example" / "inc" / "cosmos" / "cosmos.hpp"),
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            stdout.getvalue().splitlines(),
            [
                f"cosmos/cosmos.hpp\t{(REPO_ROOT / 'example' / 'inc' / 'cosmos' / 'cosmos.hpp').resolve()}",
                f"cosmos/types.hpp\t{(REPO_ROOT / 'example' / 'inc' / 'cosmos' / 'types.hpp').resolve()}",
                f"cosmos/functions.hpp\t{(REPO_ROOT / 'example' / 'inc' / 'cosmos' / 'functions.hpp').resolve()}",
                f"cosmos/objects.hpp\t{(REPO_ROOT / 'example' / 'inc' / 'cosmos' / 'objects.hpp').resolve()}",
            ],
        )
