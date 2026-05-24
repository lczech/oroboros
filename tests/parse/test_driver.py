from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from oroboros.headers import HeaderFile, HeaderSelection
from oroboros.parse import ParserConfig, parse_header_selection
from oroboros.parse.build_model import BuildResult
from oroboros.parse.clang_driver import build_clang_arguments, build_synthetic_include_source
from oroboros.parse.toolchain import (
    _parse_system_include_dirs,
    _resolve_parser_config_toolchain,
    detect_compiler_toolchain,
)


class ParseDriverTest(unittest.TestCase):
    def test_build_synthetic_include_source_includes_headers_in_order(self) -> None:
        headers = [
            Path("/tmp/project/a.hpp"),
            Path("/tmp/project/b.hpp"),
        ]

        source = build_synthetic_include_source(headers)

        self.assertEqual(
            source,
            '#include "/tmp/project/a.hpp"\n#include "/tmp/project/b.hpp"\n',
        )

    def test_build_clang_arguments_translates_parser_config(self) -> None:
        config = ParserConfig(
            include_dirs=[Path("/tmp/inc"), Path("/tmp/vendor")],
            system_include_dirs=[Path("/tmp/sys"), Path("/tmp/sys-cxx")],
            defines=["FOO=1", "BAR"],
            undefines=["BAZ"],
            extra_args=["-Wall"],
            language="c++",
            cxx_standard="c++20",
            resource_dir=Path("/tmp/clang-resource"),
        )

        arguments = build_clang_arguments(config)

        self.assertEqual(
            arguments,
            [
                "-xc++",
                "-fparse-all-comments",
                "-std=c++20",
                "-resource-dir=/tmp/clang-resource",
                "-I/tmp/inc",
                "-I/tmp/vendor",
                "-isystem",
                "/tmp/sys",
                "-isystem",
                "/tmp/sys-cxx",
                "-DFOO=1",
                "-DBAR",
                "-UBAZ",
                "-Wall",
            ],
        )

    def test_resolve_parser_config_toolchain_only_fills_missing_fields(self) -> None:
        config = ParserConfig(
            include_dirs=[Path("/tmp/project-inc")],
            auto_detect_toolchain=True,
            toolchain_compiler="clang++",
            system_include_dirs=[Path("/tmp/already-set")],
            resource_dir=Path("/tmp/already-resource"),
        )

        with patch("oroboros.parse.toolchain.detect_compiler_toolchain") as detect_toolchain:
            updated = _resolve_parser_config_toolchain(config)

        detect_toolchain.assert_not_called()
        self.assertEqual(updated.include_dirs, [Path("/tmp/project-inc")])
        self.assertEqual(updated.system_include_dirs, [Path("/tmp/already-set")])
        self.assertEqual(updated.resource_dir, Path("/tmp/already-resource"))

    def test_resolve_parser_config_toolchain_detects_missing_fields_when_enabled(self) -> None:
        config = ParserConfig(
            include_dirs=[Path("/tmp/project-inc")],
            auto_detect_toolchain=True,
            toolchain_compiler="clang++",
            language="c++",
        )

        with (
            patch("oroboros.parse.toolchain._detect_resource_dir", return_value=Path("/tmp/detected-resource")) as detect_resource,
            patch(
                "oroboros.parse.toolchain._detect_system_include_dirs",
                return_value=[Path("/tmp/detected-system")],
            ) as detect_system_includes,
        ):
            updated = _resolve_parser_config_toolchain(config)

        detect_resource.assert_called_once_with("clang++")
        detect_system_includes.assert_called_once_with("clang++", language="c++")
        self.assertEqual(updated.include_dirs, [Path("/tmp/project-inc")])
        self.assertEqual(updated.resource_dir, Path("/tmp/detected-resource"))
        self.assertEqual(updated.system_include_dirs, [Path("/tmp/detected-system")])

    def test_resolve_parser_config_toolchain_only_probes_missing_resource_dir(self) -> None:
        config = ParserConfig(
            auto_detect_toolchain=True,
            toolchain_compiler="clang++",
            language="c++",
            system_include_dirs=[Path("/tmp/already-set")],
        )

        with (
            patch("oroboros.parse.toolchain._detect_resource_dir", return_value=Path("/tmp/detected-resource")) as detect_resource,
            patch("oroboros.parse.toolchain._detect_system_include_dirs") as detect_system_includes,
        ):
            updated = _resolve_parser_config_toolchain(config)

        detect_resource.assert_called_once_with("clang++")
        detect_system_includes.assert_not_called()
        self.assertEqual(updated.resource_dir, Path("/tmp/detected-resource"))
        self.assertEqual(updated.system_include_dirs, [Path("/tmp/already-set")])

    def test_resolve_parser_config_toolchain_only_probes_missing_system_include_dirs(self) -> None:
        config = ParserConfig(
            auto_detect_toolchain=True,
            toolchain_compiler="clang++",
            language="c++",
            resource_dir=Path("/tmp/already-resource"),
        )

        with (
            patch("oroboros.parse.toolchain._detect_resource_dir") as detect_resource,
            patch(
                "oroboros.parse.toolchain._detect_system_include_dirs",
                return_value=[Path("/tmp/detected-system")],
            ) as detect_system_includes,
        ):
            updated = _resolve_parser_config_toolchain(config)

        detect_resource.assert_not_called()
        detect_system_includes.assert_called_once_with("clang++", language="c++")
        self.assertEqual(updated.resource_dir, Path("/tmp/already-resource"))
        self.assertEqual(updated.system_include_dirs, [Path("/tmp/detected-system")])

    def test_parse_system_include_dirs_extracts_verbose_search_list(self) -> None:
        verbose_output = """
some prelude
#include <...> search starts here:
 /usr/include/c++/14
 /usr/include/x86_64-linux-gnu/c++/14
 /usr/lib/llvm-17/lib/clang/17/include
 /usr/local/include
 /usr/include/x86_64-linux-gnu
 /usr/include
End of search list.
some trailer
"""

        include_dirs = _parse_system_include_dirs(verbose_output)

        self.assertEqual(
            include_dirs,
            [
                Path("/usr/include/c++/14"),
                Path("/usr/include/x86_64-linux-gnu/c++/14"),
                Path("/usr/lib/llvm-17/lib/clang/17/include"),
                Path("/usr/local/include"),
                Path("/usr/include/x86_64-linux-gnu"),
                Path("/usr/include"),
            ],
        )

    def test_detect_compiler_toolchain_reports_missing_compiler_cleanly(self) -> None:
        with patch(
            "oroboros.parse.toolchain._detect_resource_dir",
            side_effect=RuntimeError("compiler was not found"),
        ):
            with self.assertRaisesRegex(RuntimeError, "was not found"):
                detect_compiler_toolchain("missing-clang")

    def test_detect_compiler_toolchain_reports_probe_failure_with_guidance(self) -> None:
        with (
            patch("oroboros.parse.toolchain._detect_resource_dir", return_value=Path("/tmp/resource")),
            patch(
                "oroboros.parse.toolchain._detect_system_include_dirs",
                side_effect=RuntimeError("First compiler message: probe failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "First compiler message: probe failed"):
                detect_compiler_toolchain("clang++")

    def test_parse_header_selection_returns_empty_validated_module_for_empty_header_list(self) -> None:
        result = parse_header_selection(HeaderSelection(header_files=[]), ParserConfig())

        self.assertEqual(result.headers, [])
        self.assertEqual(result.module.declarations.namespaces, [])
        self.assertEqual(result.module.cpp.header_files, [])

    def test_parse_header_selection_wires_driver_and_builder_results(self) -> None:
        translation_unit = object()
        diagnostics = [SimpleNamespace(severity="warning")]
        driver_result = SimpleNamespace(translation_unit=translation_unit, diagnostics=diagnostics)
        built_module = SimpleNamespace(
            validate_tree=lambda: None,
            validate_semantics=lambda: None,
        )
        build_result = BuildResult(
            module=built_module,
            semantic_warnings=[],
            skipped_kind_counts={"TYPEDEF_DECL": 2},
        )

        with (
            patch("oroboros.parse.api.parse_with_clang", return_value=driver_result) as parse_tu,
            patch("oroboros.parse.api.build_module_from_clang", return_value=build_result) as build_module,
        ):
            result = parse_header_selection(
                HeaderSelection(
                    header_files=[
                        HeaderFile(
                            full_path=Path("/tmp/project/demo.hpp"),
                            relative_path=Path("demo.hpp"),
                        )
                    ]
                ),
                ParserConfig(),
            )

        parse_tu.assert_called_once()
        build_module.assert_called_once_with(
            translation_unit,
            [Path("/tmp/project/demo.hpp").resolve()],
            unittest.mock.ANY,
            known_project_headers=[Path("/tmp/project/demo.hpp").resolve()],
        )
        self.assertIs(result.module, built_module)
        self.assertEqual(result.diagnostics, diagnostics)
        self.assertEqual(result.skipped_kind_counts, {"TYPEDEF_DECL": 2})
        self.assertEqual(
            result.warnings,
            ["Skipped unsupported libclang cursor kinds: TYPEDEF_DECL (2)"],
        )
        self.assertEqual(result.headers, [Path("/tmp/project/demo.hpp").resolve()])

    def test_parse_header_selection_passes_explicit_known_project_headers_to_builder(self) -> None:
        translation_unit = object()
        diagnostics = [SimpleNamespace(severity="warning")]
        driver_result = SimpleNamespace(translation_unit=translation_unit, diagnostics=diagnostics)
        built_module = SimpleNamespace(
            validate_tree=lambda: None,
            validate_semantics=lambda: None,
        )
        build_result = BuildResult(
            module=built_module,
            semantic_warnings=[],
            skipped_kind_counts={},
        )
        active_header = Path("/tmp/project/api.hpp")
        inactive_header = Path("/tmp/project/detail.hpp")

        with (
            patch("oroboros.parse.api.parse_with_clang", return_value=driver_result),
            patch("oroboros.parse.api.build_module_from_clang", return_value=build_result) as build_module,
        ):
            parse_header_selection(
                HeaderSelection(
                    header_files=[
                        HeaderFile(full_path=active_header, relative_path=Path("api.hpp")),
                        HeaderFile(full_path=inactive_header, relative_path=Path("detail.hpp"), active=False),
                    ]
                ),
                ParserConfig(),
            )

        build_module.assert_called_once_with(
            translation_unit,
            [active_header.resolve()],
            unittest.mock.ANY,
            known_project_headers=[active_header.resolve(), inactive_header.resolve()],
        )
