from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from oroboros.model import (
    BuiltinCppType,
    CppClass,
    CppFunction,
    CppMethod,
    CppNamespace,
    CppVisibility,
    LValueReferenceCppType,
    NamedCppType,
    SourceLocation,
    TemplateInstanceCppType,
)
from oroboros.parse import ParserConfig, parse_headers
from oroboros.parse.decls import ModuleBuildResult, build_module_from_translation_unit
from oroboros.parse.driver import build_clang_arguments, build_synthetic_translation_unit_source
from oroboros.parse.types import build_cpp_type
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

        build_result = build_module_from_translation_unit(translation_unit, [active_header])
        module = build_result.module

        self.assertEqual(module.cpp.header_files, [active_header.resolve()])
        self.assertEqual(build_result.skipped_kind_counts, {})
        self.assertEqual([namespace.name for namespace in module.namespaces], ["demo"])
        self.assertIsInstance(module.namespaces[0].classes[0], CppClass)
        self.assertEqual(module.namespaces[0].classes[0].name, "Widget")
        self.assertIsInstance(module.namespaces[0].classes[0].methods[0], CppMethod)
        self.assertEqual(module.namespaces[0].classes[0].methods[0].name, "size")
        self.assertEqual(module.namespaces[0].classes[0].methods[0].parameters[0].name, "value")
        self.assertIsInstance(module.namespaces[0].functions[0], CppFunction)
        self.assertEqual(module.namespaces[0].functions[0].name, "make_widget")

    def test_build_module_from_translation_unit_populates_types_bases_and_flags(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        base_specifier = _fake_cursor(
            "CXX_BASE_SPECIFIER",
            "",
            file=active_header,
            type=_fake_type(
                "RECORD",
                "Mortal",
            ),
            access_specifier="PUBLIC",
        )
        method_parameter_type = _fake_type(
            "LVALUEREFERENCE",
            "const std::string&",
            pointee=_fake_type(
                "ELABORATED",
                "std::string",
                is_const=True,
            ),
        )
        method_cursor = _fake_cursor(
            "CXX_METHOD",
            "bless",
            file=active_header,
            result_type=_fake_type("INT", "int"),
            access_specifier="PUBLIC",
            exception_specification_kind="BASIC_NOEXCEPT",
            methods={
                "is_const_method": True,
                "is_virtual_method": True,
            },
            children=[
                _fake_cursor(
                    "PARM_DECL",
                    "request",
                    file=active_header,
                    type=method_parameter_type,
                )
            ],
        )
        field_cursor = _fake_cursor(
            "FIELD_DECL",
            "values_",
            file=active_header,
            type=_fake_type("ELABORATED", "std::vector<int>"),
            access_specifier="PRIVATE",
        )
        enum_cursor = _fake_cursor(
            "ENUM_DECL",
            "Realm",
            file=active_header,
            access_specifier="PUBLIC",
            enum_type=_fake_type("UINT", "unsigned int"),
            methods={"is_scoped_enum": True},
            children=[
                _fake_cursor(
                    "ENUM_CONSTANT_DECL",
                    "earth",
                    file=active_header,
                    enum_value=1,
                )
            ],
        )
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
                                "Demigod",
                                file=active_header,
                                children=[
                                    base_specifier,
                                    method_cursor,
                                    field_cursor,
                                    enum_cursor,
                                ],
                            ),
                            _fake_cursor(
                                "FUNCTION_DECL",
                                "make_values",
                                file=active_header,
                                result_type=_fake_type("BOOL", "bool"),
                                exception_specification_kind="COMPUTED_NOEXCEPT",
                            ),
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_translation_unit(translation_unit, [active_header])
        module = build_result.module

        cls = module.namespaces[0].classes[0]
        self.assertEqual(cls.cpp.visibility, None)
        self.assertEqual(len(cls.cpp.bases), 1)
        self.assertIsInstance(cls.cpp.bases[0].type, NamedCppType)
        self.assertEqual(cls.cpp.bases[0].type.name, "Mortal")
        self.assertEqual(cls.cpp.bases[0].visibility, CppVisibility.PUBLIC)

        method = cls.methods[0]
        self.assertIsInstance(method.cpp.return_type, BuiltinCppType)
        self.assertEqual(method.cpp.return_type.kind, "int")
        self.assertTrue(method.cpp.is_const)
        self.assertTrue(method.cpp.is_virtual)
        self.assertTrue(method.cpp.is_noexcept)
        self.assertEqual(method.cpp.visibility, CppVisibility.PUBLIC)
        self.assertIsInstance(method.parameters[0].cpp.type, LValueReferenceCppType)
        self.assertIsInstance(method.parameters[0].cpp.type.referred, NamedCppType)
        self.assertTrue(method.parameters[0].cpp.type.referred.is_const)
        self.assertEqual(method.parameters[0].cpp.type.referred.name, "std::string")

        field = cls.fields[0]
        self.assertIsInstance(field.cpp.type, TemplateInstanceCppType)
        self.assertEqual(field.cpp.type.template_name, "std::vector")
        self.assertEqual(field.cpp.visibility, CppVisibility.PRIVATE)

        enum_ = cls.enums[0]
        self.assertTrue(enum_.cpp.is_scoped)
        self.assertIsInstance(enum_.cpp.underlying_type, BuiltinCppType)
        self.assertEqual(enum_.cpp.underlying_type.kind, "unsigned_int")
        self.assertEqual(enum_.enumerators[0].cpp.value_spelling, "1")

        function = module.namespaces[0].functions[0]
        self.assertTrue(function.cpp.is_noexcept)
        self.assertIsInstance(function.cpp.return_type, BuiltinCppType)
        self.assertEqual(function.cpp.return_type.kind, "bool")

    def test_build_module_from_translation_unit_tracks_unsupported_cursor_kinds(self) -> None:
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
                            _fake_cursor("TYPEDEF_DECL", "AliasA", file=active_header),
                            _fake_cursor("TYPEDEF_DECL", "AliasB", file=active_header),
                            _fake_cursor("UNION_DECL", "Storage", file=active_header),
                            _fake_cursor("CXX_ACCESS_SPEC_DECL", "", file=active_header),
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_translation_unit(translation_unit, [active_header])

        self.assertEqual(
            build_result.skipped_kind_counts,
            {
                "TYPEDEF_DECL": 2,
                "UNION_DECL": 1,
            },
        )

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
        build_result = ModuleBuildResult(
            module=built_module,
            skipped_kind_counts={"TYPEDEF_DECL": 2},
        )

        with (
            patch("oroboros.parse.api.parse_translation_unit", return_value=driver_result) as parse_tu,
            patch("oroboros.parse.api.build_module_from_translation_unit", return_value=build_result) as build_module,
        ):
            result = parse_headers([Path("/tmp/project/demo.hpp")], ParserConfig())

        parse_tu.assert_called_once()
        build_module.assert_called_once_with(
            translation_unit,
            [Path("/tmp/project/demo.hpp").resolve()],
        )
        self.assertIs(result.module, built_module)
        self.assertEqual(result.diagnostics, diagnostics)
        self.assertEqual(result.skipped_kind_counts, {"TYPEDEF_DECL": 2})
        self.assertEqual(
            result.warnings,
            ["Skipped unsupported libclang cursor kinds: TYPEDEF_DECL (2)"],
        )
        self.assertEqual(result.headers, [Path("/tmp/project/demo.hpp").resolve()])


