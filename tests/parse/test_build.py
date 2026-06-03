from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from clang.cindex import CursorKind, TokenKind, TypeKind

from oroboros.model import *
from oroboros.parse import ParserConfig, ParserInvariantError
from oroboros.parse.build_model import BuildContext, build_module_from_clang
from oroboros.parse.cursor_data import cursor_class_kind, is_class_cursor
from oroboros.parse.merge_properties import (
    _element_diagnostic_locations,
    merge_class_bases,
    merge_cpp_scalar,
    merge_template_parameters,
)
from oroboros.parse.template_observations import record_template_observation_hints_in_type
from oroboros.parse.types import build_cpp_type


class ParseBuildTest(unittest.TestCase):
    def test_is_class_cursor_identifies_only_class_decl(self) -> None:
        class_cursor = _fake_cursor("CLASS_DECL", "Widget", file=Path("/tmp/project/demo.hpp"))
        struct_cursor = _fake_cursor("STRUCT_DECL", "Widget", file=Path("/tmp/project/demo.hpp"))

        self.assertTrue(is_class_cursor(class_cursor))
        self.assertFalse(is_class_cursor(struct_cursor))

    def test_cursor_class_kind_returns_class_for_class_decl(self) -> None:
        cursor = _fake_cursor("CLASS_DECL", "Widget", file=Path("/tmp/project/demo.hpp"))

        self.assertEqual(cursor_class_kind(cursor), "class")

    def test_cursor_class_kind_recovers_struct_for_class_template_from_header_tokens(self) -> None:
        cursor = _fake_cursor(
            "CLASS_TEMPLATE",
            "Widget",
            file=Path("/tmp/project/demo.hpp"),
            tokens=["template", "<", "class", "T", ">", "struct", "Widget", "{", "struct", "Inner"],
        )

        self.assertEqual(cursor_class_kind(cursor), "struct")

    def test_cursor_class_kind_raises_when_header_tokens_lack_record_keyword(self) -> None:
        cursor = _fake_cursor(
            "CLASS_TEMPLATE",
            "Widget",
            file=Path("/tmp/project/demo.hpp"),
            tokens=["template", "<", "class", "T", ">", "Widget", "{", "}"],
        )

        with self.assertRaisesRegex(ParserInvariantError, "Failed to determine class-like declaration spelling"):
            cursor_class_kind(cursor)

    def test_merge_cpp_scalar_reports_existing_and_new_values_in_detail(self) -> None:
        context = BuildContext(
            active_headers=set(),
            known_project_headers=set(),
            config=ParserConfig(),
        )
        function = CppFunction(name="make_widget")
        function.cpp.availability = "available"
        cursor = _fake_cursor("FUNCTION_DECL", "make_widget", file=Path("/tmp/project/demo.hpp"))

        merge_cpp_scalar(function, "availability", "deprecated", context, cursor)

        self.assertEqual(len(context.report.warnings), 1)
        warning = context.report.warnings[0]
        self.assertEqual(warning.code, "parse.merge.conflicting_scalar")
        self.assertIsNotNone(warning.detail)
        self.assertIn("existing parsed availability:", warning.detail)
        self.assertIn("'available'", warning.detail)
        self.assertIn("new parsed availability:", warning.detail)
        self.assertIn("'deprecated'", warning.detail)
        self.assertIn("selected: existing", warning.detail)

    def test_merge_class_bases_reports_existing_and_new_values_in_detail(self) -> None:
        context = BuildContext(
            active_headers=set(),
            known_project_headers=set(),
            config=ParserConfig(),
        )
        class_ = CppClass(name="Widget")
        class_.cpp.bases.append(
            CppClassBase(
                type=NamedCppType(name="BaseA"),
                visibility=CppVisibility.PUBLIC,
            )
        )
        cursor = _fake_cursor("CLASS_DECL", "Widget", file=Path("/tmp/project/demo.hpp"))

        merge_class_bases(
            class_,
            [
                CppClassBase(
                    type=NamedCppType(name="BaseB"),
                    visibility=CppVisibility.PUBLIC,
                )
            ],
            context,
            cursor,
        )

        self.assertEqual(len(context.report.warnings), 1)
        warning = context.report.warnings[0]
        self.assertEqual(warning.code, "parse.merge.conflicting_bases")
        self.assertIsNotNone(warning.detail)
        self.assertIn("existing parsed bases:", warning.detail)
        self.assertIn("BaseA", warning.detail)
        self.assertIn("new parsed bases:", warning.detail)
        self.assertIn("BaseB", warning.detail)
        self.assertIn("selected: existing", warning.detail)

    def test_merge_template_parameters_reports_existing_and_new_values_in_detail(self) -> None:
        context = BuildContext(
            active_headers=set(),
            known_project_headers=set(),
            config=ParserConfig(),
        )
        cursor = _fake_cursor("FUNCTION_TEMPLATE", "make_widget", file=Path("/tmp/project/demo.hpp"))
        existing_parameters = [CppTypeTemplateParameter(name="T")]
        new_parameters = [CppTypeTemplateParameter(name="U")]

        merge_template_parameters(existing_parameters, new_parameters, context, cursor)

        self.assertEqual(len(context.report.warnings), 1)
        warning = context.report.warnings[0]
        self.assertEqual(warning.code, "parse.merge.conflicting_template_parameters")
        self.assertIsNotNone(warning.detail)
        self.assertIn("existing parsed template_parameters:", warning.detail)
        self.assertIn("name='T'", warning.detail)
        self.assertIn("new parsed template_parameters:", warning.detail)
        self.assertIn("name='U'", warning.detail)
        self.assertIn("selected: existing", warning.detail)

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
        self.assertEqual([namespace.name for namespace in module.declarations.namespaces], ["demo"])
        self.assertIsInstance(module.declarations.namespaces[0].declarations.classes[0], CppClass)
        self.assertEqual(module.declarations.namespaces[0].declarations.classes[0].name, "Widget")
        self.assertIsInstance(module.declarations.namespaces[0].declarations.classes[0].declarations.methods[0], CppMethod)
        self.assertEqual(module.declarations.namespaces[0].declarations.classes[0].declarations.methods[0].name, "size")
        self.assertEqual(module.declarations.namespaces[0].declarations.classes[0].declarations.methods[0].parameters[0].name, "value")

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

        self.assertEqual(len(module.declarations.functions), 1)
        self.assertEqual(module.declarations.functions[0].name, "make_widget")
        self.assertEqual(len(module.declarations.functions[0].parameters), 1)
        self.assertEqual(module.declarations.functions[0].parameters[0].name, "value")

    def test_build_module_from_clang_materializes_destructors(self) -> None:
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
                                        "DESTRUCTOR",
                                        "~Widget",
                                        file=active_header,
                                        access_specifier="PUBLIC",
                                        methods={
                                            "is_virtual_method": True,
                                            "is_default_method": True,
                                        },
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        cls = build_result.module.declarations.namespaces[0].declarations.classes[0]
        destructor = cls.declarations.destructor

        self.assertIsNotNone(destructor)
        self.assertEqual(destructor.name, "~Widget")
        self.assertTrue(destructor.cpp.is_virtual)
        self.assertTrue(destructor.cpp.is_defaulted)
        self.assertEqual(destructor.cpp.visibility, CppVisibility.PUBLIC)

    def test_build_module_from_clang_populates_method_ref_qualifiers_from_tokens(self) -> None:
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
                                        "invoke",
                                        file=active_header,
                                        result_type=_fake_type("VOID", "void"),
                                        tokens=["void", "invoke", "(", ")", "const", "&"],
                                        methods={"is_const_method": True},
                                    ),
                                    _fake_cursor(
                                        "CXX_METHOD",
                                        "consume",
                                        file=active_header,
                                        result_type=_fake_type("VOID", "void"),
                                        tokens=["void", "consume", "(", ")", "&&"],
                                    ),
                                ],
                            )
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        methods = build_result.module.declarations.namespaces[0].declarations.classes[0].declarations.methods

        self.assertEqual(methods[0].cpp.ref_qualifier, "&")
        self.assertTrue(methods[0].cpp.is_const)
        self.assertEqual(methods[1].cpp.ref_qualifier, "&&")

    def test_build_module_from_clang_populates_method_template_defaulted_flag(self) -> None:
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
                                        "FUNCTION_TEMPLATE",
                                        "compare",
                                        file=active_header,
                                        result_type=_fake_type("BOOL", "bool"),
                                        methods={"is_default_method": True},
                                        children=[
                                            _fake_cursor(
                                                "TEMPLATE_TYPE_PARAMETER",
                                                "T",
                                                file=active_header,
                                                tokens=["class", "T"],
                                            )
                                        ],
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        method_template = (
            build_result.module
            .declarations.namespaces[0]
            .declarations.classes[0]
            .declarations.method_templates[0]
        )

        self.assertTrue(method_template.declaration.cpp.is_defaulted)

    def test_build_module_from_clang_enriches_repeated_variable_cpp_fields(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        translation_unit = SimpleNamespace(
            cursor=_fake_cursor(
                "TRANSLATION_UNIT",
                "",
                file=active_header,
                children=[
                    _fake_cursor(
                        "VAR_DECL",
                        "counter",
                        file=active_header,
                        usr="c:@counter",
                        type=_fake_type("INT", "int"),
                    ),
                    _fake_cursor(
                        "VAR_DECL",
                        "counter",
                        file=active_header,
                        usr="c:@counter",
                        type=_fake_type("INT", "int"),
                        storage_class="STATIC",
                        linkage="INTERNAL",
                        tls_kind="DYNAMIC",
                    ),
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        variable = build_result.module.declarations.variables[0]

        self.assertEqual(variable.cpp.storage_class, "static")
        self.assertEqual(variable.cpp.linkage, "internal")
        self.assertEqual(variable.cpp.tls_kind, "dynamic")

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
        variable_cursor = _fake_cursor(
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
                                    variable_cursor,
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

        cls = module.declarations.namespaces[0].declarations.classes[0]
        self.assertEqual(cls.cpp.visibility, None)
        self.assertEqual(len(cls.cpp.bases), 1)
        self.assertIsInstance(cls.cpp.bases[0].type, NamedCppType)
        self.assertEqual(cls.cpp.bases[0].type.name, "Mortal")
        self.assertEqual(cls.cpp.bases[0].visibility, CppVisibility.PUBLIC)

        method = cls.declarations.methods[0]
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

        variable = cls.declarations.variables[0]
        self.assertIsInstance(variable.cpp.type, TemplateInstanceCppType)
        self.assertEqual(variable.cpp.type.template_name, "std::vector")
        self.assertEqual(variable.cpp.visibility, CppVisibility.PRIVATE)

        enum_ = cls.declarations.enums[0]
        self.assertTrue(enum_.cpp.is_scoped)
        self.assertIsInstance(enum_.cpp.underlying_type, BuiltinCppType)
        self.assertEqual(enum_.cpp.underlying_type.kind, "unsigned_int")
        self.assertEqual(enum_.enumerators[0].cpp.value_spelling, "1")

        function = module.declarations.namespaces[0].declarations.functions[0]
        self.assertTrue(function.cpp.is_noexcept)
        self.assertIsInstance(function.cpp.return_type, BuiltinCppType)
        self.assertEqual(function.cpp.return_type.kind, "bool")

    def test_build_module_from_clang_materializes_var_decl_variables_and_ignores_locals(self) -> None:
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
                                "VAR_DECL",
                                "global_count",
                                file=active_header,
                                type=_fake_type("INT", "int"),
                            ),
                            _fake_cursor(
                                "CLASS_DECL",
                                "Widget",
                                file=active_header,
                                children=[
                                    _fake_cursor(
                                        "FIELD_DECL",
                                        "value",
                                        file=active_header,
                                        type=_fake_type("INT", "int"),
                                    ),
                                    _fake_cursor(
                                        "VAR_DECL",
                                        "instance_count",
                                        file=active_header,
                                        type=_fake_type("INT", "int"),
                                        access_specifier="PUBLIC",
                                    ),
                                    _fake_cursor(
                                        "CXX_METHOD",
                                        "size",
                                        file=active_header,
                                        result_type=_fake_type("INT", "int"),
                                        children=[
                                            _fake_cursor(
                                                "VAR_DECL",
                                                "local_count",
                                                file=active_header,
                                                type=_fake_type("INT", "int"),
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
        namespace = build_result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]

        self.assertEqual([variable.name for variable in namespace.declarations.variables], ["global_count"])
        self.assertEqual([variable.name for variable in widget.declarations.variables], ["value"])
        self.assertEqual([variable.name for variable in widget.declarations.static_variables], ["instance_count"])
        self.assertEqual(widget.declarations.variables[0].cpp.kind, "member_variable")
        self.assertEqual(widget.declarations.static_variables[0].cpp.kind, "static_member_variable")
        self.assertEqual(namespace.declarations.variables[0].cpp.kind, "variable")
        self.assertEqual(widget.declarations.methods[0].element_names, [])

    def test_build_module_from_clang_populates_variable_constness_and_storage_metadata(self) -> None:
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
                                "VAR_DECL",
                                "global_count",
                                file=active_header,
                                type=_fake_type("INT", "int"),
                                linkage="EXTERNAL",
                            ),
                            _fake_cursor(
                                "VAR_DECL",
                                "internal_count",
                                file=active_header,
                                type=_fake_type("INT", "int"),
                                storage_class="STATIC",
                                linkage="INTERNAL",
                            ),
                            _fake_cursor(
                                "VAR_DECL",
                                "tls_count",
                                file=active_header,
                                type=_fake_type("INT", "int"),
                                tls_kind="DYNAMIC",
                            ),
                            _fake_cursor(
                                "VAR_DECL",
                                "answer",
                                file=active_header,
                                type=_fake_type("INT", "const int", is_const=True),
                            ),
                        ],
                    )
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        namespace = build_result.module.declarations.namespaces[0]
        variables = {variable.name: variable for variable in namespace.declarations.variables}

        self.assertFalse(variables["global_count"].cpp.is_const)
        self.assertEqual(variables["global_count"].cpp.linkage, "external")
        self.assertIsNone(variables["global_count"].cpp.storage_class)
        self.assertIsNone(variables["global_count"].cpp.tls_kind)

        self.assertEqual(variables["internal_count"].cpp.storage_class, "static")
        self.assertEqual(variables["internal_count"].cpp.linkage, "internal")

        self.assertEqual(variables["tls_count"].cpp.tls_kind, "dynamic")
        self.assertTrue(variables["answer"].cpp.is_const)

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
        namespace = build_result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        function = namespace.declarations.functions[0]
        holder = namespace.declarations.classes[1]
        method = holder.declarations.methods[0]

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
        parameter_type = build_result.module.declarations.functions[0].parameters[0].cpp.type

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
        namespace = build_result.module.declarations.namespaces[0]

        self.assertEqual([alias.name for alias in namespace.declarations.aliases], ["Alias", "WidgetAlias"])
        self.assertIsInstance(namespace.declarations.aliases[0], CppAlias)
        self.assertEqual(namespace.declarations.aliases[0].qualified_name, "demo::Alias")
        self.assertEqual(namespace.declarations.aliases[0].cpp.kind, "using")
        self.assertIsInstance(namespace.declarations.aliases[0].cpp.target, NamedCppType)
        self.assertIs(namespace.declarations.aliases[0].cpp.target.declaration, namespace.declarations.classes[0])
        self.assertEqual(namespace.declarations.aliases[1].cpp.kind, "typedef")

    def test_build_module_from_clang_merges_reopened_namespace_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            active_header = Path(temp_dir) / "demo.hpp"
            active_header.write_text("\n" * 20)
            translation_unit = _fake_translation_unit(
                _fake_cursor(
                    "TRANSLATION_UNIT",
                    "",
                    file=active_header,
                    children=[
                        _fake_cursor(
                            "NAMESPACE",
                            "demo",
                            file=active_header,
                            line=3,
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
                ),
                tokens=[
                    _fake_comment_token(
                        active_header,
                        "/// Namespace docs.",
                        start_line=11,
                    ),
                ],
            )

            build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
            namespace = build_result.module.declarations.namespaces[0]

            self.assertEqual(namespace.name, "demo")
            self.assertEqual(len(namespace.cpp.location.declarations), 2)
            self.assertIsNotNone(namespace.cpp.doc.attached_comment)
            self.assertIn("Namespace docs.", namespace.cpp.doc.attached_comment)
            self.assertEqual(len(namespace.declarations.classes), 1)
            self.assertEqual(len(namespace.declarations.functions), 1)

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
        parameter_type = build_result.module.declarations.namespaces[0].declarations.functions[0].parameters[0].cpp.type

        self.assertIsInstance(parameter_type, TemplateInstanceCppType)
        self.assertIsInstance(parameter_type.arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(parameter_type.arguments[0].type, TemplateInstanceCppType)
        self.assertIsInstance(parameter_type.arguments[0].type.arguments[1], CppTypeTemplateArgument)
        self.assertIsInstance(parameter_type.arguments[0].type.arguments[1].type, NamedCppType)
        self.assertIs(
            parameter_type.arguments[0].type.arguments[1].type.declaration,
            build_result.module.declarations.namespaces[0].declarations.classes[0],
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
        namespace = build_result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]

        self.assertEqual(len(namespace.declarations.aliases), 1)
        self.assertEqual(namespace.declarations.aliases[0].name, "Index")
        self.assertIsInstance(namespace.declarations.aliases[0].cpp.target, BuiltinCppType)
        self.assertEqual(namespace.declarations.aliases[0].cpp.target.kind, "unsigned_long")
        self.assertEqual(len(widget.declarations.variables), 1)
        self.assertIsInstance(widget.declarations.variables[0].cpp.type, BuiltinCppType)
        self.assertEqual(widget.declarations.variables[0].cpp.type.kind, "int")
        self.assertEqual(len(widget.declarations.enums[0].enumerators), 1)
        self.assertEqual(widget.declarations.enums[0].enumerators[0].cpp.value_spelling, "1")
        self.assertTrue(
            any("repeated alias declaration" in warning.message for warning in build_result.report.warnings)
        )
        self.assertTrue(
            any("repeated variable declaration" in warning.message for warning in build_result.report.warnings)
        )
        self.assertTrue(
            any("repeated enumerator declaration" in warning.message for warning in build_result.report.warnings)
        )

    def test_build_module_from_clang_materializes_union_declarations(self) -> None:
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
        namespace = build_result.module.declarations.namespaces[0]
        union_ = namespace.declarations.classes[0]

        self.assertEqual(len(namespace.declarations.classes), 1)
        self.assertEqual(union_.name, "Storage")
        self.assertEqual(union_.cpp.kind, "union")

    def test_build_module_from_clang_prefers_longer_conflicting_comment_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            active_header = Path(temp_dir) / "demo.hpp"
            active_header.write_text("\n" * 20)
            translation_unit = _fake_translation_unit(
                _fake_cursor(
                    "TRANSLATION_UNIT",
                    "",
                    file=active_header,
                    children=[
                        _fake_cursor(
                            "FUNCTION_DECL",
                            "make_widget",
                            file=active_header,
                            usr="c:@F@make_widget#",
                            line=4,
                        ),
                        _fake_cursor(
                            "FUNCTION_DECL",
                            "make_widget",
                            file=active_header,
                            usr="c:@F@make_widget#",
                            line=8,
                        ),
                    ],
                ),
                tokens=[
                    _fake_comment_token(
                        active_header,
                        "/// Forward declaration note.",
                        start_line=3,
                    ),
                    _fake_comment_token(
                        active_header,
                        "/// Create one widget from the current demo factory state.",
                        start_line=7,
                    ),
                ],
            )

            build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())

            self.assertEqual(len(build_result.module.declarations.functions), 1)
            self.assertEqual(
                build_result.module.declarations.functions[0].cpp.doc.attached_comment,
                "/// Create one widget from the current demo factory state.",
            )
            self.assertEqual(
                build_result.module.declarations.functions[0].cpp.doc.parsed.brief,
                "Create one widget from the current demo factory state.",
            )
            conflict_warnings = [
                warning
                for warning in build_result.report.warnings
                if "Conflicting parsed comments" in warning.message
            ]
            self.assertTrue(conflict_warnings)
            self.assertIsNotNone(conflict_warnings[0].detail)
            self.assertIn("existing parsed comment:", conflict_warnings[0].detail)
            self.assertIn("new parsed comment:", conflict_warnings[0].detail)
            self.assertIn("selected: new", conflict_warnings[0].detail)

    def test_build_module_from_clang_recomputes_structured_doc_after_comment_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            active_header = Path(temp_dir) / "demo.hpp"
            active_header.write_text("\n" * 30)
            translation_unit = _fake_translation_unit(
                _fake_cursor(
                    "TRANSLATION_UNIT",
                    "",
                    file=active_header,
                    children=[
                        _fake_cursor(
                            "FUNCTION_DECL",
                            "make_widget",
                            file=active_header,
                            usr="c:@F@make_widget#I#",
                            line=6,
                            children=[
                                _fake_cursor(
                                    "PARM_DECL",
                                    "value",
                                    file=active_header,
                                    usr="c:@F@make_widget#I#@value",
                                )
                            ],
                        ),
                        _fake_cursor(
                            "FUNCTION_DECL",
                            "make_widget",
                            file=active_header,
                            usr="c:@F@make_widget#I#",
                            line=16,
                            children=[
                                _fake_cursor(
                                    "PARM_DECL",
                                    "value",
                                    file=active_header,
                                    usr="c:@F@make_widget#I#@value",
                                )
                            ],
                        ),
                    ],
                ),
                tokens=[
                    _fake_comment_token(
                        active_header,
                        """
/**
 * Forward declaration docs.
 * @param value Value from the forward declaration.
 */
""".strip(),
                        start_line=2,
                        end_line=5,
                    ),
                    _fake_comment_token(
                        active_header,
                        """
/**
 * Build one widget from the current state.
 * @param value Value from the definition.
 * @return One widget.
 */
""".strip(),
                        start_line=11,
                        end_line=15,
                    ),
                ],
            )

            build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())

            function = build_result.module.declarations.functions[0]
            self.assertEqual(function.cpp.doc.parsed.brief, "Build one widget from the current state.")
            self.assertEqual(function.cpp.doc.parsed.parameters["value"], "Value from the definition.")
            self.assertEqual(function.cpp.doc.parsed.returns, "One widget.")

    def test_build_module_from_clang_raises_for_unresolved_active_type_link(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        missing_declaration_cursor = _fake_cursor(
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
                            _fake_cursor(
                                "FUNCTION_DECL",
                                "take_widget",
                                file=active_header,
                                result_type=_fake_type("VOID", "void"),
                                children=[
                                    _fake_cursor(
                                        "PARM_DECL",
                                        "value",
                                        file=active_header,
                                        type=_fake_type(
                                            "ELABORATED",
                                            "Widget",
                                            declaration_cursor=missing_declaration_cursor,
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    )
                ],
            )
        )

        with self.assertRaisesRegex(ParserInvariantError, "Failed to resolve an internal named-type"):
            build_module_from_clang(translation_unit, [active_header], ParserConfig())

    def test_build_module_from_clang_raises_on_callable_parameter_count_mismatch(self) -> None:
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
                        result_type=_fake_type("INT", "int"),
                    ),
                    _fake_cursor(
                        "FUNCTION_DECL",
                        "make_widget",
                        file=active_header,
                        usr="c:@F@make_widget#",
                        result_type=_fake_type("INT", "int"),
                        children=[
                            _fake_cursor(
                                "PARM_DECL",
                                "value",
                                file=active_header,
                                usr="c:@F@make_widget#@value",
                                type=_fake_type("INT", "int"),
                            )
                        ],
                    ),
                ],
            )
        )

        with self.assertRaisesRegex(ParserInvariantError, "different parameter count"):
            build_module_from_clang(translation_unit, [active_header], ParserConfig())

    def test_build_module_from_clang_raises_when_clang_diagnostics_contain_errors(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        translation_unit = SimpleNamespace(
            cursor=_fake_cursor("TRANSLATION_UNIT", "", file=active_header),
            diagnostics=[
                SimpleNamespace(
                    severity=3,
                    spelling="fatal parse problem",
                    location=SimpleNamespace(
                        file=SimpleNamespace(name=str(active_header)),
                        line=7,
                        column=3,
                    ),
                )
            ],
        )

        with self.assertRaisesRegex(ParserInvariantError, "Refusing to build a semantic model"):
            build_module_from_clang(translation_unit, [active_header], ParserConfig())

    def test_build_module_from_clang_allows_translation_units_without_diagnostics(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        translation_unit = SimpleNamespace(
            cursor=_fake_cursor("TRANSLATION_UNIT", "", file=active_header),
            diagnostics=None,
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())

        self.assertEqual(build_result.module.cpp.header_files, [active_header.resolve()])

    def test_process_variable_cursor_raises_on_unexpected_owner(self) -> None:
        from oroboros.parse import process_cursors

        context = BuildContext(
            active_headers=set(),
            known_project_headers=set(),
            config=ParserConfig(),
        )
        cursor = _fake_cursor(
            "VAR_DECL",
            "local_value",
            file=Path("/tmp/project/demo.hpp"),
            type=_fake_type("INT", "int"),
        )

        with self.assertRaisesRegex(ParserInvariantError, "unexpected semantic owner"):
            process_cursors.process_variable_cursor(cursor, CppEnum(name="Kind"), context)

    def test_build_module_from_clang_records_example_skipped_cursors_when_requested(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        translation_unit = SimpleNamespace(
            cursor=_fake_cursor(
                "TRANSLATION_UNIT",
                "",
                file=active_header,
                children=[
                    _fake_cursor("MACRO_DEFINITION", "DEMO_MACRO", file=active_header),
                ],
            )
        )

        build_result = build_module_from_clang(
            translation_unit,
            [active_header],
            ParserConfig(unsupported_cursor_reporting="examples"),
        )

        warning = build_result.report.warnings[0]
        self.assertEqual(warning.code, "parse.skipped_cursor_kinds")
        self.assertIsNotNone(warning.detail)
        self.assertIn("DEMO_MACRO", warning.detail)

    def test_build_module_from_clang_completes_missing_non_type_observed_template_arguments(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        template_cursor = _fake_cursor(
            "CLASS_TEMPLATE",
            "Box",
            file=active_header,
            usr="c:@ST>1#T@Box",
            tokens=["template", "<", "class", "T", ",", "bool", "is_const", ">", "class", "Box", "{", "}"],
            children=[
                _fake_cursor("TEMPLATE_TYPE_PARAMETER", "T", file=active_header),
                _fake_cursor(
                    "TEMPLATE_NON_TYPE_PARAMETER",
                    "is_const",
                    file=active_header,
                    type=_fake_type("BOOL", "bool"),
                ),
            ],
        )
        specialization_cursor = _fake_cursor(
            "CLASS_DECL",
            "Box",
            file=active_header,
            usr="c:@S@Box>#I#b",
            methods={
                "get_num_template_arguments": 2,
                "get_template_argument_type": lambda index: [
                    _fake_type("INT", "int"),
                    None,
                ][index],
                "get_template_argument_value": lambda index: [0, 1][index],
                "get_template_argument_unsigned_value": lambda index: [0, 1][index],
            },
        )
        specialization_cursor.specialized_template = template_cursor

        translation_unit = SimpleNamespace(
            cursor=_fake_cursor(
                "TRANSLATION_UNIT",
                "",
                file=active_header,
                children=[
                    template_cursor,
                    _fake_cursor(
                        "FUNCTION_DECL",
                        "take_box",
                        file=active_header,
                        result_type=_fake_type("VOID", "void"),
                        children=[
                            _fake_cursor(
                                "PARM_DECL",
                                "value",
                                file=active_header,
                                type=_fake_type(
                                    "UNEXPOSED",
                                    "Box<int>",
                                    template_argument_types=[_fake_type("INT", "int")],
                                    declaration_cursor=specialization_cursor,
                                ),
                            )
                        ],
                    ),
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        hints = build_result.module.declarations.class_templates[0].declaration.cpp.template_observation_hints

        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0].spelling, "Box<int>")

    # ------------------------------------------------------------------
    # Issue 1 – non-callable USR collision

    def test_register_element_for_cursor_warns_on_usr_collision_when_types_differ(self) -> None:
        from oroboros.parse.element_registry import register_element_for_cursor

        active_header = Path("/tmp/project/demo.hpp")
        context = BuildContext(
            active_headers={active_header},
            known_project_headers={active_header},
            config=ParserConfig(),
        )
        cursor = _fake_cursor("CLASS_DECL", "Widget", file=active_header, usr="c:@S@Widget")

        widget = CppClass(name="Widget")
        function = CppFunction(name="Widget")

        register_element_for_cursor(cursor, widget, context)
        register_element_for_cursor(cursor, function, context)

        self.assertIs(context.usr_to_element["c:@S@Widget"], widget)
        self.assertEqual(len(context.report.warnings), 1)
        self.assertEqual(context.report.warnings[0].code, "parse.non_callable_usr_collision")
        self.assertIn("CppClass", context.report.warnings[0].message)
        self.assertIn("CppFunction", context.report.warnings[0].message)

    def test_register_element_for_cursor_warns_on_usr_collision_when_names_differ(self) -> None:
        from oroboros.parse.element_registry import register_element_for_cursor

        active_header = Path("/tmp/project/demo.hpp")
        context = BuildContext(
            active_headers={active_header},
            known_project_headers={active_header},
            config=ParserConfig(),
        )
        cursor = _fake_cursor("CLASS_DECL", "Widget", file=active_header, usr="c:@S@Widget")

        widget_a = CppClass(name="WidgetA")
        widget_b = CppClass(name="WidgetB")

        register_element_for_cursor(cursor, widget_a, context)
        register_element_for_cursor(cursor, widget_b, context)

        self.assertIs(context.usr_to_element["c:@S@Widget"], widget_a)
        self.assertEqual(len(context.report.warnings), 1)
        self.assertEqual(context.report.warnings[0].code, "parse.non_callable_usr_collision")

    def test_element_diagnostic_locations_fall_back_to_template_declaration_locations(self) -> None:
        header = Path("/tmp/project/demo.hpp")
        declaration_location = CppLocationInfo(
            primary=SourceLocation(file=header, line=10, column=2),
            declarations=[SourceLocation(file=header, line=10, column=2)],
            definition=SourceLocation(file=header, line=24, column=7),
        )
        wrappers = [
            CppClassTemplate(
                name="Box",
                declaration=CppClassTemplateDeclaration(
                    name="Box",
                    cpp=CppClassTemplateDeclarationCppFacet(location=declaration_location),
                ),
            ),
            CppFunctionTemplate(
                name="make_box",
                declaration=CppFunctionTemplateDeclaration(
                    name="make_box",
                    cpp=CppFunctionTemplateDeclarationCppFacet(location=declaration_location),
                ),
            ),
            CppMethodTemplate(
                name="convert",
                declaration=CppMethodTemplateDeclaration(
                    name="convert",
                    cpp=CppMethodTemplateDeclarationCppFacet(location=declaration_location),
                ),
            ),
        ]

        for wrapper in wrappers:
            with self.subTest(wrapper=type(wrapper).__name__):
                locations = _element_diagnostic_locations(wrapper)
                self.assertEqual(
                    [(location.file, location.line, location.column) for location in locations],
                    [
                        (header, 10, 2),
                        (header, 24, 7),
                    ],
                )

    def test_build_module_from_clang_merges_function_template_redeclarations_with_same_usr(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        translation_unit = SimpleNamespace(
            cursor=_fake_cursor(
                "TRANSLATION_UNIT",
                "",
                file=active_header,
                children=[
                    _fake_cursor(
                        "FUNCTION_TEMPLATE",
                        "operator>>",
                        file=active_header,
                        usr="c:@F@operator>>",
                        line=10,
                        column=5,
                        children=[
                            _fake_cursor("TEMPLATE_TYPE_PARAMETER", "T", file=active_header, line=10, column=14),
                            _fake_cursor(
                                "PARM_DECL",
                                "deserializer",
                                file=active_header,
                                line=11,
                                column=9,
                                tokens=[
                                    "genesis", "::", "util", "::", "io", "::", "Deserializer", "&", "deserializer",
                                ],
                            ),
                            _fake_cursor(
                                "PARM_DECL",
                                "mat",
                                file=active_header,
                                line=12,
                                column=9,
                                tokens=[
                                    "genesis", "::", "util", "::", "container", "::", "Matrix",
                                    "<", "T", ">", "&", "mat",
                                ],
                            ),
                        ],
                    ),
                    _fake_cursor(
                        "FUNCTION_TEMPLATE",
                        "operator>>",
                        file=active_header,
                        usr="c:@F@operator>>",
                        line=24,
                        column=7,
                        children=[
                            _fake_cursor("TEMPLATE_TYPE_PARAMETER", "T", file=active_header, line=24, column=16),
                            _fake_cursor(
                                "PARM_DECL",
                                "deserializer",
                                file=active_header,
                                line=25,
                                column=9,
                                tokens=[
                                    "genesis", "::", "util", "::", "io", "::", "Deserializer", "&", "deserializer",
                                ],
                            ),
                            _fake_cursor(
                                "PARM_DECL",
                                "mat",
                                file=active_header,
                                line=26,
                                column=9,
                                tokens=["Matrix", "<", "T", ">", "&", "mat"],
                                methods={"is_definition": True},
                            ),
                        ],
                        methods={"is_definition": True},
                    ),
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        function_templates = build_result.module.declarations.function_templates
        self.assertEqual(len(function_templates), 1)
        declaration = function_templates[0].declaration
        self.assertIsNotNone(declaration)
        self.assertEqual(declaration.parameters[0].name, "deserializer")
        self.assertEqual(declaration.parameters[1].name, "mat")
        self.assertEqual(
            [
                (location.file, location.line, location.column)
                for location in declaration.cpp.location.declarations
            ],
            [
                (active_header.resolve(), 10, 5),
                (active_header.resolve(), 24, 7),
            ],
        )
        self.assertEqual(
            [
                diagnostic.code
                for diagnostic in build_result.report.diagnostics
            ],
            [],
        )

    def test_register_element_for_cursor_does_not_warn_when_same_element_reregistered(self) -> None:
        from oroboros.parse.element_registry import register_element_for_cursor

        active_header = Path("/tmp/project/demo.hpp")
        context = BuildContext(
            active_headers={active_header},
            known_project_headers={active_header},
            config=ParserConfig(),
        )
        cursor = _fake_cursor("CLASS_DECL", "Widget", file=active_header, usr="c:@S@Widget")
        widget = CppClass(name="Widget")

        register_element_for_cursor(cursor, widget, context)
        register_element_for_cursor(cursor, widget, context)

        self.assertIs(context.usr_to_element["c:@S@Widget"], widget)
        self.assertEqual(len(context.report.warnings), 0)

    def test_register_element_for_cursor_does_not_warn_when_same_type_and_name_but_different_object(self) -> None:
        from oroboros.parse.element_registry import register_element_for_cursor

        active_header = Path("/tmp/project/demo.hpp")
        context = BuildContext(
            active_headers={active_header},
            known_project_headers={active_header},
            config=ParserConfig(),
        )
        cursor = _fake_cursor("CLASS_DECL", "Widget", file=active_header, usr="c:@S@Widget")

        widget_a = CppClass(name="Widget")
        widget_b = CppClass(name="Widget")

        register_element_for_cursor(cursor, widget_a, context)
        register_element_for_cursor(cursor, widget_b, context)

        self.assertIs(context.usr_to_element["c:@S@Widget"], widget_a)
        self.assertEqual(len(context.report.warnings), 0)

    # ------------------------------------------------------------------
    # Issue 2 – unresolved type link with cursor but no location

    def test_resolve_pending_type_declaration_links_emits_note_for_cursor_without_location(self) -> None:
        from oroboros.parse.build_model import PendingTypeDeclarationLink, _resolve_pending_type_declaration_links
        from types import SimpleNamespace as NS

        context = BuildContext(
            active_headers=set(),
            known_project_headers=set(),
            config=ParserConfig(),
        )
        cursor_no_location = NS(
            kind=CursorKind.CLASS_DECL,
            spelling="Ghost",
            location=NS(file=None, line=0, column=0),
            get_children=lambda: [],
            get_usr=lambda: "c:@S@Ghost",
            semantic_parent=None,
        )
        cpp_type = NamedCppType(name="Ghost")
        context.pending_type_declaration_links.append(
            PendingTypeDeclarationLink(
                cpp_type=cpp_type,
                declaration_usr="c:@S@Ghost",
                declaration_cursor=cursor_no_location,
                declaration_location=None,
                must_resolve_in_active_headers=False,
            )
        )

        _resolve_pending_type_declaration_links(context)

        self.assertIsNone(cpp_type.declaration)
        self.assertEqual(len(context.report.notes), 1)
        self.assertEqual(context.report.notes[0].code, "parse.unresolved_type_declaration_link")
        self.assertIn("Ghost", context.report.notes[0].message)

    def test_resolve_pending_type_declaration_links_does_not_emit_note_without_cursor(self) -> None:
        from oroboros.parse.build_model import PendingTypeDeclarationLink, _resolve_pending_type_declaration_links

        context = BuildContext(
            active_headers=set(),
            known_project_headers=set(),
            config=ParserConfig(),
        )
        cpp_type = NamedCppType(name="External")
        context.pending_type_declaration_links.append(
            PendingTypeDeclarationLink(
                cpp_type=cpp_type,
                declaration_usr="c:@S@External",
                declaration_cursor=None,
                declaration_location=None,
                must_resolve_in_active_headers=False,
            )
        )

        _resolve_pending_type_declaration_links(context)

        self.assertIsNone(cpp_type.declaration)
        self.assertEqual(len(context.report.notes), 0)

    # ------------------------------------------------------------------
    # Issue 3 – unsupported cursor kind in declaration link resolution

    def test_find_direct_declaration_match_emits_note_for_unsupported_cursor_kind(self) -> None:
        from oroboros.parse.element_registry import _find_direct_declaration_match

        active_header = Path("/tmp/project/demo.hpp")
        context = BuildContext(
            active_headers={active_header},
            known_project_headers={active_header},
            config=ParserConfig(),
        )
        owner = CppClass(name="Outer")
        cursor = _fake_cursor("FUNCTION_DECL", "do_something", file=active_header)

        result = _find_direct_declaration_match(owner, cursor, context)

        self.assertIsNone(result)
        self.assertEqual(len(context.report.notes), 1)
        self.assertEqual(context.report.notes[0].code, "parse.declaration_link_unsupported_cursor_kind")
        self.assertIn("FUNCTION_DECL", context.report.notes[0].message)

    def test_find_direct_declaration_match_returns_none_silently_without_context(self) -> None:
        from oroboros.parse.element_registry import _find_direct_declaration_match

        active_header = Path("/tmp/project/demo.hpp")
        owner = CppClass(name="Outer")
        cursor = _fake_cursor("FUNCTION_DECL", "do_something", file=active_header)

        result = _find_direct_declaration_match(owner, cursor)

        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # Issue 5 – no partial clang additions stored on incomplete enrichment

    def test_build_module_from_clang_discards_partial_clang_template_argument_enrichment(self) -> None:
        """Verify that when clang can build arg N1 but not arg N2, neither is stored.

        Before the fix the partial N1 addition was kept even after the break, producing
        an inconsistent [int, N1_value] observation.  Now neither clang-derived arg is
        added; the observation falls back to whatever defaults are available.
        """
        active_header = Path("/tmp/project/demo.hpp")
        template_cursor = _fake_cursor(
            "CLASS_TEMPLATE",
            "Box",
            file=active_header,
            usr="c:@ST>3#T@Box",
            tokens=["template", "<", "class", "T", ",", "int", "N1", ",", "int", "N2", ">", "class", "Box", "{", "}"],
            children=[
                _fake_cursor("TEMPLATE_TYPE_PARAMETER", "T", file=active_header),
                _fake_cursor(
                    "TEMPLATE_NON_TYPE_PARAMETER",
                    "N1",
                    file=active_header,
                    type=_fake_type("INT", "int"),
                ),
                _fake_cursor(
                    "TEMPLATE_NON_TYPE_PARAMETER",
                    "N2",
                    file=active_header,
                    type=_fake_type("INT", "int"),
                ),
            ],
        )
        # Clang sees 3 args: int, N1=5, N2=None (can't determine second non-type arg)
        specialization_cursor = _fake_cursor(
            "CLASS_DECL",
            "Box",
            file=active_header,
            usr="c:@S@Box>#I",
            methods={
                "get_num_template_arguments": 3,
                "get_template_argument_type": lambda index: [
                    _fake_type("INT", "int"),
                    None,
                    None,
                ][index],
                "get_template_argument_value": lambda index: [0, 5, None][index],
                "get_template_argument_unsigned_value": lambda index: [0, 5, None][index],
            },
        )
        specialization_cursor.specialized_template = template_cursor

        translation_unit = SimpleNamespace(
            cursor=_fake_cursor(
                "TRANSLATION_UNIT",
                "",
                file=active_header,
                children=[
                    template_cursor,
                    _fake_cursor(
                        "FUNCTION_DECL",
                        "take_box",
                        file=active_header,
                        result_type=_fake_type("VOID", "void"),
                        children=[
                            _fake_cursor(
                                "PARM_DECL",
                                "value",
                                file=active_header,
                                type=_fake_type(
                                    "UNEXPOSED",
                                    "Box<int>",
                                    template_argument_types=[_fake_type("INT", "int")],
                                    declaration_cursor=specialization_cursor,
                                ),
                            )
                        ],
                    ),
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        hints = build_result.module.declarations.class_templates[0].declaration.cpp.template_observation_hints

        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0].spelling, "Box<int>")

    def test_build_module_from_clang_stores_all_clang_template_arguments_when_all_succeed(self) -> None:
        """Verify the for/else success path still extends complete_arguments."""
        active_header = Path("/tmp/project/demo.hpp")
        template_cursor = _fake_cursor(
            "CLASS_TEMPLATE",
            "Box",
            file=active_header,
            usr="c:@ST>2#T@Box",
            tokens=["template", "<", "class", "T", ",", "int", "N", ">", "class", "Box", "{", "}"],
            children=[
                _fake_cursor("TEMPLATE_TYPE_PARAMETER", "T", file=active_header),
                _fake_cursor(
                    "TEMPLATE_NON_TYPE_PARAMETER",
                    "N",
                    file=active_header,
                    type=_fake_type("INT", "int"),
                ),
            ],
        )
        specialization_cursor = _fake_cursor(
            "CLASS_DECL",
            "Box",
            file=active_header,
            usr="c:@S@Box>#I#7",
            methods={
                "get_num_template_arguments": 2,
                "get_template_argument_type": lambda index: [_fake_type("INT", "int"), None][index],
                "get_template_argument_value": lambda index: [0, 7][index],
                "get_template_argument_unsigned_value": lambda index: [0, 7][index],
            },
        )
        specialization_cursor.specialized_template = template_cursor

        translation_unit = SimpleNamespace(
            cursor=_fake_cursor(
                "TRANSLATION_UNIT",
                "",
                file=active_header,
                children=[
                    template_cursor,
                    _fake_cursor(
                        "FUNCTION_DECL",
                        "take_box",
                        file=active_header,
                        result_type=_fake_type("VOID", "void"),
                        children=[
                            _fake_cursor(
                                "PARM_DECL",
                                "value",
                                file=active_header,
                                type=_fake_type(
                                    "UNEXPOSED",
                                    "Box<int>",
                                    template_argument_types=[_fake_type("INT", "int")],
                                    declaration_cursor=specialization_cursor,
                                ),
                            )
                        ],
                    ),
                ],
            )
        )

        build_result = build_module_from_clang(translation_unit, [active_header], ParserConfig())
        hints = build_result.module.declarations.class_templates[0].declaration.cpp.template_observation_hints

        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0].spelling, "Box<int>")


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
        self.assertIsInstance(cpp_type.canonical.arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(cpp_type.canonical.arguments[0].type, NamedCppType)
        self.assertEqual(cpp_type.canonical.arguments[0].type.name, "std::string")

    def test_record_template_observation_hints_in_type_records_class_template_instantiation_from_specialized_template_views(self) -> None:
        active_header = Path("/tmp/project/demo.hpp")
        context = BuildContext(
            active_headers={active_header},
            known_project_headers={active_header},
            config=ParserConfig(),
        )
        module = CppModule(name="module")
        namespace = module.add_namespace(CppNamespace(name="demo"))
        template = namespace.add_class_template(
            CppClassTemplate(
                name="Box",
                declaration=CppClassTemplateDeclaration(
                    name="Box",
                    cpp=CppClassTemplateDeclarationCppFacet(
                        template_parameters=[CppTypeTemplateParameter(name="T")],
                    ),
                ),
            )
        )
        namespace_cursor = _fake_cursor(
            "NAMESPACE",
            "demo",
            file=active_header,
            usr="c:@N@demo",
        )
        context.usr_to_element[namespace_cursor.get_usr()] = namespace

        specialized_box_cursor = _fake_cursor(
            "CLASS_DECL",
            "Box",
            file=active_header,
            usr="c:@N@demo@S@Box>#I",
            line=10,
        )
        specialized_box_cursor.semantic_parent = namespace_cursor
        specialized_box_cursor.get_specialized_cursor_template = lambda: specialized_box_cursor

        clang_type = _fake_type(
            "ELABORATED",
            "demo::Box<int>",
            declaration_cursor=specialized_box_cursor,
            template_argument_types=[_fake_type("INT", "int")],
        )

        source_cursor = _fake_cursor("TYPE_ALIAS_DECL", "ObservedBox", file=active_header)
        record_template_observation_hints_in_type(
            clang_type,
            context=context,
            source_cursor=source_cursor,
        )

        cpp_type = build_cpp_type(
            clang_type,
            context=context,
            source_cursor=source_cursor,
        )
        self.assertIsInstance(cpp_type, TemplateInstanceCppType)
        self.assertEqual(len(template.declaration.cpp.template_observation_hints), 1)
        hint = template.declaration.cpp.template_observation_hints[0]
        self.assertEqual(hint.spelling, "demo::Box<int>")

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
    storage_class: str | None = None,
    linkage: str | None = None,
    tls_kind: str | None = None,
    tokens: list[str] | None = None,
    methods: dict[str, object] | None = None,
) -> SimpleNamespace:
    start_offset = line * 1000 + column
    end_offset = start_offset + max(1, len(spelling))
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
        storage_class=SimpleNamespace(name=storage_class) if storage_class is not None else None,
        linkage=SimpleNamespace(name=linkage) if linkage is not None else None,
        tls_kind=SimpleNamespace(name=tls_kind) if tls_kind is not None else None,
        raw_comment=raw_comment,
        location=SimpleNamespace(
            file=SimpleNamespace(name=str(file)),
            line=line,
            column=column,
        ),
        extent=SimpleNamespace(
            start=SimpleNamespace(line=line, column=column, offset=start_offset),
            end=SimpleNamespace(line=line, column=column + max(1, len(spelling)), offset=end_offset),
        ),
        get_children=lambda: list(children or []),
        get_tokens=lambda: [SimpleNamespace(spelling=token) for token in (tokens or [])],
        get_usr=lambda: usr,
    )
    for method_name, method_result in (methods or {}).items():
        if callable(method_result):
            setattr(cursor, method_name, method_result)
        else:
            setattr(cursor, method_name, lambda result=method_result: result)
    return cursor


def _fake_translation_unit(cursor: SimpleNamespace, *, tokens: list[SimpleNamespace] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        cursor=cursor,
        get_extent=lambda *args, **kwargs: SimpleNamespace(),
        get_tokens=lambda extent=None: list(tokens or []),
    )


def _fake_comment_token(
    file: Path,
    spelling: str,
    *,
    start_line: int,
    end_line: int | None = None,
    start_column: int = 1,
) -> SimpleNamespace:
    token_end_line = end_line if end_line is not None else start_line
    start_offset = start_line * 1000 + start_column
    end_offset = token_end_line * 1000 + start_column + max(1, len(spelling))
    return SimpleNamespace(
        kind=TokenKind.COMMENT,
        spelling=spelling,
        location=SimpleNamespace(file=SimpleNamespace(name=str(file))),
        extent=SimpleNamespace(
            start=SimpleNamespace(line=start_line, column=start_column, offset=start_offset),
            end=SimpleNamespace(line=token_end_line, column=start_column + max(1, len(spelling)), offset=end_offset),
        ),
    )


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
