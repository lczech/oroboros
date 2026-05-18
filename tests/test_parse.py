from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from oroboros.model import CppClass, CppFunction, CppMethod, CppNamespace, SourceLocation
from oroboros.parse import ParserConfig, parse_headers
from oroboros.parse.decls import build_module_from_translation_unit
from oroboros.parse.driver import build_clang_arguments, build_synthetic_translation_unit_source
from oroboros.parse.toolchain import (
    _parse_system_include_dirs,
    _resolve_parser_config_toolchain,
    detect_compiler_toolchain,
)


class ParseDriverTest(unittest.TestCase):
    def test_build_synthetic_translation_unit_source_includes_headers_in_order(self) -> None:
        headers = [
            Path("/tmp/project/a.hpp"),
            Path("/tmp/project/b.hpp"),
        ]

        source = build_synthetic_translation_unit_source(headers)

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
            extra_args=["-xc++"],
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
                "-xc++",
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

        with patch("oroboros.parse.toolchain.detect_compiler_toolchain") as detect_toolchain:
            detect_toolchain.return_value = SimpleNamespace(
                resource_dir=Path("/tmp/detected-resource"),
                system_include_dirs=[Path("/tmp/detected-system")],
            )
            updated = _resolve_parser_config_toolchain(config)

        detect_toolchain.assert_called_once_with("clang++", language="c++")
        self.assertEqual(updated.include_dirs, [Path("/tmp/project-inc")])
        self.assertEqual(updated.resource_dir, Path("/tmp/detected-resource"))
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
        with patch("oroboros.parse.toolchain._detect_resource_dir", side_effect=FileNotFoundError()):
            with self.assertRaisesRegex(RuntimeError, "was not found"):
                detect_compiler_toolchain("missing-clang")

    def test_detect_compiler_toolchain_reports_probe_failure_with_guidance(self) -> None:
        probe_error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["clang++", "-E", "-v", "-"],
            stderr="probe failed",
        )
        with (
            patch("oroboros.parse.toolchain._detect_resource_dir", return_value=Path("/tmp/resource")),
            patch("oroboros.parse.toolchain._run_compiler_include_probe", side_effect=probe_error),
        ):
            with self.assertRaisesRegex(RuntimeError, "First compiler message: probe failed"):
                detect_compiler_toolchain("clang++")


class ParseDeclsTest(unittest.TestCase):
    def test_build_module_from_translation_unit_materializes_basic_declarations(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        translation_unit = SimpleNamespace(
            cursor=_fake_cursor(
                "TRANSLATION_UNIT",
                "",
                file=active_header,
                children=[
                    _fake_cursor(
                        "NAMESPACE",
                        "demo",
                        file=active_header,
                        children=[
                            _fake_cursor(
                                "CLASS_DECL",
                                "Widget",
                                file=active_header,
                                children=[
                                    _fake_cursor(
                                        "CXX_METHOD",
                                        "size",
                                        file=active_header,
                                        children=[
                                            _fake_cursor(
                                                "PARM_DECL",
                                                "value",
                                                file=active_header,
                                            )
                                        ],
                                    )
                                ],
                            ),
                            _fake_cursor(
                                "FUNCTION_DECL",
                                "make_widget",
                                file=active_header,
                            ),
                        ],
                    )
                ],
            )
        )

        module = build_module_from_translation_unit(translation_unit, [active_header])

        self.assertEqual(module.cpp.header_files, [active_header.resolve()])
        self.assertEqual([namespace.name for namespace in module.namespaces], ["demo"])
        self.assertIsInstance(module.namespaces[0].classes[0], CppClass)
        self.assertEqual(module.namespaces[0].classes[0].name, "Widget")
        self.assertIsInstance(module.namespaces[0].classes[0].methods[0], CppMethod)
        self.assertEqual(module.namespaces[0].classes[0].methods[0].name, "size")
        self.assertEqual(module.namespaces[0].classes[0].methods[0].parameters[0].name, "value")
        self.assertIsInstance(module.namespaces[0].functions[0], CppFunction)
        self.assertEqual(module.namespaces[0].functions[0].name, "make_widget")

    def test_parse_headers_returns_empty_validated_module_for_empty_header_list(self) -> None:
        result = parse_headers([], ParserConfig())

        self.assertEqual(result.headers, [])
        self.assertEqual(result.module.namespaces, [])
        self.assertEqual(result.module.cpp.header_files, [])

    def test_parse_headers_wires_driver_and_builder_results(self) -> None:
        translation_unit = object()
        diagnostics = [SimpleNamespace(severity="warning")]
        driver_result = SimpleNamespace(translation_unit=translation_unit, diagnostics=diagnostics)
        built_module = SimpleNamespace(
            validate_tree=lambda: None,
            validate_semantics=lambda: None,
        )

        with (
            patch("oroboros.parse.api.parse_translation_unit", return_value=driver_result) as parse_tu,
            patch("oroboros.parse.api.build_module_from_translation_unit", return_value=built_module) as build_module,
        ):
            result = parse_headers([Path("/tmp/project/demo.hpp")], ParserConfig())

        parse_tu.assert_called_once()
        build_module.assert_called_once_with(
            translation_unit,
            [Path("/tmp/project/demo.hpp").resolve()],
        )
        self.assertIs(result.module, built_module)
        self.assertEqual(result.diagnostics, diagnostics)
        self.assertEqual(result.headers, [Path("/tmp/project/demo.hpp").resolve()])


def _fake_cursor(
    kind_name: str,
    spelling: str,
    *,
    file: Path,
    line: int = 1,
    column: int = 1,
    children: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        kind=SimpleNamespace(name=kind_name),
        spelling=spelling,
        location=SimpleNamespace(
            file=SimpleNamespace(name=str(file)),
            line=line,
            column=column,
        ),
        get_children=lambda: list(children or []),
    )
