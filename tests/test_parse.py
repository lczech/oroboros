from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from oroboros.model import CppClass, CppFunction, CppMethod, CppNamespace, SourceLocation
from oroboros.parse import ParserConfig, parse_headers
from oroboros.parse.decls import build_module_from_translation_unit
from oroboros.parse.driver import build_clang_arguments, build_synthetic_translation_unit_source


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
            defines=["FOO=1", "BAR"],
            undefines=["BAZ"],
            extra_args=["-xc++"],
            cxx_standard="c++20",
        )

        arguments = build_clang_arguments(config)

        self.assertEqual(
            arguments,
            [
                "-fparse-all-comments",
                "-std=c++20",
                "-I/tmp/inc",
                "-I/tmp/vendor",
                "-DFOO=1",
                "-DBAR",
                "-UBAZ",
                "-xc++",
            ],
        )


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
