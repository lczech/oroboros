from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from oroboros.headers import HeaderFile, HeaderSelection
from oroboros.model import *
from oroboros.parse import ParserConfig, parse_header_selection
from tests.support.parse_helpers import parse_headers_from_sources as _parse_headers_from_sources


class ParseIntegrationDeclarationTest(unittest.TestCase):
    def test_parse_headers_warns_and_avoids_materializing_known_inactive_project_declarations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            inactive_header = temp_path / "detail.hpp"
            active_header = temp_path / "api.hpp"
            inactive_header.write_text(
                """
                    namespace demo {

                    struct Helper {
                        int value {};
                    };

                    }
                """
            )
            active_header.write_text(
                """
                    #include "detail.hpp"

                    namespace demo {

                    struct Widget {
                        Helper helper {};
                    };

                    Helper make_helper(Helper value);

                    }
                """
            )

            result = parse_header_selection(
                HeaderSelection(
                    header_files=[
                        HeaderFile(full_path=active_header, relative_path=Path("api.hpp")),
                        HeaderFile(full_path=inactive_header, relative_path=Path("detail.hpp"), active=False),
                    ]
                ),
                ParserConfig(
                    auto_detect_toolchain=False,
                    cxx_standard="c++20",
                    validate_model=True,
                ),
            )

        namespace = result.module.declarations.namespaces[0]
        widget = next(class_ for class_ in namespace.declarations.classes if class_.name == "Widget")
        make_helper = namespace.declarations.functions[0]

        self.assertEqual([cls.name for cls in namespace.declarations.classes], ["Widget"])
        self.assertIsInstance(widget.declarations.variables[0].cpp.type, NamedCppType)
        self.assertEqual(widget.declarations.variables[0].cpp.type.name, "Helper")
        self.assertIsNone(widget.declarations.variables[0].cpp.type.declaration)
        self.assertIsInstance(make_helper.cpp.return_type, NamedCppType)
        self.assertEqual(make_helper.cpp.return_type.name, "Helper")
        self.assertIsNone(make_helper.cpp.return_type.declaration)
        self.assertIsInstance(make_helper.parameters[0].cpp.type, NamedCppType)
        self.assertEqual(make_helper.parameters[0].cpp.type.name, "Helper")
        self.assertIsNone(make_helper.parameters[0].cpp.type.declaration)
        self.assertTrue(
            any("inactive" in warning.message.lower() for warning in result.report.warnings),
            msg=f"Expected an inactive-header warning, got: {result.report.warnings}",
        )

    def test_parse_headers_materializes_basic_declarations_end_to_end(self) -> None:
        source = """
            namespace demo {

            enum class Realm : unsigned int {
                earth = 1,
            };

            struct Widget {
                Widget() noexcept = default;
                int value;
                int size() const noexcept { return value; }
            };

            bool make_widget() noexcept { return true; }

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        enum_ = namespace.declarations.enums[0]
        cls = namespace.declarations.classes[0]
        function = namespace.declarations.functions[0]

        self.assertEqual(namespace.name, "demo")
        self.assertEqual(enum_.name, "Realm")
        self.assertEqual(enum_.enumerators[0].name, "earth")
        self.assertEqual(cls.name, "Widget")
        self.assertEqual(len(cls.declarations.constructors), 1)
        self.assertEqual(len(cls.declarations.variables), 1)
        self.assertEqual(cls.declarations.variables[0].name, "value")
        self.assertEqual(len(cls.declarations.methods), 1)
        self.assertEqual(cls.declarations.methods[0].name, "size")
        self.assertEqual(function.name, "make_widget")
        self.assertTrue(function.cpp.is_noexcept)

    def test_parse_headers_traverse_linkage_spec_blocks_normally(self) -> None:
        source = """
            extern "C" {
            int c_api(int value) { return value + 1; }
            typedef int c_int;
            int c_counter = 7;
            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        function = result.module.declarations.functions[0]
        alias_ = result.module.declarations.aliases[0]
        variable = result.module.declarations.variables[0]

        self.assertEqual(function.name, "c_api")
        self.assertEqual(function.parameters[0].name, "value")
        self.assertEqual(alias_.name, "c_int")
        self.assertEqual(variable.name, "c_counter")

    def test_parse_headers_traverse_single_linkage_spec_declarations_inside_namespaces(self) -> None:
        source = """
            namespace demo {
            extern "C" int c_api(int value);
            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        function = namespace.declarations.functions[0]

        self.assertEqual(function.name, "c_api")
        self.assertEqual(function.parameters[0].name, "value")

    def test_parse_headers_mark_inline_namespaces(self) -> None:
        source = """
            namespace demo {
            inline namespace v1 {
            int make_widget() { return 1; }
            }
            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        inline_namespace = namespace.declarations.namespaces[0]

        self.assertEqual(namespace.name, "demo")
        self.assertFalse(namespace.cpp.is_inline)
        self.assertEqual(inline_namespace.name, "v1")
        self.assertTrue(inline_namespace.cpp.is_inline)
        self.assertEqual(inline_namespace.declarations.functions[0].name, "make_widget")

    def test_parse_headers_ignore_using_declarations_without_skipped_kind_noise(self) -> None:
        source = """
            namespace detail {
            int helper() { return 1; }
            }

            namespace demo {
            using detail::helper;
            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        detail_namespace = result.module.declarations.namespaces[0]
        demo_namespace = result.module.declarations.namespaces[1]

        self.assertEqual(detail_namespace.name, "detail")
        self.assertEqual(detail_namespace.declarations.functions[0].name, "helper")
        self.assertEqual(demo_namespace.name, "demo")
        self.assertEqual(demo_namespace.declarations.functions, [])

    def test_parse_headers_ignore_non_binding_declaration_kinds_without_skipped_kind_noise(self) -> None:
        source = """
            namespace detail {
            int helper() { return 1; }
            }

            namespace demo {
            namespace detail_alias = detail;
            using namespace detail;
            static_assert(true, "still parse the rest");

            template <class T>
            concept HasSize = requires(T value) {
                value.size();
            };

            int make_widget() { return helper(); }
            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        detail_namespace = result.module.declarations.namespaces[0]
        demo_namespace = result.module.declarations.namespaces[1]

        self.assertEqual(detail_namespace.name, "detail")
        self.assertEqual(demo_namespace.name, "demo")
        self.assertEqual([function.name for function in demo_namespace.declarations.functions], ["make_widget"])

    def test_parse_headers_materialize_coarse_availability_annotations(self) -> None:
        source = """
            namespace demo {

            [[deprecated("use new_api")]]
            int old_api();

            __attribute__((deprecated("use newer_api")))
            int old_gnu();

            struct FreshType {};

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        old_api = namespace.declarations.functions[0]
        old_gnu = namespace.declarations.functions[1]
        fresh_type = namespace.declarations.classes[0]

        self.assertEqual(old_api.cpp.availability, "deprecated")
        self.assertEqual(old_gnu.cpp.availability, "deprecated")
        self.assertEqual(fresh_type.cpp.availability, "available")

    def test_parse_headers_ignore_external_template_explicit_specializations_without_duplicate_classes(self) -> None:
        source = """
            #include <functional>

            namespace demo {
            struct Value {};
            }

            namespace std {
            template <>
            struct hash<demo::Value> {
                std::size_t operator()(demo::Value const&) const { return 0; }
            };
            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        demo_namespace = result.module.declarations.namespaces[0]
        std_namespace = result.module.declarations.namespaces[1]

        self.assertEqual(demo_namespace.name, "demo")
        self.assertEqual(demo_namespace.declarations.classes[0].name, "Value")
        self.assertEqual(std_namespace.name, "std")
        self.assertEqual(std_namespace.declarations.classes, [])
        self.assertEqual(std_namespace.declarations.class_templates, [])
        self.assertFalse(
            any("Explicit class-template specialization" in warning.message for warning in result.report.warnings),
            msg=f"Did not expect std-specialization warning by default, got: {result.report.warnings}",
        )

    def test_parse_headers_optionally_warn_for_std_explicit_specializations(self) -> None:
        source = """
            #include <functional>

            namespace demo {
            struct Value {};
            }

            namespace std {
            template <>
            struct hash<demo::Value> {
                std::size_t operator()(demo::Value const&) const { return 0; }
            };
            }
        """

        result = _parse_headers_from_sources(
            {"demo.hpp": source},
            parser_config=ParserConfig(
                auto_detect_toolchain=False,
                cxx_standard="c++20",
                warn_std_explicit_class_template_specializations=True,
            ),
        )

        self.assertTrue(
            any("Explicit class-template specialization" in warning.message for warning in result.report.warnings),
            msg=f"Expected configurable std-specialization warning, got: {result.report.warnings}",
        )

    def test_parse_headers_materialize_abstract_record_classification(self) -> None:
        source = """
            namespace demo {

            struct Concrete {
                virtual void run();
            };

            struct Abstract {
                virtual void run() = 0;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        concrete = namespace.declarations.classes[0]
        abstract = namespace.declarations.classes[1]

        self.assertFalse(concrete.cpp.is_abstract)
        self.assertTrue(abstract.cpp.is_abstract)

    def test_parse_headers_materialize_abstract_class_template_declarations(self) -> None:
        source = """
            namespace demo {

            template <class T>
            struct AbstractBox {
                virtual void run(T value) = 0;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        abstract_template = namespace.declarations.class_templates[0]

        self.assertEqual(abstract_template.name, "AbstractBox")
        self.assertTrue(abstract_template.declaration.cpp.is_abstract)

    def test_parse_headers_materializes_unions_via_the_class_path(self) -> None:
        source = """
            namespace demo {

            union Storage {
                int count;
                double weight;

                Storage() : count(0) {}
                ~Storage() = default;
                int active_count() const { return count; }
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        union_ = namespace.declarations.classes[0]

        self.assertEqual(union_.name, "Storage")
        self.assertEqual(union_.cpp.kind, "union")
        self.assertEqual(len(union_.declarations.variables), 2)
        self.assertEqual([variable.name for variable in union_.declarations.variables], ["count", "weight"])
        self.assertEqual(len(union_.declarations.constructors), 1)
        self.assertIsNotNone(union_.declarations.destructor)
        self.assertEqual(len(union_.declarations.methods), 1)
        self.assertEqual(union_.declarations.methods[0].name, "active_count")
        self.assertTrue(union_.declarations.methods[0].cpp.is_const)

    def test_parse_headers_preserves_union_comments_and_nested_union_structure(self) -> None:
        source = """
            namespace demo {

            struct Wrapper {
                /// Store one active payload variant.
                union Storage {
                    /// Current element count.
                    int count;
                    /// Current floating payload.
                    double weight;
                };
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        wrapper = result.module.declarations.namespaces[0].declarations.classes[0]
        union_ = wrapper.declarations.classes[0]

        self.assertEqual(union_.cpp.kind, "union")
        self.assertIsNotNone(union_.cpp.attached_comment)
        self.assertIn("Store one active payload variant.", union_.cpp.attached_comment)
        self.assertIsNotNone(union_.cpp.doc)
        self.assertEqual(union_.cpp.doc.brief, "Store one active payload variant.")
        self.assertEqual([variable.name for variable in union_.declarations.variables], ["count", "weight"])
        self.assertIn("Current element count.", union_.declarations.variables[0].cpp.attached_comment)
        self.assertIn("Current floating payload.", union_.declarations.variables[1].cpp.attached_comment)

    def test_parse_headers_materialize_union_templates_as_class_templates(self) -> None:
        source = """
            namespace demo {

            template <class T>
            union Storage {
                T value;
                int tag;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        union_template = namespace.declarations.class_templates[0]

        self.assertEqual(union_template.name, "Storage")
        self.assertEqual(union_template.declaration.cpp.kind, "union")
        self.assertEqual(len(union_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(union_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(union_template.declaration.cpp.template_parameters[0].name, "T")
        self.assertEqual(
            [variable.name for variable in union_template.declaration.declarations.variables],
            ["value", "tag"],
        )

    def test_parse_headers_merge_union_declarations_with_out_of_line_members(self) -> None:
        source = """
            namespace demo {

            union Storage {
                Storage();
                int active_count() const;
                int count;
            };

            Storage::Storage() : count(0) {}

            int Storage::active_count() const {
                return count;
            }

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        union_ = namespace.declarations.classes[0]
        constructor = union_.declarations.constructors[0]
        method = union_.declarations.methods[0]

        self.assertEqual(union_.cpp.kind, "union")
        self.assertEqual(len(namespace.declarations.classes), 1)
        self.assertEqual(len(union_.declarations.constructors), 1)
        self.assertEqual(len(union_.declarations.methods), 1)
        self.assertEqual(constructor.name, "Storage")
        self.assertIsNotNone(constructor.cpp.location.definition)
        self.assertEqual(method.name, "active_count")
        self.assertTrue(method.cpp.is_const)
        self.assertIsNotNone(method.cpp.location.definition)

    def test_parse_headers_preserve_nested_union_visibility(self) -> None:
        source = """
            namespace demo {

            class Vault {
            protected:
                union Storage {
                    int count;
                };
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        vault = result.module.declarations.namespaces[0].declarations.classes[0]
        union_ = vault.declarations.classes[0]

        self.assertEqual(union_.cpp.kind, "union")
        self.assertEqual(union_.cpp.visibility, CppVisibility.PROTECTED)
        self.assertEqual(union_.name, "Storage")
        self.assertEqual(len(union_.declarations.variables), 1)

    def test_parse_headers_links_named_types_and_bases_end_to_end(self) -> None:
        source = """
            namespace demo {

            struct Widget {};

            struct Holder : public Widget {
                void take_widget(const Widget& widget) {}
            };

            Widget make_widget() {
                return Widget{};
            }

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        holder = namespace.declarations.classes[1]
        function = namespace.declarations.functions[0]
        method = holder.declarations.methods[0]

        self.assertIsInstance(function.cpp.return_type, NamedCppType)
        self.assertIs(function.cpp.return_type.declaration, widget)
        self.assertIsInstance(holder.cpp.bases[0].type, NamedCppType)
        self.assertIs(holder.cpp.bases[0].type.declaration, widget)
        self.assertIsInstance(method.parameters[0].cpp.type, LValueReferenceCppType)
        self.assertIsInstance(method.parameters[0].cpp.type.referred, NamedCppType)
        self.assertEqual(method.parameters[0].cpp.type.referred.name, "Widget")
        self.assertTrue(method.parameters[0].cpp.type.referred.is_const)
        self.assertIs(method.parameters[0].cpp.type.referred.declaration, widget)

    def test_parse_headers_reopens_namespaces_across_active_headers(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
                    /// Namespace docs.
                    namespace demo {
                    struct Widget {};
                    }
                """,
                "b.hpp": """
                    namespace demo {
                    int make_widget() { return 1; }
                    }
                """,
            },
            header_order=["a.hpp", "b.hpp"],
        )

        self.assertEqual(len(result.module.declarations.namespaces), 1)
        namespace = result.module.declarations.namespaces[0]
        self.assertEqual(namespace.name, "demo")
        self.assertEqual(len(namespace.cpp.location.declarations), 2)
        self.assertIsNotNone(namespace.cpp.attached_comment)
        self.assertIn("Namespace docs.", namespace.cpp.attached_comment)
        self.assertEqual(len(namespace.declarations.classes), 1)
        self.assertEqual(namespace.declarations.classes[0].name, "Widget")
        self.assertEqual(len(namespace.declarations.functions), 1)
        self.assertEqual(namespace.declarations.functions[0].name, "make_widget")

    def test_parse_headers_merge_forward_declared_classes_with_later_definitions(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
                    namespace demo {

                    /// Forward declaration docs.
                    class Widget;

                    }
                """,
                "b.hpp": """
                    namespace demo {

                    struct Base {};

                    class Widget : public Base {
                    public:
                        int value {};
                    };

                    }
                """,
            },
            header_order=["a.hpp", "b.hpp"],
        )

        namespace = result.module.declarations.namespaces[0]
        base = next(class_ for class_ in namespace.declarations.classes if class_.name == "Base")
        widget = next(class_ for class_ in namespace.declarations.classes if class_.name == "Widget")

        self.assertEqual(len(namespace.declarations.classes), 2)
        self.assertEqual(len(widget.cpp.location.declarations), 2)
        self.assertIsNotNone(widget.cpp.attached_comment)
        self.assertIn("Forward declaration docs.", widget.cpp.attached_comment)
        self.assertEqual(len(widget.cpp.bases), 1)
        self.assertIsInstance(widget.cpp.bases[0].type, NamedCppType)
        self.assertIs(widget.cpp.bases[0].type.declaration, base)
        self.assertEqual(len(widget.declarations.variables), 1)
        self.assertEqual(widget.declarations.variables[0].name, "value")

    def test_parse_headers_merge_anonymous_namespaces_by_semantic_identity(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
                    namespace {
                    struct Widget {};
                    }
                """,
                "b.hpp": """
                    namespace {
                    int make_widget() { return 1; }
                    }
                """,
            },
            header_order=["a.hpp", "b.hpp"],
        )

        self.assertEqual(len(result.module.declarations.namespaces), 1)
        namespace = result.module.declarations.namespaces[0]
        self.assertEqual(namespace.name, "")
        self.assertEqual(len(namespace.cpp.location.declarations), 2)
        self.assertEqual(len(namespace.declarations.classes), 1)
        self.assertEqual(namespace.declarations.classes[0].name, "Widget")
        self.assertEqual(len(namespace.declarations.functions), 1)
        self.assertEqual(namespace.declarations.functions[0].name, "make_widget")

    def test_parse_headers_normalizes_const_named_type_spellings_in_refs_and_pointers(self) -> None:
        source = """
            namespace demo {

            struct Widget {};

            void take_prefix_ref(const Widget& value) {}
            void take_postfix_ref(Widget const& value) {}
            void take_prefix_ptr(const Widget* value) {}
            void take_postfix_ptr(Widget const* value) {}
            void take_const_ptr(Widget* const value) {}
            void take_const_ptr_to_const(Widget const* const value) {}

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        functions = {function.name: function for function in namespace.declarations.functions}

        prefix_ref = functions["take_prefix_ref"].parameters[0].cpp.type
        postfix_ref = functions["take_postfix_ref"].parameters[0].cpp.type
        prefix_ptr = functions["take_prefix_ptr"].parameters[0].cpp.type
        postfix_ptr = functions["take_postfix_ptr"].parameters[0].cpp.type
        const_ptr = functions["take_const_ptr"].parameters[0].cpp.type
        const_ptr_to_const = functions["take_const_ptr_to_const"].parameters[0].cpp.type

        self.assertIsInstance(prefix_ref, LValueReferenceCppType)
        self.assertIsInstance(prefix_ref.referred, NamedCppType)
        self.assertEqual(prefix_ref.referred.name, "Widget")
        self.assertTrue(prefix_ref.referred.is_const)

        self.assertIsInstance(postfix_ref, LValueReferenceCppType)
        self.assertIsInstance(postfix_ref.referred, NamedCppType)
        self.assertEqual(postfix_ref.referred.name, "Widget")
        self.assertTrue(postfix_ref.referred.is_const)

        self.assertIsInstance(prefix_ptr, PointerCppType)
        self.assertFalse(prefix_ptr.is_const)
        self.assertIsInstance(prefix_ptr.pointee, NamedCppType)
        self.assertEqual(prefix_ptr.pointee.name, "Widget")
        self.assertTrue(prefix_ptr.pointee.is_const)

        self.assertIsInstance(postfix_ptr, PointerCppType)
        self.assertFalse(postfix_ptr.is_const)
        self.assertIsInstance(postfix_ptr.pointee, NamedCppType)
        self.assertEqual(postfix_ptr.pointee.name, "Widget")
        self.assertTrue(postfix_ptr.pointee.is_const)

        self.assertIsInstance(const_ptr, PointerCppType)
        self.assertTrue(const_ptr.is_const)
        self.assertIsInstance(const_ptr.pointee, NamedCppType)
        self.assertEqual(const_ptr.pointee.name, "Widget")
        self.assertFalse(const_ptr.pointee.is_const)

        self.assertIsInstance(const_ptr_to_const, PointerCppType)
        self.assertTrue(const_ptr_to_const.is_const)
        self.assertIsInstance(const_ptr_to_const.pointee, NamedCppType)
        self.assertEqual(const_ptr_to_const.pointee.name, "Widget")
        self.assertTrue(const_ptr_to_const.pointee.is_const)

    def test_parse_headers_preserves_alias_and_typedef_spellings(self) -> None:
        source = """
            namespace demo {

            struct Widget {};
            using Alias = Widget;
            typedef Widget WidgetAlias;

            Alias make_alias(Alias value);
            WidgetAlias make_typedef(WidgetAlias value);

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        make_alias = namespace.declarations.functions[0]
        make_typedef = namespace.declarations.functions[1]
        alias = namespace.declarations.aliases[0]
        typedef_alias = namespace.declarations.aliases[1]

        self.assertEqual([alias.name for alias in namespace.declarations.aliases], ["Alias", "WidgetAlias"])
        self.assertEqual(alias.cpp.kind, "using")
        self.assertEqual(typedef_alias.cpp.kind, "typedef")
        self.assertIsInstance(alias.cpp.target, NamedCppType)
        self.assertIs(alias.cpp.target.declaration, widget)
        self.assertIsInstance(typedef_alias.cpp.target, NamedCppType)
        self.assertIs(typedef_alias.cpp.target.declaration, widget)

        self.assertIsInstance(make_alias.cpp.return_type, NamedCppType)
        self.assertEqual(make_alias.cpp.return_type.name, "Alias")
        self.assertIs(make_alias.cpp.return_type.declaration, alias)
        self.assertIsInstance(make_alias.cpp.return_type.canonical, NamedCppType)
        self.assertIs(make_alias.cpp.return_type.canonical.declaration, widget)

        self.assertIsInstance(make_alias.parameters[0].cpp.type, NamedCppType)
        self.assertEqual(make_alias.parameters[0].cpp.type.name, "Alias")
        self.assertIs(make_alias.parameters[0].cpp.type.declaration, alias)
        self.assertIsInstance(make_alias.parameters[0].cpp.type.canonical, NamedCppType)
        self.assertIs(make_alias.parameters[0].cpp.type.canonical.declaration, widget)

        self.assertIsInstance(make_typedef.cpp.return_type, NamedCppType)
        self.assertEqual(make_typedef.cpp.return_type.name, "WidgetAlias")
        self.assertIs(make_typedef.cpp.return_type.declaration, typedef_alias)
        self.assertIsInstance(make_typedef.cpp.return_type.canonical, NamedCppType)
        self.assertIs(make_typedef.cpp.return_type.canonical.declaration, widget)

        self.assertIsInstance(make_typedef.parameters[0].cpp.type, NamedCppType)
        self.assertEqual(make_typedef.parameters[0].cpp.type.name, "WidgetAlias")
        self.assertIs(make_typedef.parameters[0].cpp.type.declaration, typedef_alias)
        self.assertIsInstance(make_typedef.parameters[0].cpp.type.canonical, NamedCppType)
        self.assertIs(make_typedef.parameters[0].cpp.type.canonical.declaration, widget)

    def test_parse_headers_materializes_alias_nodes_with_distinct_scope_and_comments(self) -> None:
        source = """
            namespace demo {

            struct Widget {};

            /** Namespace alias used for handle-style APIs. */
            using WidgetHandle = Widget;

            struct Holder {
                /** Class-local alias used inside holder declarations. */
                using LocalWidget = Widget;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        holder = namespace.declarations.classes[1]
        widget_handle = namespace.declarations.aliases[0]
        local_widget = holder.declarations.aliases[0]

        self.assertIsInstance(widget_handle, CppAlias)
        self.assertEqual(widget_handle.qualified_name, "demo::WidgetHandle")
        self.assertEqual(widget_handle.cpp.kind, "using")
        self.assertIsNotNone(widget_handle.cpp.attached_comment)
        self.assertIn("handle-style APIs", widget_handle.cpp.attached_comment)
        self.assertIsInstance(widget_handle.cpp.target, NamedCppType)
        self.assertIs(widget_handle.cpp.target.declaration, widget)

        self.assertIsInstance(local_widget, CppAlias)
        self.assertEqual(local_widget.qualified_name, "demo::Holder::LocalWidget")
        self.assertEqual(local_widget.cpp.kind, "using")
        self.assertIsNotNone(local_widget.cpp.attached_comment)
        self.assertIn("holder declarations", local_widget.cpp.attached_comment)
        self.assertIsInstance(local_widget.cpp.target, NamedCppType)
        self.assertIs(local_widget.cpp.target.declaration, widget)

    def test_parse_headers_preserves_alias_heavy_public_api_surfaces(self) -> None:
        source = """
            namespace demo {

            struct Widget {
                using SizeType = unsigned long;
            };

            using WidgetHandle = Widget;
            using WidgetAlias = WidgetHandle;

            WidgetAlias take_widget(WidgetHandle value);
            Widget::SizeType measure(WidgetAlias value);

            struct Holder {
                using PublicHandle = WidgetAlias;
                PublicHandle value;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        widget_handle = namespace.alias["WidgetHandle"]
        widget_alias = namespace.alias["WidgetAlias"]
        holder = namespace.class_["Holder"]
        take_widget = namespace.function["take_widget"][0]
        measure = namespace.function["measure"][0]

        self.assertIsInstance(widget_handle.cpp.target, NamedCppType)
        self.assertIs(widget_handle.cpp.target.declaration, widget)
        self.assertIsInstance(widget_alias.cpp.target, NamedCppType)
        self.assertEqual(widget_alias.cpp.target.name, "WidgetHandle")
        self.assertIs(widget_alias.cpp.target.declaration, widget_handle)
        self.assertIsInstance(take_widget.cpp.return_type, NamedCppType)
        self.assertEqual(take_widget.cpp.return_type.name, "WidgetAlias")
        self.assertIs(take_widget.cpp.return_type.declaration, widget_alias)
        self.assertIsInstance(take_widget.parameters[0].cpp.type, NamedCppType)
        self.assertEqual(take_widget.parameters[0].cpp.type.name, "WidgetHandle")
        self.assertIs(take_widget.parameters[0].cpp.type.declaration, widget_handle)
        self.assertIsInstance(measure.cpp.return_type, NamedCppType)
        self.assertEqual(measure.cpp.return_type.name, "Widget::SizeType")
        self.assertIs(measure.cpp.return_type.declaration, widget.alias["SizeType"])
        self.assertIsInstance(measure.parameters[0].cpp.type, NamedCppType)
        self.assertEqual(measure.parameters[0].cpp.type.name, "WidgetAlias")
        self.assertIs(measure.parameters[0].cpp.type.declaration, widget_alias)
        self.assertIsInstance(holder.alias["PublicHandle"].cpp.target, NamedCppType)
        self.assertEqual(holder.alias["PublicHandle"].cpp.target.name, "WidgetAlias")
        self.assertIs(holder.alias["PublicHandle"].cpp.target.declaration, widget_alias)
        self.assertIsInstance(holder.declarations.variables[0].cpp.type, NamedCppType)
        self.assertEqual(holder.declarations.variables[0].cpp.type.name, "PublicHandle")
        self.assertIs(holder.declarations.variables[0].cpp.type.declaration, holder.alias["PublicHandle"])

    def test_parse_headers_materialize_free_and_static_variables_and_ignore_locals(self) -> None:
        source = """
            namespace demo {

            inline int global_count = 1;
            static int internal_count = 2;
            thread_local int tls_count = 3;
            constexpr int answer = 42;

            struct Widget {
                static int instance_count;
                int value {0};

                int size() const {
                    int local_count = value;
                    return local_count;
                }
            };

            int Widget::instance_count = 0;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        method = widget.declarations.methods[0]

        self.assertEqual(
            [variable.name for variable in namespace.declarations.variables],
            ["global_count", "internal_count", "tls_count", "answer"],
        )
        self.assertEqual(
            [variable.cpp.kind for variable in namespace.declarations.variables],
            ["variable", "variable", "variable", "variable"],
        )
        by_name = {variable.name: variable for variable in namespace.declarations.variables}
        self.assertEqual(by_name["internal_count"].cpp.storage_class, "static")
        self.assertEqual(by_name["internal_count"].cpp.linkage, "internal")
        self.assertEqual(by_name["tls_count"].cpp.tls_kind, "dynamic")
        self.assertTrue(by_name["answer"].cpp.is_const)
        self.assertEqual([variable.name for variable in widget.declarations.variables], ["value"])
        self.assertEqual(widget.declarations.variables[0].cpp.kind, "member_variable")
        self.assertEqual([variable.name for variable in widget.declarations.static_variables], ["instance_count"])
        self.assertEqual(widget.declarations.static_variables[0].cpp.kind, "static_member_variable")
        self.assertEqual(method.element_names, [])

    def test_parse_headers_preserves_scope_relative_named_type_spellings(self) -> None:
        source = """
            namespace demo {

            namespace types {
            enum class OmenKind : unsigned int {
                bright = 1,
            };
            }

            struct Holder {
                types::OmenKind kind;
                types::OmenKind reveal(types::OmenKind value) const { return value; }
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        omen_kind = namespace.declarations.namespaces[0].declarations.enums[0]
        holder = namespace.declarations.classes[0]
        field_type = holder.declarations.variables[0].cpp.type
        method = holder.declarations.methods[0]

        self.assertIsInstance(field_type, NamedCppType)
        self.assertEqual(field_type.name, "types::OmenKind")
        self.assertIs(field_type.declaration, omen_kind)

        self.assertIsInstance(method.cpp.return_type, NamedCppType)
        self.assertEqual(method.cpp.return_type.name, "types::OmenKind")
        self.assertIs(method.cpp.return_type.declaration, omen_kind)

        self.assertIsInstance(method.parameters[0].cpp.type, NamedCppType)
        self.assertEqual(method.parameters[0].cpp.type.name, "types::OmenKind")
        self.assertIs(method.parameters[0].cpp.type.declaration, omen_kind)

    def test_parse_headers_materializes_real_array_function_pointer_and_nested_template_types(self) -> None:
        source = """
            namespace demo {

            struct Widget {};
            template <class T> struct Box {};
            template <class A, class B> struct Pair {};

            void take_values(int values[4]) {}
            void take_callback(void (*callback)(int, bool)) {}
            void take_nested(Box<Pair<int, Widget>> value) {}

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        functions = {function.name: function for function in namespace.declarations.functions}
        widget = namespace.declarations.classes[0]

        values_type = functions["take_values"].parameters[0].cpp.type
        callback_type = functions["take_callback"].parameters[0].cpp.type
        nested_type = functions["take_nested"].parameters[0].cpp.type

        self.assertIsInstance(values_type, ArrayCppType)
        self.assertEqual(values_type.extent, "4")
        self.assertIsInstance(values_type.element_type, BuiltinCppType)
        self.assertEqual(values_type.element_type.kind, "int")

        self.assertIsInstance(callback_type, PointerCppType)
        self.assertIsInstance(callback_type.pointee, FunctionCppType)
        self.assertIsInstance(callback_type.pointee.return_type, BuiltinCppType)
        self.assertEqual(callback_type.pointee.return_type.kind, "void")
        self.assertEqual(len(callback_type.pointee.parameters), 2)
        self.assertIsInstance(callback_type.pointee.parameters[0], BuiltinCppType)
        self.assertEqual(callback_type.pointee.parameters[0].kind, "int")
        self.assertIsInstance(callback_type.pointee.parameters[1], BuiltinCppType)
        self.assertEqual(callback_type.pointee.parameters[1].kind, "bool")

        self.assertIsInstance(nested_type, TemplateInstanceCppType)
        self.assertEqual(nested_type.template_name, "Box")
        self.assertEqual(len(nested_type.arguments), 1)
        self.assertIsInstance(nested_type.arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(nested_type.arguments[0].type, TemplateInstanceCppType)
        self.assertEqual(nested_type.arguments[0].type.template_name, "Pair")
        self.assertEqual(len(nested_type.arguments[0].type.arguments), 2)
        self.assertIsInstance(nested_type.arguments[0].type.arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(nested_type.arguments[0].type.arguments[0].type, BuiltinCppType)
        self.assertEqual(nested_type.arguments[0].type.arguments[0].type.kind, "int")
        self.assertIsInstance(nested_type.arguments[0].type.arguments[1], CppTypeTemplateArgument)
        self.assertIsInstance(nested_type.arguments[0].type.arguments[1].type, NamedCppType)
        self.assertEqual(nested_type.arguments[0].type.arguments[1].type.name, "Widget")
        self.assertIs(nested_type.arguments[0].type.arguments[1].type.declaration, widget)

    def test_parse_headers_preserve_callback_typedef_links_and_canonical_function_pointer_types(self) -> None:
        source = """
            namespace demo {

            typedef void (*Callback)(int, bool);

            struct Holder {
                Callback callback;
            };

            Callback get_callback();
            void install_callback(Callback callback) {}

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        callback_alias = namespace.declarations.aliases[0]
        holder = namespace.declarations.classes[0]
        functions = {function.name: function for function in namespace.declarations.functions}

        self.assertIsInstance(callback_alias.cpp.target, PointerCppType)
        self.assertIsInstance(callback_alias.cpp.target.pointee, FunctionCppType)
        self.assertEqual(callback_alias.cpp.target.render(), "void (*)(int, bool)")

        field_type = holder.declarations.variables[0].cpp.type
        self.assertIsInstance(field_type, NamedCppType)
        self.assertEqual(field_type.name, "Callback")
        self.assertIs(field_type.declaration, callback_alias)
        self.assertIsInstance(field_type.canonical, PointerCppType)
        self.assertEqual(field_type.canonical.render(), "void (*)(int, bool)")

        return_type = functions["get_callback"].cpp.return_type
        self.assertIsInstance(return_type, NamedCppType)
        self.assertEqual(return_type.name, "Callback")
        self.assertIs(return_type.declaration, callback_alias)
        self.assertIsInstance(return_type.canonical, PointerCppType)
        self.assertEqual(return_type.canonical.render(), "void (*)(int, bool)")

        parameter_type = functions["install_callback"].parameters[0].cpp.type
        self.assertIsInstance(parameter_type, NamedCppType)
        self.assertEqual(parameter_type.name, "Callback")
        self.assertIs(parameter_type.declaration, callback_alias)
        self.assertIsInstance(parameter_type.canonical, PointerCppType)
        self.assertEqual(parameter_type.canonical.render(), "void (*)(int, bool)")

    def test_parse_headers_materialize_bitfield_and_mutable_field_traits(self) -> None:
        source = """
            namespace demo {

            struct Holder {
                mutable int cache;
                unsigned mode : 3;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        holder = result.module.declarations.namespaces[0].declarations.classes[0]
        cache = holder.declarations.variables[0]
        mode = holder.declarations.variables[1]

        self.assertFalse(cache.cpp.is_bitfield)
        self.assertIsNone(cache.cpp.bitfield_width)
        self.assertTrue(cache.cpp.is_mutable)

        self.assertTrue(mode.cpp.is_bitfield)
        self.assertEqual(mode.cpp.bitfield_width, 3)
        self.assertFalse(mode.cpp.is_mutable)
