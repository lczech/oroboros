from __future__ import annotations

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from oroboros.diagnostics import DiagnosticReport
from oroboros.headers import HeaderFile, HeaderSelection, select_active_headers
from oroboros.headers.select_headers import (
    parse_activation_header,
    print_update_report,
    update_activation_header,
    write_activation_header,
)


class SelectHeadersTest(unittest.TestCase):
    def test_parse_activation_header_marks_active_and_inactive_headers(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            activation_header = temp_dir / "activated_headers.hpp"
            activation_header.write_text(
                "\n".join(
                    [
                        "#pragma once",
                        '#include <demo/a.hpp>',
                        '// #include <demo/b.hpp>',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            header_files = [
                HeaderFile(full_path=temp_dir / "a.hpp", relative_path=Path("demo/a.hpp")),
                HeaderFile(full_path=temp_dir / "b.hpp", relative_path=Path("demo/b.hpp")),
            ]

            selected_headers = parse_activation_header(header_files, activation_header)

        self.assertEqual(
            selected_headers,
            [
                HeaderFile(
                    full_path=header_files[0].full_path,
                    relative_path=Path("demo/a.hpp"),
                    active=True,
                ),
                HeaderFile(
                    full_path=header_files[1].full_path,
                    relative_path=Path("demo/b.hpp"),
                    active=False,
                ),
            ],
        )

    def test_parse_activation_header_warns_about_missing_headers(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            activation_header = temp_dir / "activated_headers.hpp"
            activation_header.write_text(
                '#include <demo/a.hpp>\n',
                encoding="utf-8",
            )

            header_files = [
                HeaderFile(full_path=temp_dir / "a.hpp", relative_path=Path("demo/a.hpp")),
                HeaderFile(full_path=temp_dir / "b.hpp", relative_path=Path("demo/b.hpp")),
            ]
            report = DiagnosticReport()

            selected_headers = parse_activation_header(
                header_files,
                activation_header,
                report=report,
            )

        self.assertEqual(len(report.warnings), 1)
        self.assertIn("demo/b.hpp", report.warnings[0].message)

    def test_select_active_headers_returns_structured_selection(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            activation_header = temp_dir / "active.hpp"
            activation_header.write_text(
                '#include <demo/a.hpp>\n// #include <demo/b.hpp>\n',
                encoding="utf-8",
            )
            selection = HeaderSelection(
                header_files=[
                    HeaderFile(full_path=temp_dir / "a.hpp", relative_path=Path("demo/a.hpp")),
                    HeaderFile(full_path=temp_dir / "b.hpp", relative_path=Path("demo/b.hpp")),
                ]
            )

            selected = select_active_headers(selection, activation_header)

        self.assertEqual(
            [(header.relative_path.as_posix(), header.active) for header in selected.known_headers],
            [("demo/a.hpp", True), ("demo/b.hpp", False)],
        )
        self.assertEqual(
            [header.relative_path.as_posix() for header in selected.active_headers],
            ["demo/a.hpp"],
        )

    def test_write_activation_header_supports_sections(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            target_file = temp_dir / "activated_headers.hpp"
            header_files = [
                HeaderFile(
                    full_path=temp_dir / "name.hpp",
                    relative_path=Path("genesis/placement/pquery/name.hpp"),
                    active=False,
                ),
                HeaderFile(
                    full_path=temp_dir / "placement.hpp",
                    relative_path=Path("genesis/placement/pquery/placement.hpp"),
                    active=False,
                ),
                HeaderFile(
                    full_path=temp_dir / "edge_color.hpp",
                    relative_path=Path("genesis/placement/format/edge_color.hpp"),
                    active=True,
                ),
            ]

            write_activation_header(header_files, target_file, with_sections=True)

            written_text = target_file.read_text(encoding="utf-8")

        self.assertEqual(
            written_text,
            "\n".join(
                [
                    "#pragma once",
                    "",
                    "// ---------------------------------------------------------------------",
                    "//   genesis/placement/pquery",
                    "// ---------------------------------------------------------------------",
                    "",
                    "// #include <genesis/placement/pquery/name.hpp>",
                    "// #include <genesis/placement/pquery/placement.hpp>",
                    "",
                    "// ---------------------------------------------------------------------",
                    "//   genesis/placement/format",
                    "// ---------------------------------------------------------------------",
                    "",
                    "#include <genesis/placement/format/edge_color.hpp>",
                    "",
                ]
            ),
        )

    def test_update_activation_header_preserves_existing_choices_and_reports_changes(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            target_file = temp_dir / "activated_headers.hpp"
            target_file.write_text(
                "\n".join(
                    [
                        "#pragma once",
                        "",
                        "#include <demo/a.hpp>",
                        "// #include <demo/b.hpp>",
                        "#include <demo/old.hpp>",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            header_files = [
                HeaderFile(full_path=temp_dir / "a.hpp", relative_path=Path("demo/a.hpp")),
                HeaderFile(full_path=temp_dir / "b.hpp", relative_path=Path("demo/b.hpp")),
                HeaderFile(full_path=temp_dir / "c.hpp", relative_path=Path("demo/c.hpp")),
            ]

            update_result = update_activation_header(
                header_files,
                target_file,
                default_active=False,
            )

            updated_text = target_file.read_text(encoding="utf-8")

        self.assertEqual(
            update_result.header_files,
            [
                HeaderFile(full_path=temp_dir / "a.hpp", relative_path=Path("demo/a.hpp"), active=True),
                HeaderFile(full_path=temp_dir / "b.hpp", relative_path=Path("demo/b.hpp"), active=False),
                HeaderFile(full_path=temp_dir / "c.hpp", relative_path=Path("demo/c.hpp"), active=False),
            ],
        )
        self.assertEqual(update_result.added_headers, [Path("demo/c.hpp")])
        self.assertEqual(update_result.removed_headers, [Path("demo/old.hpp")])
        self.assertFalse(update_result.created_file)
        self.assertTrue(update_result.updated_file)
        self.assertEqual(
            updated_text,
            "\n".join(
                [
                    "#pragma once",
                    "",
                    "#include <demo/a.hpp>",
                    "// #include <demo/b.hpp>",
                    "// #include <demo/c.hpp>",
                    "",
                ]
            ),
        )

    def test_update_activation_header_creates_file_for_new_inventory(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            target_file = temp_dir / "activated_headers.hpp"
            header_files = [
                HeaderFile(full_path=temp_dir / "a.hpp", relative_path=Path("demo/a.hpp")),
                HeaderFile(full_path=temp_dir / "b.hpp", relative_path=Path("demo/b.hpp")),
            ]

            update_result = update_activation_header(
                header_files,
                target_file,
                default_active=False,
            )

            created_text = target_file.read_text(encoding="utf-8")
            target_file_exists = target_file.exists()

        self.assertTrue(update_result.created_file)
        self.assertTrue(update_result.updated_file)
        self.assertEqual(
            update_result.added_headers,
            [Path("demo/a.hpp"), Path("demo/b.hpp")],
        )
        self.assertEqual(update_result.removed_headers, [])
        self.assertTrue(target_file_exists)
        self.assertEqual(
            created_text,
            "\n".join(
                [
                    "#pragma once",
                    "",
                    "// #include <demo/a.hpp>",
                    "// #include <demo/b.hpp>",
                    "",
                ]
            ),
        )

    def test_update_activation_header_skips_rewrite_when_content_is_unchanged(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            target_file = temp_dir / "activated_headers.hpp"
            target_file.write_text(
                "\n".join(
                    [
                        "#pragma once",
                        "",
                        "#include <demo/a.hpp>",
                        "// #include <demo/b.hpp>",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            original_mtime_ns = target_file.stat().st_mtime_ns
            header_files = [
                HeaderFile(full_path=temp_dir / "a.hpp", relative_path=Path("demo/a.hpp")),
                HeaderFile(full_path=temp_dir / "b.hpp", relative_path=Path("demo/b.hpp")),
            ]

            update_result = update_activation_header(
                header_files,
                target_file,
                default_active=False,
            )

            updated_mtime_ns = target_file.stat().st_mtime_ns

        self.assertFalse(update_result.created_file)
        self.assertFalse(update_result.updated_file)
        self.assertEqual(original_mtime_ns, updated_mtime_ns)

    def test_print_update_report_formats_added_and_removed_headers(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            target_file = temp_dir / "activated_headers.hpp"
            header_files = [
                HeaderFile(full_path=temp_dir / "a.hpp", relative_path=Path("demo/a.hpp"), active=False),
            ]
            update_result = update_activation_header(
                header_files,
                target_file,
                default_active=False,
            )

            output = StringIO()
            print_update_report(update_result, stream=output)

        report_text = output.getvalue()
        self.assertIn("Activation header:", report_text)
        self.assertIn("Added headers:", report_text)
        self.assertIn("demo/a.hpp", report_text)

    def test_print_update_report_optionally_renders_ansi_color(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            target_file = temp_dir / "activated_headers.hpp"
            update_result = update_activation_header(
                [HeaderFile(full_path=temp_dir / "a.hpp", relative_path=Path("demo/a.hpp"), active=False)],
                target_file,
                default_active=False,
            )

            output = StringIO()
            print_update_report(update_result, stream=output, color=True)

        report_text = output.getvalue()
        self.assertIn("\033[", report_text)
        self.assertIn("Activation header:", report_text)