class ParseTypesTest(unittest.TestCase):
    def test_build_cpp_type_preserves_named_alias_and_canonical_template(self) -> None:
        clang_type = _fake_type(
            "TYPEDEF",
            "StringVec",
            canonical=_fake_type("ELABORATED", "std::vector<std::string>"),
        )

        cpp_type = build_cpp_type(clang_type)

        self.assertIsInstance(cpp_type, NamedCppType)
        self.assertEqual(cpp_type.name, "StringVec")
        self.assertIsInstance(cpp_type.canonical, TemplateInstanceCppType)
        self.assertEqual(cpp_type.canonical.template_name, "std::vector")
        self.assertEqual(len(cpp_type.canonical.arguments), 1)
        self.assertIsInstance(cpp_type.canonical.arguments[0], NamedCppType)
        self.assertEqual(cpp_type.canonical.arguments[0].name, "std::string")


def _fake_cursor(
    kind_name: str,
    spelling: str,
    *,
    file: Path,
    line: int = 1,
    column: int = 1,
    children: list[SimpleNamespace] | None = None,
    type: SimpleNamespace | None = None,
    result_type: SimpleNamespace | None = None,
    access_specifier: str | None = None,
    exception_specification_kind: str | None = None,
    enum_type: SimpleNamespace | None = None,
    enum_value: int | None = None,
    methods: dict[str, object] | None = None,
) -> SimpleNamespace:
    cursor = SimpleNamespace(
        kind=SimpleNamespace(name=kind_name),
        spelling=spelling,
        type=type,
        result_type=result_type,
        access_specifier=SimpleNamespace(name=access_specifier) if access_specifier is not None else None,
        exception_specification_kind=(
            SimpleNamespace(name=exception_specification_kind)
            if exception_specification_kind is not None else None
        ),
        enum_type=enum_type,
        enum_value=enum_value,
        location=SimpleNamespace(
            file=SimpleNamespace(name=str(file)),
            line=line,
            column=column,
        ),
        get_children=lambda: list(children or []),
    )
    for method_name, method_result in (methods or {}).items():
        setattr(cursor, method_name, lambda result=method_result: result)
    return cursor


def _fake_type(
    kind_name: str,
    spelling: str,
    *,
    is_const: bool = False,
    pointee: SimpleNamespace | None = None,
    element_type: SimpleNamespace | None = None,
    array_size: int | None = None,
    result_type: SimpleNamespace | None = None,
    argument_types: list[SimpleNamespace] | None = None,
    is_variadic: bool = False,
    canonical: SimpleNamespace | None = None,
) -> SimpleNamespace:
    fake_type = SimpleNamespace(
        kind=SimpleNamespace(name=kind_name),
        spelling=spelling,
        is_const_qualified=lambda: is_const,
        get_pointee=lambda: pointee,
        get_array_element_type=lambda: element_type,
        get_array_size=lambda: -1 if array_size is None else array_size,
        get_result=lambda: result_type,
        argument_types=lambda: list(argument_types or []),
        is_function_variadic=lambda: is_variadic,
    )
    fake_type.get_canonical = lambda: canonical if canonical is not None else fake_type
    return fake_type
