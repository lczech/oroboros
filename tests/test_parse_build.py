from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from clang.cindex import CursorKind, TypeKind

from oroboros.model import (
    BuiltinCppType,
    CppAlias,
    CppClass,
    CppMethod,
    CppVisibility,
    LValueReferenceCppType,
    NamedCppType,
    PointerCppType,
    TemplateInstanceCppType,
)
from oroboros.parse import ParserConfig
from oroboros.parse.build_model import build_module_from_clang
from oroboros.parse.types import build_cpp_type


class ParseBuildTest(unittest.TestCase):
    def test_build_module_from_clang_materializes_basic_declarations(self) -> None:
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

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        module = build_result.module

        self.assertEqual(module.cpp.header_files, [active_header.resolve()])
        self.assertEqual(build_result.skipped_kind_counts, {})
        self.assertEqual([namespace.name for namespace in module.namespaces], ["demo"])
        self.assertIsInstance(module.namespaces[0].classes[0], CppClass)
        self.assertEqual(module.namespaces[0].classes[0].name, "Widget")
        self.assertIsInstance(module.namespaces[0].classes[0].methods[0], CppMethod)
        self.assertEqual(module.namespaces[0].classes[0].methods[0].name, "size")
        self.assertEqual(module.namespaces[0].classes[0].methods[0].parameters[0].name, "value")

    def test_build_module_from_clang_reuses_existing_nodes_by_usr(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        translation_unit = SimpleNamespace(
            cursor=_fake_cursor(
                "TRANSLATION_UNIT",
                "",
                file=active_header,
                children=[
                    _fake_cursor(
                        "FUNCTION_DECL",
                        "make_widget",
                        file=active_header,
                        usr="c:@F@make_widget#",
                        children=[
                            _fake_cursor(
                                "PARM_DECL",
                                "value",
                                file=active_header,
                                usr="c:@F@make_widget#@value",
                            )
                        ],
                    ),
                    _fake_cursor(
                        "FUNCTION_DECL",
                        "make_widget",
                        file=active_header,
                        usr="c:@F@make_widget#",
                        children=[
                            _fake_cursor(
                                "PARM_DECL",
                                "request",
                                file=active_header,
                                usr="c:@F@make_widget#@request",
                            )
                        ],
                    ),
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        module = build_result.module

        self.assertEqual(len(module.functions), 1)
        self.assertEqual(module.functions[0].name, "make_widget")
        self.assertEqual(len(module.functions[0].parameters), 1)
        self.assertEqual(module.functions[0].parameters[0].name, "value")

    def test_build_module_from_clang_populates_types_bases_and_flags(self) -> None:
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

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
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

    def test_build_module_from_clang_links_named_types_to_declarations_by_usr(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        widget_cursor = _fake_cursor(
            "CLASS_DECL",
            "Widget",
            file=active_header,
            usr="c:@N@demo@S@Widget",
        )
        method_parameter_type = _fake_type(
            "LVALUEREFERENCE",
            "const Widget&",
            pointee=_fake_type(
                "ELABORATED",
                "Widget",
                is_const=True,
                declaration_cursor=widget_cursor,
            ),
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
                            widget_cursor,
                            _fake_cursor(
                                "FUNCTION_DECL",
                                "make_widget",
                                file=active_header,
                                result_type=_fake_type(
                                    "ELABORATED",
                                    "Widget",
                                    declaration_cursor=widget_cursor,
                                ),
                            ),
                            _fake_cursor(
                                "CLASS_DECL",
                                "Holder",
                                file=active_header,
                                children=[
                                    _fake_cursor(
                                        "CXX_BASE_SPECIFIER",
                                        "",
                                        file=active_header,
                                        type=_fake_type(
                                            "RECORD",
                                            "Widget",
                                            declaration_cursor=widget_cursor,
                                        ),
                                        access_specifier="PUBLIC",
                                    ),
                                    _fake_cursor(
                                        "CXX_METHOD",
                                        "take_widget",
                                        file=active_header,
                                        result_type=_fake_type("VOID", "void"),
                                        children=[
                                            _fake_cursor(
                                                "PARM_DECL",
                                                "widget",
                                                file=active_header,
                                                type=method_parameter_type,
                                            )
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        namespace = build_result.module.namespaces[0]
        widget = namespace.classes[0]
        function = namespace.functions[0]
        holder = namespace.classes[1]
        method = holder.methods[0]

        self.assertIsInstance(function.cpp.return_type, NamedCppType)
        self.assertIs(function.cpp.return_type.declaration, widget)
        self.assertIsInstance(holder.cpp.bases[0].type, NamedCppType)
        self.assertIs(holder.cpp.bases[0].type.declaration, widget)
        self.assertIsInstance(method.parameters[0].cpp.type, LValueReferenceCppType)
        self.assertIsInstance(method.parameters[0].cpp.type.referred, NamedCppType)
        self.assertIs(method.parameters[0].cpp.type.referred.declaration, widget)

    def test_build_module_from_clang_leaves_external_named_types_unlinked(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        translation_unit = SimpleNamespace(
            cursor=_fake_cursor(
                "TRANSLATION_UNIT",
                "",
                file=active_header,
                children=[
                    _fake_cursor(
                        "FUNCTION_DECL",
                        "take_external",
                        file=active_header,
                        result_type=_fake_type("VOID", "void"),
                        children=[
                            _fake_cursor(
                                "PARM_DECL",
                                "value",
                                file=active_header,
                                type=_fake_type(
                                    "ELABORATED",
                                    "External",
                                    declaration_cursor=_fake_cursor(
                                        "CLASS_DECL",
                                        "External",
                                        file=Path("/tmp/external/external.hpp"),
                                        usr="c:@N@ext@S@External",
                                    ),
                                ),
                            )
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        parameter_type = build_result.module.functions[0].parameters[0].cpp.type

        self.assertIsInstance(parameter_type, NamedCppType)
        self.assertIsNone(parameter_type.declaration)

    def test_build_module_from_clang_allows_scope_relative_qualified_type_spellings(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        omen_kind_cursor = _fake_cursor(
            "ENUM_DECL",
            "OmenKind",
            file=active_header,
            usr="c:@N@cosmos@N@types@E@OmenKind",
        )
        vocation_cursor = _fake_cursor(
            "ENUM_DECL",
            "Vocation",
            file=active_header,
            usr="c:@N@cosmos@N@beings@S@Mortal@E@Vocation",
        )
        translation_unit = SimpleNamespace(
            cursor=_fake_cursor(
                "TRANSLATION_UNIT",
                "",
                file=active_header,
                children=[
                    _fake_cursor(
                        "NAMESPACE",
                        "cosmos",
                        file=active_header,
                        children=[
                            _fake_cursor(
                                "NAMESPACE",
                                "types",
                                file=active_header,
                                children=[omen_kind_cursor],
                            ),
                            _fake_cursor(
                                "NAMESPACE",
                                "functions",
                                file=active_header,
                                children=[
                                    _fake_cursor(
                                        "NAMESPACE",
                                        "omens",
                                        file=active_header,
                                        children=[
                                            _fake_cursor(
                                                "FUNCTION_DECL",
                                                "classify",
                                                file=active_header,
                                                result_type=_fake_type(
                                                    "ELABORATED",
                                                    "types::OmenKind",
                                                    declaration_cursor=omen_kind_cursor,
                                                ),
                                            )
                                        ],
                                    )
                                ],
                            ),
                            _fake_cursor(
                                "NAMESPACE",
                                "beings",
                                file=active_header,
                                children=[
                                    _fake_cursor(
                                        "CLASS_DECL",
                                        "Mortal",
                                        file=active_header,
                                        children=[vocation_cursor],
                                    ),
                                    _fake_cursor(
                                        "FUNCTION_DECL",
                                        "vocation_name",
                                        file=active_header,
                                        result_type=_fake_type("VOID", "void"),
                                        children=[
                                            _fake_cursor(
                                                "PARM_DECL",
                                                "vocation",
                                                file=active_header,
                                                type=_fake_type(
                                                    "ELABORATED",
                                                    "Mortal::Vocation",
                                                    declaration_cursor=vocation_cursor,
                                                ),
                                            )
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())

        build_result.module.validate_semantics()

    def test_build_module_from_clang_materializes_alias_declarations(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        widget_cursor = _fake_cursor(
            "CLASS_DECL",
            "Widget",
            file=active_header,
            usr="c:@N@demo@S@Widget",
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
                            widget_cursor,
                            _fake_cursor(
                                "TYPE_ALIAS_DECL",
                                "Alias",
                                file=active_header,
                                usr="c:@N@demo@Alias",
                                type=_fake_type("TYPEDEF", "Alias"),
                                underlying_typedef_type=_fake_type(
                                    "ELABORATED",
                                    "Widget",
                                    declaration_cursor=widget_cursor,
                                ),
                            ),
                            _fake_cursor(
                                "TYPEDEF_DECL",
                                "WidgetAlias",
                                file=active_header,
                                usr="c:@N@demo@T@WidgetAlias",
                                type=_fake_type("TYPEDEF", "WidgetAlias"),
                                underlying_typedef_type=_fake_type(
                                    "ELABORATED",
                                    "Widget",
                                    declaration_cursor=widget_cursor,
                                ),
                            ),
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        namespace = build_result.module.namespaces[0]

        self.assertEqual([alias.name for alias in namespace.aliases], ["Alias", "WidgetAlias"])
        self.assertIsInstance(namespace.aliases[0], CppAlias)
        self.assertEqual(namespace.aliases[0].qualified_name, "demo::Alias")
        self.assertEqual(namespace.aliases[0].cpp.kind, "using")
        self.assertIsInstance(namespace.aliases[0].cpp.target, NamedCppType)
        self.assertIs(namespace.aliases[0].cpp.target.declaration, namespace.classes[0])
        self.assertEqual(namespace.aliases[1].cpp.kind, "typedef")

    def test_build_module_from_clang_merges_reopened_namespace_provenance(self) -> None:
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
                        line=3,
                        raw_comment=None,
                        children=[
                            _fake_cursor(
                                "CLASS_DECL",
                                "Widget",
                                file=active_header,
                                usr="c:@N@demo@S@Widget",
                            ),
                        ],
                    ),
                    _fake_cursor(
                        "NAMESPACE",
                        "demo",
                        file=active_header,
                        line=12,
                        raw_comment="/// Namespace docs.",
                        children=[
                            _fake_cursor(
                                "FUNCTION_DECL",
                                "make_widget",
                                file=active_header,
                                usr="c:@N@demo@F@make_widget#",
                                result_type=_fake_type("INT", "int"),
                            ),
                        ],
                    ),
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        namespace = build_result.module.namespaces[0]

        self.assertEqual(namespace.name, "demo")
        self.assertEqual(len(namespace.cpp.location.declarations), 2)
        self.assertIsNotNone(namespace.cpp.comment)
        self.assertIn("Namespace docs.", namespace.cpp.comment)
        self.assertEqual(len(namespace.classes), 1)
        self.assertEqual(len(namespace.functions), 1)

    def test_build_module_from_clang_links_nested_template_argument_types_to_declarations(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        widget_cursor = _fake_cursor(
            "CLASS_DECL",
            "Widget",
            file=active_header,
            usr="c:@N@demo@S@Widget",
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
                            widget_cursor,
                            _fake_cursor(
                                "FUNCTION_DECL",
                                "take_nested",
                                file=active_header,
                                result_type=_fake_type("VOID", "void"),
                                children=[
                                    _fake_cursor(
                                        "PARM_DECL",
                                        "value",
                                        file=active_header,
                                        type=_fake_type(
                                            "UNEXPOSED",
                                            "Box<Pair<int, Widget>>",
                                            template_argument_types=[
                                                _fake_type(
                                                    "UNEXPOSED",
                                                    "Pair<int, Widget>",
                                                    template_argument_types=[
                                                        _fake_type("INT", "int"),
                                                        _fake_type(
                                                            "ELABORATED",
                                                            "Widget",
                                                            declaration_cursor=widget_cursor,
                                                        ),
                                                    ],
                                                ),
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        parameter_type = build_result.module.namespaces[0].functions[0].parameters[0].cpp.type

        self.assertIsInstance(parameter_type, TemplateInstanceCppType)
        self.assertIsInstance(parameter_type.arguments[0], TemplateInstanceCppType)
        self.assertIsInstance(parameter_type.arguments[0].arguments[1], NamedCppType)
        self.assertIs(
            parameter_type.arguments[0].arguments[1].declaration,
            build_result.module.namespaces[0].classes[0],
        )

    def test_build_module_from_clang_warns_on_unexpected_repeated_non_redeclarable_declarations(self) -> None:
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
                                "TYPE_ALIAS_DECL",
                                "Index",
                                file=active_header,
                                usr="c:@N@demo@Alias",
                                type=_fake_type("TYPEDEF", "Index"),
                                underlying_typedef_type=_fake_type("ULONG", "unsigned long"),
                            ),
                            _fake_cursor(
                                "TYPE_ALIAS_DECL",
                                "Index",
                                file=active_header,
                                usr="c:@N@demo@Alias",
                                type=_fake_type("TYPEDEF", "Index"),
                                underlying_typedef_type=_fake_type("UINT", "unsigned int"),
                            ),
                            _fake_cursor(
                                "CLASS_DECL",
                                "Widget",
                                file=active_header,
                                children=[
                                    _fake_cursor(
                                        "FIELD_DECL",
                                        "size_",
                                        file=active_header,
                                        usr="c:@N@demo@S@Widget@FI@size_",
                                        type=_fake_type("INT", "int"),
                                    ),
                                    _fake_cursor(
                                        "FIELD_DECL",
                                        "size_",
                                        file=active_header,
                                        usr="c:@N@demo@S@Widget@FI@size_",
                                        type=_fake_type("BOOL", "bool"),
                                    ),
                                    _fake_cursor(
                                        "ENUM_DECL",
                                        "Kind",
                                        file=active_header,
                                        children=[
                                            _fake_cursor(
                                                "ENUM_CONSTANT_DECL",
                                                "primary",
                                                file=active_header,
                                                usr="c:@N@demo@S@Widget@E@Kind@primary",
                                                enum_value=1,
                                            ),
                                            _fake_cursor(
                                                "ENUM_CONSTANT_DECL",
                                                "primary",
                                                file=active_header,
                                                usr="c:@N@demo@S@Widget@E@Kind@primary",
                                                enum_value=2,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        namespace = build_result.module.namespaces[0]
        widget = namespace.classes[0]

        self.assertEqual(len(namespace.aliases), 1)
        self.assertEqual(namespace.aliases[0].name, "Index")
        self.assertIsInstance(namespace.aliases[0].cpp.target, BuiltinCppType)
        self.assertEqual(namespace.aliases[0].cpp.target.kind, "unsigned_long")
        self.assertEqual(len(widget.fields), 1)
        self.assertIsInstance(widget.fields[0].cpp.type, BuiltinCppType)
        self.assertEqual(widget.fields[0].cpp.type.kind, "int")
        self.assertEqual(len(widget.enums[0].enumerators), 1)
        self.assertEqual(widget.enums[0].enumerators[0].cpp.value_spelling, "1")
        self.assertTrue(
            any("repeated alias declaration" in warning for warning in build_result.warnings)
        )
        self.assertTrue(
            any("repeated field declaration" in warning for warning in build_result.warnings)
        )
        self.assertTrue(
            any("repeated enumerator declaration" in warning for warning in build_result.warnings)
        )

    def test_build_module_from_clang_tracks_unsupported_cursor_kinds(self) -> None:
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
                            _fake_cursor("UNION_DECL", "Storage", file=active_header),
                            _fake_cursor("CXX_ACCESS_SPEC_DECL", "", file=active_header),
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())

        self.assertEqual(
            build_result.skipped_kind_counts,
            {
                "UNION_DECL": 1,
            },
        )

    def test_build_module_from_clang_prefers_longer_conflicting_comment_by_default(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        translation_unit = SimpleNamespace(
            cursor=_fake_cursor(
                "TRANSLATION_UNIT",
                "",
                file=active_header,
                children=[
                    _fake_cursor(
                        "FUNCTION_DECL",
                        "make_widget",
                        file=active_header,
                        usr="c:@F@make_widget#",
                        raw_comment="/// Forward declaration note.",
                    ),
                    _fake_cursor(
                        "FUNCTION_DECL",
                        "make_widget",
                        file=active_header,
                        usr="c:@F@make_widget#",
                        raw_comment="/// Create one widget from the current demo factory state.",
                    ),
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())

        self.assertEqual(len(build_result.module.functions), 1)
        self.assertEqual(
            build_result.module.functions[0].cpp.comment,
            "/// Create one widget from the current demo factory state.",
        )
        self.assertTrue(
            any("Conflicting parsed comments" in warning for warning in build_result.warnings)
        )


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

    def test_build_cpp_type_parses_pointer_constness_correctly_in_template_argument_spellings(self) -> None:
        clang_type = _fake_type(
            "ELABORATED",
            "Pair<Widget const* const, const Widget* const>",
        )

        cpp_type = build_cpp_type(clang_type)

        self.assertIsInstance(cpp_type, TemplateInstanceCppType)
        self.assertEqual(cpp_type.template_name, "Pair")
        self.assertEqual(len(cpp_type.arguments), 2)

        first_argument = cpp_type.arguments[0]
        second_argument = cpp_type.arguments[1]

        self.assertIsInstance(first_argument, PointerCppType)
        self.assertTrue(first_argument.is_const)
        self.assertIsInstance(first_argument.pointee, NamedCppType)
        self.assertEqual(first_argument.pointee.name, "Widget")
        self.assertTrue(first_argument.pointee.is_const)

        self.assertIsInstance(second_argument, PointerCppType)
        self.assertTrue(second_argument.is_const)
        self.assertIsInstance(second_argument.pointee, NamedCppType)
        self.assertEqual(second_argument.pointee.name, "Widget")
        self.assertTrue(second_argument.pointee.is_const)


def _fake_cursor(
    kind_name: str,
    spelling: str,
    *,
    file: Path,
    usr: str | None = None,
    raw_comment: str | None = None,
    line: int = 1,
    column: int = 1,
    children: list[SimpleNamespace] | None = None,
    type: SimpleNamespace | None = None,
    result_type: SimpleNamespace | None = None,
    access_specifier: str | None = None,
    exception_specification_kind: str | None = None,
    enum_type: SimpleNamespace | None = None,
    enum_value: int | None = None,
    underlying_typedef_type: SimpleNamespace | None = None,
    methods: dict[str, object] | None = None,
) -> SimpleNamespace:
    cursor = SimpleNamespace(
        kind=getattr(CursorKind, kind_name),
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
        underlying_typedef_type=underlying_typedef_type,
        raw_comment=raw_comment,
        location=SimpleNamespace(
            file=SimpleNamespace(name=str(file)),
            line=line,
            column=column,
        ),
        get_children=lambda: list(children or []),
        get_usr=lambda: usr,
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
    template_argument_types: list[SimpleNamespace] | None = None,
    is_variadic: bool = False,
    canonical: SimpleNamespace | None = None,
    declaration_cursor: SimpleNamespace | None = None,
) -> SimpleNamespace:
    fake_type = SimpleNamespace(
        kind=getattr(TypeKind, kind_name),
        spelling=spelling,
        is_const_qualified=lambda: is_const,
        get_pointee=lambda: pointee,
        get_array_element_type=lambda: element_type,
        get_array_size=lambda: -1 if array_size is None else array_size,
        get_result=lambda: result_type,
        argument_types=lambda: list(argument_types or []),
        get_num_template_arguments=lambda: len(template_argument_types or []),
        get_template_argument_type=lambda index: list(template_argument_types or [])[index],
        is_function_variadic=lambda: is_variadic,
        get_declaration=lambda: declaration_cursor,
    )
    fake_type.get_canonical = lambda: canonical if canonical is not None else fake_type
    return fake_type
