from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from oroboros.headers import HeaderFile, HeaderSelection, discover_headers, find_all_headers, find_included_headers


REPO_ROOT = Path(__file__).resolve().parents[1]


class FindHeadersTest(unittest.TestCase):
    def test_find_all_headers_recursively(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            base_dir = Path(temp_dir_name) / "include"
            nested_dir = base_dir / "demo" / "nested"
            nested_dir.mkdir(parents=True)

            (base_dir / "demo" / "alpha.hpp").write_text("", encoding="utf-8")
            (nested_dir / "beta.hxx").write_text("", encoding="utf-8")
            (base_dir / "demo" / "gamma.txt").write_text("", encoding="utf-8")

            header_files = find_all_headers(base_dir)

        self.assertEqual(
            header_files,
            [
                HeaderFile(
                    full_path=(base_dir / "demo" / "alpha.hpp").resolve(),
                    relative_path=Path("demo/alpha.hpp"),
                ),
                HeaderFile(
                    full_path=(base_dir / "demo" / "nested" / "beta.hxx").resolve(),
                    relative_path=Path("demo/nested/beta.hxx"),
                ),
            ],
        )

    def test_find_included_headers_lists_root_header_before_dependencies(self) -> None:
        base_dir = REPO_ROOT / "example" / "inc"
        root_header = base_dir / "cosmos" / "cosmos.hpp"

        header_files = find_included_headers(base_dir, root_header)

        self.assertEqual(
            header_files,
            [
                HeaderFile(
                    full_path=(base_dir / "cosmos" / "cosmos.hpp").resolve(),
                    relative_path=Path("cosmos/cosmos.hpp"),
                ),
                HeaderFile(
                    full_path=(base_dir / "cosmos" / "types.hpp").resolve(),
                    relative_path=Path("cosmos/types.hpp"),
                ),
                HeaderFile(
                    full_path=(base_dir / "cosmos" / "functions.hpp").resolve(),
                    relative_path=Path("cosmos/functions.hpp"),
                ),
                HeaderFile(
                    full_path=(base_dir / "cosmos" / "objects.hpp").resolve(),
                    relative_path=Path("cosmos/objects.hpp"),
                ),
            ],
        )

    def test_find_included_headers_accepts_root_header_relative_to_base_dir(self) -> None:
        base_dir = REPO_ROOT / "example" / "inc"

        header_files = find_included_headers(base_dir, "cosmos/cosmos.hpp")

        self.assertEqual(
            header_files[0],
            HeaderFile(
                full_path=(base_dir / "cosmos" / "cosmos.hpp").resolve(),
                relative_path=Path("cosmos/cosmos.hpp"),
            ),
        )

    def test_find_included_headers_skips_external_root_and_follows_local_dependencies(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            base_dir = temp_dir / "include"
            project_dir = base_dir / "demo"
            project_dir.mkdir(parents=True)

            root_header = temp_dir / "root.hpp"
            root_header.write_text(
                '#include "demo/feature.hpp"\n#include <vector>\n',
                encoding="utf-8",
            )
            (project_dir / "feature.hpp").write_text(
                '#include "detail/helper.hpp"\n',
                encoding="utf-8",
            )
            detail_dir = project_dir / "detail"
            detail_dir.mkdir()
            (detail_dir / "helper.hpp").write_text("", encoding="utf-8")

            header_files = find_included_headers(base_dir, root_header)

            self.assertEqual(
                header_files,
                [
                HeaderFile(
                    full_path=(project_dir / "feature.hpp").resolve(),
                    relative_path=Path("demo/feature.hpp"),
                ),
                HeaderFile(
                    full_path=(detail_dir / "helper.hpp").resolve(),
                    relative_path=Path("demo/detail/helper.hpp"),
                ),
                ],
            )

    def test_discover_headers_builds_known_and_active_selection(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            base_dir = Path(temp_dir_name) / "include"
            demo_dir = base_dir / "demo"
            demo_dir.mkdir(parents=True)
            (demo_dir / "api.hpp").write_text('#include "detail.hpp"\n', encoding="utf-8")
            (demo_dir / "detail.hpp").write_text("", encoding="utf-8")

            selection = discover_headers(base_dir, umbrella_header="demo/api.hpp")

            self.assertIsInstance(selection, HeaderSelection)
            self.assertEqual(
                [header.relative_path.as_posix() for header in selection.known_headers],
                ["demo/api.hpp", "demo/detail.hpp"],
            )
            self.assertEqual(
                [header.relative_path.as_posix() for header in selection.active_headers],
                ["demo/api.hpp", "demo/detail.hpp"],
            )


if __name__ == "__main__":
    unittest.main()
