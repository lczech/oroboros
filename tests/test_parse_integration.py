from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from oroboros.headers import HeaderFile, HeaderSelection
from oroboros.model import (
    ArrayCppType,
    BuiltinCppType,
    CppAlias,
    CppClassTemplate,
    CppFunctionTemplate,
    CppNonTypeTemplateArgument,
    CppNonTypeTemplateParameter,
    CppTemplateTemplateParameter,
    CppTypeTemplateArgument,
    CppTypeTemplateParameter,
    CppVisibility,
    FunctionCppType,
    LValueReferenceCppType,
    NamedCppType,
    PointerCppType,
    TemplateInstanceCppType,
)
from oroboros.parse import ParserConfig, parse_header_selection


class ParseIntegrationTest(unittest.TestCase):
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
            any("inactive" in warning.lower() for warning in result.warnings),
            msg=f"Expected an inactive-header warning, got: {result.warnings}",
        )

    def test_parse_headers_materializes_real_template_declarations(self) -> None:
        source = """
namespace demo {

template <class T, int N, template <class> class Wrapper>
struct Box {
    T value;
};

template <class T>
T make_value(T value) {
    return value;
}

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        class_template = namespace.declarations.class_templates[0]
        function_template = namespace.declarations.function_templates[0]

        self.assertIsInstance(class_template, CppClassTemplate)
        self.assertEqual(class_template.name, "Box")
        self.assertEqual(class_template.qualified_name, "demo::Box")
        self.assertEqual(class_template.declaration.qualified_name, "demo::Box")
        self.assertEqual(len(class_template.declaration.cpp.template_parameters), 3)
        self.assertIsInstance(class_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(class_template.declaration.cpp.template_parameters[0].name, "T")
        self.assertIsInstance(class_template.declaration.cpp.template_parameters[1], CppNonTypeTemplateParameter)
        self.assertEqual(class_template.declaration.cpp.template_parameters[1].name, "N")
        self.assertIsInstance(class_template.declaration.cpp.template_parameters[1].type, BuiltinCppType)
        self.assertEqual(class_template.declaration.cpp.template_parameters[1].type.kind, "int")
        self.assertIsInstance(class_template.declaration.cpp.template_parameters[2], CppTemplateTemplateParameter)
        self.assertEqual(class_template.declaration.cpp.template_parameters[2].name, "Wrapper")
        self.assertEqual(len(class_template.declaration.cpp.template_parameters[2].parameters), 1)
        self.assertIsInstance(class_template.declaration.cpp.template_parameters[2].parameters[0], CppTypeTemplateParameter)
        self.assertEqual(class_template.declaration.cpp.template_parameters[2].parameters[0].name, "")
        self.assertEqual(len(class_template.declaration.declarations.variables), 1)
        self.assertEqual(class_template.declaration.declarations.variables[0].name, "value")

        self.assertIsInstance(function_template, CppFunctionTemplate)
        self.assertEqual(function_template.name, "make_value")
        self.assertEqual(function_template.qualified_name, "demo::make_value")
        self.assertEqual(function_template.declaration.qualified_name, "demo::make_value")
        self.assertEqual(len(function_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(function_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(function_template.declaration.cpp.template_parameters[0].name, "T")
        self.assertEqual(len(function_template.declaration.parameters), 1)
        self.assertEqual(function_template.declaration.parameters[0].name, "value")
        self.assertIsInstance(function_template.declaration.cpp.return_type, NamedCppType)
        self.assertEqual(function_template.declaration.cpp.return_type.name, "T")

    def test_parse_headers_materializes_structured_template_features_end_to_end(self) -> None:
        source = """
#include <array>

namespace demo::types {

struct RelicInfo {
    int power {0};
};

template <class T>
struct Reliquary {
    T value {};
};

using RelicQuartet = std::array<RelicInfo, 4>;
using ReliquaryShelf = Reliquary<RelicQuartet>;

}  // namespace demo::types

namespace demo::functions {

template <class T>
T echo_prophecy(T value) {
    return value;
}

types::Reliquary<types::RelicInfo> bless_reliquary(types::RelicInfo relic);

}  // namespace demo::functions
"""

        result = _parse_headers_from_sources(
            {"demo.hpp": source},
            parser_config=ParserConfig(
                cxx_standard="c++20",
                auto_detect_toolchain=False,
                validate_model=True,
            ),
        )

        root_namespace = result.module.declarations.namespaces[0]
        types_namespace = root_namespace.declarations.namespaces[0]
        functions_namespace = root_namespace.declarations.namespaces[1]

        class_template = types_namespace.declarations.class_templates[0]
        self.assertIsInstance(class_template, CppClassTemplate)
        self.assertEqual(class_template.name, "Reliquary")
        self.assertEqual(len(class_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(class_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(class_template.declaration.cpp.template_parameters[0].name, "T")
        self.assertEqual(len(class_template.declaration.declarations.variables), 1)
        self.assertEqual(class_template.declaration.declarations.variables[0].name, "value")

        relic_quartet = types_namespace.alias["RelicQuartet"]
        self.assertIsInstance(relic_quartet, CppAlias)
        self.assertIsInstance(relic_quartet.cpp.target, TemplateInstanceCppType)
        self.assertEqual(relic_quartet.cpp.target.template_name, "std::array")
        self.assertEqual(len(relic_quartet.cpp.target.arguments), 2)
        self.assertIsInstance(relic_quartet.cpp.target.arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(relic_quartet.cpp.target.arguments[0].type, NamedCppType)
        self.assertEqual(relic_quartet.cpp.target.arguments[0].type.name, "RelicInfo")
        self.assertIsInstance(relic_quartet.cpp.target.arguments[1], CppNonTypeTemplateArgument)
        self.assertEqual(relic_quartet.cpp.target.arguments[1].value, "4")

        reliquary_shelf = types_namespace.alias["ReliquaryShelf"]
        self.assertIsInstance(reliquary_shelf.cpp.target, TemplateInstanceCppType)
        self.assertEqual(reliquary_shelf.cpp.target.template_name, "Reliquary")
        self.assertEqual(len(reliquary_shelf.cpp.target.arguments), 1)
        self.assertIsInstance(reliquary_shelf.cpp.target.arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(reliquary_shelf.cpp.target.arguments[0].type, NamedCppType)
        self.assertEqual(reliquary_shelf.cpp.target.arguments[0].type.name, "RelicQuartet")
        self.assertIs(reliquary_shelf.cpp.target.arguments[0].type.declaration, relic_quartet)

        function_template = functions_namespace.declarations.function_templates[0]
        self.assertIsInstance(function_template, CppFunctionTemplate)
        self.assertEqual(function_template.name, "echo_prophecy")
        self.assertEqual(len(function_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(function_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(function_template.declaration.cpp.template_parameters[0].name, "T")
        self.assertEqual(len(function_template.declaration.parameters), 1)
        self.assertEqual(function_template.declaration.parameters[0].name, "value")
        self.assertIsInstance(function_template.declaration.cpp.return_type, NamedCppType)
        self.assertEqual(function_template.declaration.cpp.return_type.name, "T")

        bless_reliquary = functions_namespace.declarations.functions[0]
        self.assertEqual(bless_reliquary.name, "bless_reliquary")
        self.assertIsInstance(bless_reliquary.cpp.return_type, TemplateInstanceCppType)
        self.assertEqual(bless_reliquary.cpp.return_type.template_name, "types::Reliquary")
        self.assertEqual(len(bless_reliquary.cpp.return_type.arguments), 1)
        self.assertIsInstance(bless_reliquary.cpp.return_type.arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(bless_reliquary.cpp.return_type.arguments[0].type, NamedCppType)
        self.assertEqual(bless_reliquary.cpp.return_type.arguments[0].type.name, "types::RelicInfo")

    def test_parse_headers_collects_observed_class_template_instances_from_declaration_types(self) -> None:
        source = """
namespace demo {

struct RelicInfo {};

template <class T>
struct Box {
    T value {};
};

using RelicBox = Box<RelicInfo>;

struct Holder {
    Box<RelicInfo> primary;
};

Box<RelicInfo> make_box();

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        box_template = namespace.declarations.class_templates[0]
        observed_instances = box_template.declaration.cpp.observed_instances

        self.assertEqual(len(observed_instances), 1)
        self.assertEqual(len(observed_instances[0].locations), 3)
        self.assertIsInstance(observed_instances[0].arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(observed_instances[0].arguments[0].type, NamedCppType)
        self.assertEqual(observed_instances[0].arguments[0].type.name, "RelicInfo")

    def test_parse_headers_completes_observed_instances_with_defaulted_trailing_type_arguments(self) -> None:
        source = """
namespace demo {

template <class T, class U = double>
struct Box {
    T value {};
    U scale {};
};

using IntBox = Box<int>;

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        box_template = namespace.declarations.class_templates[0]
        observed_instances = box_template.declaration.cpp.observed_instances

        self.assertEqual(len(observed_instances), 1)
        self.assertEqual(len(observed_instances[0].arguments), 2)
        self.assertIsInstance(observed_instances[0].arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(observed_instances[0].arguments[0].type, BuiltinCppType)
        self.assertEqual(observed_instances[0].arguments[0].type.kind, "int")
        self.assertIsInstance(observed_instances[0].arguments[1], CppTypeTemplateArgument)
        self.assertIsInstance(observed_instances[0].arguments[1].type, BuiltinCppType)
        self.assertEqual(observed_instances[0].arguments[1].type.kind, "double")

    def test_parse_headers_deduplicates_observed_instances_with_implicit_and_explicit_defaults(self) -> None:
        source = """
namespace demo {

template <class T, class U = double>
struct Box {
    T value {};
    U scale {};
};

using IntBox = Box<int>;
using ExplicitIntBox = Box<int, double>;

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        box_template = namespace.declarations.class_templates[0]
        observed_instances = box_template.declaration.cpp.observed_instances

        self.assertEqual(len(observed_instances), 1)
        self.assertEqual(len(observed_instances[0].locations), 2)
        self.assertEqual(len(observed_instances[0].arguments), 2)
        self.assertIsInstance(observed_instances[0].arguments[0].type, BuiltinCppType)
        self.assertEqual(observed_instances[0].arguments[0].type.kind, "int")
        self.assertIsInstance(observed_instances[0].arguments[1].type, BuiltinCppType)
        self.assertEqual(observed_instances[0].arguments[1].type.kind, "double")

    def test_parse_headers_collects_observed_instances_through_reference_wrappers(self) -> None:
        source = """
namespace demo {

template <class T>
struct Box {
    T value {};
};

void take_box(Box<int> const& box);

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        box_template = namespace.declarations.class_templates[0]
        observed_instances = box_template.declaration.cpp.observed_instances

        self.assertEqual(len(observed_instances), 1)
        self.assertEqual(len(observed_instances[0].locations), 1)
        self.assertEqual(len(observed_instances[0].arguments), 1)
        self.assertIsInstance(observed_instances[0].arguments[0].type, BuiltinCppType)
        self.assertEqual(observed_instances[0].arguments[0].type.kind, "int")

    def test_parse_headers_collects_observed_instances_through_pointer_wrappers(self) -> None:
        source = """
namespace demo {

template <class T>
struct Box {
    T value {};
};

Box<int>* make_box_ptr();

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        box_template = namespace.declarations.class_templates[0]
        observed_instances = box_template.declaration.cpp.observed_instances

        self.assertEqual(len(observed_instances), 1)
        self.assertEqual(len(observed_instances[0].locations), 1)
        self.assertEqual(len(observed_instances[0].arguments), 1)
        self.assertIsInstance(observed_instances[0].arguments[0].type, BuiltinCppType)
        self.assertEqual(observed_instances[0].arguments[0].type.kind, "int")

    def test_parse_headers_collects_nested_observed_instances(self) -> None:
        source = """
namespace demo {

template <class T>
struct Box {
    T value {};
};

template <class T>
struct Holder {
    T value {};
};

using NestedHolder = Holder<Box<int>>;

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        box_template = namespace.declarations.class_templates[0]
        holder_template = namespace.declarations.class_templates[1]

        self.assertEqual(len(box_template.declaration.cpp.observed_instances), 1)
        self.assertEqual(len(holder_template.declaration.cpp.observed_instances), 1)
        self.assertIsInstance(
            box_template.declaration.cpp.observed_instances[0].arguments[0].type,
            BuiltinCppType,
        )
        self.assertEqual(
            box_template.declaration.cpp.observed_instances[0].arguments[0].type.kind,
            "int",
        )

    def test_parse_headers_preserves_alias_chains_around_template_instances(self) -> None:
        source = """
namespace demo {

template <class T>
struct Box {
    T value {};
};

using IntBox = Box<int>;
using IntBoxAlias = IntBox;

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        box_template = namespace.declarations.class_templates[0]
        int_box = namespace.alias["IntBox"]
        int_box_alias = namespace.alias["IntBoxAlias"]

        self.assertEqual(len(box_template.declaration.cpp.observed_instances), 1)
        self.assertIsInstance(int_box.cpp.target, TemplateInstanceCppType)
        self.assertEqual(int_box.cpp.target.template_name, "Box")
        self.assertIsInstance(int_box_alias.cpp.target, NamedCppType)
        self.assertEqual(int_box_alias.cpp.target.name, "IntBox")
        self.assertIs(int_box_alias.cpp.target.declaration, int_box)

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

    def test_parse_headers_merges_redeclared_callable_parameters_by_position(self) -> None:
        source = """
namespace demo {

int make_widget(int value);
int make_widget(int request) {
    return request;
}

struct Widget {
    void resize(int amount) const;
};

void Widget::resize(int size) const {}

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        function = namespace.declarations.functions[0]
        method = namespace.declarations.classes[0].declarations.methods[0]

        self.assertEqual(len(function.parameters), 1)
        self.assertEqual(function.parameters[0].name, "value")
        self.assertEqual(len(method.parameters), 1)
        self.assertEqual(method.parameters[0].name, "amount")

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
        self.assertIsNotNone(namespace.cpp.comment)
        self.assertIn("Namespace docs.", namespace.cpp.comment)
        self.assertEqual(len(namespace.declarations.classes), 1)
        self.assertEqual(namespace.declarations.classes[0].name, "Widget")
        self.assertEqual(len(namespace.declarations.functions), 1)
        self.assertEqual(namespace.declarations.functions[0].name, "make_widget")

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
        self.assertIsNotNone(widget_handle.cpp.comment)
        self.assertIn("handle-style APIs", widget_handle.cpp.comment)
        self.assertIsInstance(widget_handle.cpp.target, NamedCppType)
        self.assertIs(widget_handle.cpp.target.declaration, widget)

        self.assertIsInstance(local_widget, CppAlias)
        self.assertEqual(local_widget.qualified_name, "demo::Holder::LocalWidget")
        self.assertEqual(local_widget.cpp.kind, "using")
        self.assertIsNotNone(local_widget.cpp.comment)
        self.assertIn("holder declarations", local_widget.cpp.comment)
        self.assertIsInstance(local_widget.cpp.target, NamedCppType)
        self.assertIs(local_widget.cpp.target.declaration, widget)

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

    def test_parse_headers_extracts_real_visibility_and_callable_flags(self) -> None:
        source = """
namespace demo {

class Widget {
public:
    Widget() noexcept = default;
    virtual void render() = 0;

protected:
    int cache_size;
    static void warmup() noexcept {}

private:
    int size() const noexcept { return cache_size; }
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        widget = result.module.declarations.namespaces[0].declarations.classes[0]
        constructor = widget.declarations.constructors[0]
        render = widget.declarations.methods[0]
        warmup = widget.declarations.methods[1]
        size = widget.declarations.methods[2]
        cache_size = widget.declarations.variables[0]

        self.assertEqual(constructor.cpp.visibility, CppVisibility.PUBLIC)
        self.assertTrue(constructor.cpp.is_noexcept)

        self.assertEqual(render.cpp.visibility, CppVisibility.PUBLIC)
        self.assertTrue(render.cpp.is_virtual)
        self.assertTrue(render.cpp.is_pure_virtual)
        self.assertFalse(render.cpp.is_static)
        self.assertFalse(render.cpp.is_const)

        self.assertEqual(warmup.cpp.visibility, CppVisibility.PROTECTED)
        self.assertTrue(warmup.cpp.is_static)
        self.assertTrue(warmup.cpp.is_noexcept)
        self.assertFalse(warmup.cpp.is_virtual)

        self.assertEqual(size.cpp.visibility, CppVisibility.PRIVATE)
        self.assertTrue(size.cpp.is_const)
        self.assertTrue(size.cpp.is_noexcept)
        self.assertFalse(size.cpp.is_static)

        self.assertEqual(cache_size.cpp.visibility, CppVisibility.PROTECTED)
        self.assertEqual(cache_size.cpp.kind, "member_variable")

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

    def test_parse_headers_merges_redeclared_constructor_parameters_by_position(self) -> None:
        source = """
namespace demo {

struct Widget {
    Widget(int value);
};

Widget::Widget(int amount) {}

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        constructor = result.module.declarations.namespaces[0].declarations.classes[0].declarations.constructors[0]

        self.assertEqual(len(constructor.parameters), 1)
        self.assertEqual(constructor.parameters[0].name, "value")

    def test_parse_headers_normalizes_constructor_names_inside_class_templates(self) -> None:
        source = """
namespace demo {

template <class T>
class MyClass {
public:
    explicit MyClass(T const& value)
        : t(value)
    {}

private:
    T t;
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        class_template = result.module.declarations.namespaces[0].declarations.class_templates[0]
        constructor = class_template.declaration.declarations.constructors[0]

        self.assertEqual(class_template.name, "MyClass")
        self.assertEqual(constructor.name, "MyClass")
        self.assertEqual(constructor.cpp.original_name, "MyClass")
        self.assertEqual(len(constructor.parameters), 1)
        self.assertEqual(constructor.parameters[0].name, "value")
        self.assertTrue(constructor.cpp.is_explicit)

    def test_parse_headers_populates_parameter_default_values_across_callables(self) -> None:
        source = """
namespace demo {

enum class Mode {
    fast,
};

struct Config {};

Config make_config();

template <class T>
struct Box {};

Mode make_mode(
    Mode mode = Mode::fast,
    Config cfg = make_config()
);

template <class T>
T make_value(T value = T{});

struct Widget {
    explicit Widget(Box<int> box = Box<int>{});

    void run(
        int count = -1,
        void* ptr = nullptr
    );

    template <class U>
    explicit Widget(
        U value = U{},
        Mode mode = Mode::fast
    );
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        free_function = namespace.declarations.functions[1]
        function_template = namespace.declarations.function_templates[0]
        widget = next(class_ for class_ in namespace.declarations.classes if class_.name == "Widget")
        constructor = widget.declarations.constructors[0]
        method = widget.declarations.methods[0]
        templated_constructor = widget.declarations.constructors[1]

        self.assertEqual(free_function.name, "make_mode")
        self.assertEqual(free_function.parameters[0].cpp.default_value, "Mode::fast")
        self.assertEqual(free_function.parameters[1].cpp.default_value, "make_config()")

        self.assertEqual(function_template.declaration.parameters[0].cpp.default_value, "T{}")

        self.assertEqual(constructor.parameters[0].cpp.default_value, "Box<int>{}")
        self.assertTrue(constructor.cpp.is_explicit)

        self.assertEqual(method.parameters[0].cpp.default_value, "-1")
        self.assertEqual(method.parameters[1].cpp.default_value, "nullptr")

        self.assertEqual(templated_constructor.parameters[0].cpp.default_value, "U{}")
        self.assertEqual(templated_constructor.parameters[1].cpp.default_value, "Mode::fast")
        self.assertTrue(templated_constructor.cpp.is_explicit)

    def test_parse_headers_treats_explicit_expression_specifiers_as_explicit(self) -> None:
        source = """
namespace demo {

struct Widget {
    explicit Widget(int value);
    explicit(true) Widget(char value);
    explicit(false) Widget(short value);
    explicit(sizeof(int) == 4) Widget(double value);
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        constructors = result.module.declarations.namespaces[0].declarations.classes[0].declarations.constructors

        self.assertEqual(len(constructors), 4)
        self.assertTrue(constructors[0].cpp.is_explicit)
        self.assertTrue(constructors[1].cpp.is_explicit)
        self.assertFalse(constructors[2].cpp.is_explicit)
        self.assertTrue(constructors[3].cpp.is_explicit)

    def test_parse_headers_materializes_templated_constructors_as_constructors(self) -> None:
        source = """
namespace demo {

template <class IteratorType>
class Range {
public:
    template <class Container>
    Range(Container const& cont)
        : begin_(cont.begin())
        , end_(cont.end())
    {}

private:
    IteratorType begin_;
    IteratorType end_;
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        class_template = result.module.declarations.namespaces[0].declarations.class_templates[0]

        self.assertEqual(class_template.name, "Range")
        self.assertEqual(class_template.declaration.declarations.function_templates, [])
        self.assertEqual(len(class_template.declaration.declarations.constructors), 1)

        constructor = class_template.declaration.declarations.constructors[0]
        self.assertEqual(constructor.name, "Range")
        self.assertEqual(constructor.cpp.original_name, "Range")
        self.assertEqual(len(constructor.cpp.template_parameters), 1)
        self.assertIsInstance(constructor.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(constructor.cpp.template_parameters[0].name, "Container")
        self.assertEqual(len(constructor.parameters), 1)
        self.assertEqual(constructor.parameters[0].name, "cont")

    def test_parse_headers_keeps_normal_and_templated_constructors_separate(self) -> None:
        source = """
namespace demo {

template <class T>
class Box {
public:
    Box() = default;

    template <class U>
    Box(U const& value)
        : value_(value)
    {}

private:
    T value_ {};
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        class_template = result.module.declarations.namespaces[0].declarations.class_templates[0]

        self.assertEqual(class_template.declaration.declarations.function_templates, [])
        self.assertEqual(len(class_template.declaration.declarations.constructors), 2)

        default_constructor = class_template.declaration.declarations.constructors[0]
        templated_constructor = class_template.declaration.declarations.constructors[1]

        self.assertEqual(default_constructor.name, "Box")
        self.assertEqual(len(default_constructor.parameters), 0)
        self.assertEqual(len(default_constructor.cpp.template_parameters), 0)

        self.assertEqual(templated_constructor.name, "Box")
        self.assertEqual(len(templated_constructor.parameters), 1)
        self.assertEqual(templated_constructor.parameters[0].name, "value")
        self.assertEqual(len(templated_constructor.cpp.template_parameters), 1)
        self.assertIsInstance(templated_constructor.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(templated_constructor.cpp.template_parameters[0].name, "U")

    def test_parse_headers_populates_deleted_and_defaulted_callable_flags(self) -> None:
        source = """
namespace demo {

struct Widget {
    Widget() = default;
    Widget(int value) = delete;
    Widget(Widget const&) = default;

    Widget& operator=(Widget&&) = default;
    void run() = delete;
};

void make(int value) = delete;

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        constructors = widget.declarations.constructors
        methods = widget.declarations.methods
        free_function = namespace.declarations.functions[0]

        default_constructor = next(constructor for constructor in constructors if len(constructor.parameters) == 0)
        deleted_constructor = next(
            constructor
            for constructor in constructors
            if len(constructor.parameters) == 1
            and isinstance(constructor.parameters[0].cpp.type, BuiltinCppType)
            and constructor.parameters[0].cpp.type.kind == "int"
        )
        copy_constructor = next(
            constructor
            for constructor in constructors
            if len(constructor.parameters) == 1
            and isinstance(constructor.parameters[0].cpp.type, LValueReferenceCppType)
            and isinstance(constructor.parameters[0].cpp.type.referred, NamedCppType)
            and constructor.parameters[0].cpp.type.referred.name == "Widget"
        )
        deleted_method = next(method for method in methods if method.name == "run")
        defaulted_assignment = next(method for method in methods if method.name == "operator=")

        self.assertTrue(default_constructor.cpp.is_defaulted)
        self.assertFalse(default_constructor.cpp.is_deleted)

        self.assertTrue(deleted_constructor.cpp.is_deleted)
        self.assertFalse(deleted_constructor.cpp.is_defaulted)

        self.assertTrue(copy_constructor.cpp.is_defaulted)
        self.assertFalse(copy_constructor.cpp.is_deleted)

        self.assertTrue(defaulted_assignment.cpp.is_defaulted)
        self.assertFalse(defaulted_assignment.cpp.is_deleted)

        self.assertTrue(deleted_method.cpp.is_deleted)
        self.assertFalse(deleted_method.cpp.is_defaulted)

        self.assertTrue(free_function.cpp.is_deleted)

    def test_parse_headers_populates_structured_operator_metadata(self) -> None:
        source = """
namespace demo {

struct Awaitable {};
struct Ordering {};

struct Widget {
    Widget& operator=(Widget&&) = default;
    int operator[](int index) const;
    int operator()(int value) const;
    Widget operator++();
    Widget operator++(int);
    explicit operator bool() const;
    operator int() const;

    static void* operator new(unsigned long count);
    static void operator delete(void* memory);
    static void* operator new[](unsigned long count);
    static void operator delete[](void* memory);
    Ordering operator<=>(Widget const&) const;
    Awaitable operator co_await() const;
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = next(class_ for class_ in namespace.declarations.classes if class_.name == "Widget")
        methods = widget.declarations.methods

        assignment = next(method for method in methods if method.name == "operator=")
        index = next(method for method in methods if method.name == "operator[]")
        call = next(method for method in methods if method.name == "operator()")
        prefix_increment = next(
            method for method in methods if method.name == "operator++" and len(method.parameters) == 0
        )
        postfix_increment = next(
            method for method in methods if method.name == "operator++" and len(method.parameters) == 1
        )
        conversion = next(method for method in methods if method.name == "operator bool")
        integer_conversion = next(method for method in methods if method.name == "operator int")
        allocation = next(method for method in methods if method.name == "operator new")
        deallocation = next(method for method in methods if method.name == "operator delete")
        array_allocation = next(method for method in methods if method.name == "operator new[]")
        array_deallocation = next(method for method in methods if method.name == "operator delete[]")
        spaceship = next(method for method in methods if method.name == "operator<=>")
        co_await = next(method for method in methods if method.name == "operator co_await")

        self.assertEqual(assignment.cpp.operator.kind, "symbolic")
        self.assertEqual(assignment.cpp.operator.symbol, "=")
        self.assertFalse(assignment.cpp.operator.is_postfix)
        self.assertTrue(assignment.cpp.is_defaulted)

        self.assertEqual(index.cpp.operator.kind, "symbolic")
        self.assertEqual(index.cpp.operator.symbol, "[]")
        self.assertTrue(index.cpp.is_const)

        self.assertEqual(call.cpp.operator.kind, "symbolic")
        self.assertEqual(call.cpp.operator.symbol, "()")
        self.assertTrue(call.cpp.is_const)

        self.assertEqual(prefix_increment.cpp.operator.symbol, "++")
        self.assertFalse(prefix_increment.cpp.operator.is_postfix)
        self.assertEqual(postfix_increment.cpp.operator.symbol, "++")
        self.assertTrue(postfix_increment.cpp.operator.is_postfix)

        self.assertEqual(conversion.cpp.operator.kind, "conversion")
        self.assertIsInstance(conversion.cpp.operator.conversion_type, BuiltinCppType)
        self.assertEqual(conversion.cpp.operator.conversion_type.kind, "bool")
        self.assertTrue(conversion.cpp.operator.is_explicit)
        self.assertTrue(conversion.cpp.is_const)

        self.assertEqual(integer_conversion.cpp.operator.kind, "conversion")
        self.assertIsInstance(integer_conversion.cpp.operator.conversion_type, BuiltinCppType)
        self.assertEqual(integer_conversion.cpp.operator.conversion_type.kind, "int")
        self.assertFalse(integer_conversion.cpp.operator.is_explicit)

        self.assertEqual(allocation.cpp.operator.kind, "allocation")
        self.assertEqual(allocation.cpp.operator.symbol, "new")
        self.assertEqual(deallocation.cpp.operator.kind, "deallocation")
        self.assertEqual(deallocation.cpp.operator.symbol, "delete")
        self.assertEqual(array_allocation.cpp.operator.kind, "allocation")
        self.assertEqual(array_allocation.cpp.operator.symbol, "new[]")
        self.assertEqual(array_deallocation.cpp.operator.kind, "deallocation")
        self.assertEqual(array_deallocation.cpp.operator.symbol, "delete[]")

        self.assertEqual(spaceship.cpp.operator.kind, "symbolic")
        self.assertEqual(spaceship.cpp.operator.symbol, "<=>")
        self.assertTrue(spaceship.cpp.is_const)

        self.assertEqual(co_await.cpp.operator.kind, "co_await")
        self.assertEqual(co_await.cpp.operator.symbol, "co_await")
        self.assertTrue(co_await.cpp.is_const)

    def test_parse_headers_materialize_hidden_friend_operator_under_namespace(self) -> None:
        source = """
namespace demo {

struct Widget {
    int value {};

    friend Widget operator+(Widget const& left, Widget const& right) {
        return Widget {left.value + right.value};
    }
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        operator_function = next(function for function in namespace.declarations.functions if function.name == "operator+")

        self.assertEqual([method.name for method in widget.declarations.methods], [])
        self.assertEqual(operator_function.qualified_name, "demo::operator+")
        self.assertEqual(operator_function.cpp.operator.kind, "symbolic")
        self.assertEqual(operator_function.cpp.operator.symbol, "+")
        self.assertEqual(len(operator_function.parameters), 2)
        self.assertEqual(result.skipped_kind_counts, {})

    def test_parse_headers_materialize_free_operator_templates_with_operator_metadata(self) -> None:
        source = """
namespace demo {

struct Widget {};

template <class T>
bool operator==(Widget const& left, T const& right);

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        function_template = next(
            template
            for template in namespace.declarations.function_templates
            if template.name == "operator=="
        )

        self.assertIsInstance(function_template, CppFunctionTemplate)
        self.assertEqual(function_template.qualified_name, "demo::operator==")
        self.assertEqual(function_template.declaration.cpp.operator.kind, "symbolic")
        self.assertEqual(function_template.declaration.cpp.operator.symbol, "==")
        self.assertFalse(function_template.declaration.cpp.operator.is_postfix)
        self.assertEqual(len(function_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(function_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(function_template.declaration.cpp.template_parameters[0].name, "T")
        self.assertIsInstance(function_template.declaration.cpp.return_type, BuiltinCppType)
        self.assertEqual(function_template.declaration.cpp.return_type.kind, "bool")
        self.assertEqual(len(function_template.declaration.parameters), 2)
        self.assertEqual(function_template.declaration.parameters[0].name, "left")
        self.assertEqual(function_template.declaration.parameters[1].name, "right")

    def test_parse_headers_materialize_hidden_friend_operator_templates_under_namespace(self) -> None:
        source = """
namespace demo {

struct Widget {
    template <class T>
    friend bool operator==(Widget const& left, T const& right) {
        return true;
    }
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        function_template = next(
            template
            for template in namespace.declarations.function_templates
            if template.name == "operator=="
        )

        self.assertEqual(widget.declarations.function_templates, [])
        self.assertEqual(function_template.qualified_name, "demo::operator==")
        self.assertEqual(function_template.declaration.cpp.operator.kind, "symbolic")
        self.assertEqual(function_template.declaration.cpp.operator.symbol, "==")
        self.assertEqual(len(function_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(function_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(function_template.declaration.cpp.template_parameters[0].name, "T")
        self.assertEqual(len(function_template.declaration.parameters), 2)
        self.assertEqual(function_template.declaration.parameters[0].name, "left")
        self.assertEqual(function_template.declaration.parameters[1].name, "right")
        self.assertEqual(result.skipped_kind_counts, {})

    def test_parse_headers_materialize_member_operator_templates_with_operator_metadata(self) -> None:
        source = """
namespace demo {

struct Widget {
    template <class T>
    T operator()(T value) const;
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        widget = result.module.declarations.namespaces[0].declarations.classes[0]
        function_template = widget.declarations.function_templates[0]

        self.assertEqual(function_template.name, "operator()")
        self.assertEqual(function_template.qualified_name, "demo::Widget::operator()")
        self.assertEqual(function_template.declaration.cpp.operator.kind, "symbolic")
        self.assertEqual(function_template.declaration.cpp.operator.symbol, "()")
        self.assertTrue(function_template.declaration.cpp.is_const)
        self.assertEqual(len(function_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(function_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(function_template.declaration.cpp.template_parameters[0].name, "T")
        self.assertIsInstance(function_template.declaration.cpp.return_type, NamedCppType)
        self.assertEqual(function_template.declaration.cpp.return_type.name, "T")
        self.assertEqual(len(function_template.declaration.parameters), 1)
        self.assertEqual(function_template.declaration.parameters[0].name, "value")

    def test_parse_headers_leave_user_defined_literal_operators_unclassified(self) -> None:
        source = """
namespace demo {

struct Widget {
    int value {};
};

Widget operator""_omen(unsigned long long value);

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        literal_operator = next(
            function
            for function in namespace.declarations.functions
            if function.name == 'operator""_omen'
        )

        self.assertIsNone(literal_operator.cpp.operator)
        self.assertEqual(len(literal_operator.parameters), 1)
        self.assertEqual(literal_operator.parameters[0].name, "value")
        self.assertEqual(result.skipped_kind_counts, {})

    def test_parse_headers_enriches_defaulted_redeclarations_without_warning(self) -> None:
        source = """
namespace demo {

struct Widget {
    Widget();
    void run(int value = 7);
};

Widget::Widget() = default;

void Widget::run(int value) {}

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        constructor = result.module.declarations.namespaces[0].declarations.classes[0].declarations.constructors[0]
        method = result.module.declarations.namespaces[0].declarations.classes[0].declarations.methods[0]

        self.assertTrue(constructor.cpp.is_defaulted)
        self.assertEqual(method.parameters[0].cpp.default_value, "7")
        self.assertFalse(any("is_defaulted" in warning for warning in result.warnings))

    def test_parse_headers_materializes_out_of_line_templated_constructors_as_constructors(self) -> None:
        source = """
namespace demo {

template <class IteratorType>
class Range {
public:
    template <class Container>
    Range(Container const& cont);

private:
    IteratorType begin_;
};

template <class IteratorType>
template <class Container>
Range<IteratorType>::Range(Container const& cont)
    : begin_(cont.begin())
{}

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        class_template = result.module.declarations.namespaces[0].declarations.class_templates[0]

        self.assertEqual(class_template.declaration.declarations.function_templates, [])
        self.assertEqual(len(class_template.declaration.declarations.constructors), 1)

        constructor = class_template.declaration.declarations.constructors[0]
        self.assertEqual(constructor.name, "Range")
        self.assertEqual(constructor.cpp.original_name, "Range")
        self.assertEqual(len(constructor.cpp.template_parameters), 1)
        self.assertIsInstance(constructor.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(constructor.cpp.template_parameters[0].name, "Container")
        self.assertEqual(len(constructor.parameters), 1)
        self.assertEqual(constructor.parameters[0].name, "cont")

    def test_parse_headers_keeps_out_of_line_member_function_templates_as_function_templates(self) -> None:
        source = """
namespace demo {

template <class T>
class Box {
public:
    template <class U>
    U convert(U value);
};

template <class T>
template <class U>
U Box<T>::convert(U value) {
    return value;
}

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        class_template = result.module.declarations.namespaces[0].declarations.class_templates[0]

        self.assertEqual(class_template.declaration.declarations.constructors, [])
        self.assertEqual(len(class_template.declaration.declarations.function_templates), 1)

        function_template = class_template.declaration.declarations.function_templates[0]
        self.assertEqual(function_template.name, "convert")
        self.assertEqual(function_template.declaration.name, "convert")
        self.assertEqual(len(function_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(function_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(function_template.declaration.cpp.template_parameters[0].name, "U")
        self.assertEqual(len(function_template.declaration.parameters), 1)
        self.assertEqual(function_template.declaration.parameters[0].name, "value")

    def test_parse_headers_keeps_member_function_templates_as_function_templates(self) -> None:
        source = """
namespace demo {

template <class T>
class Box {
public:
    template <class U>
    U convert(U value) {
        return value;
    }
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        class_template = result.module.declarations.namespaces[0].declarations.class_templates[0]

        self.assertEqual(class_template.name, "Box")
        self.assertEqual(class_template.declaration.declarations.constructors, [])
        self.assertEqual(len(class_template.declaration.declarations.function_templates), 1)

        function_template = class_template.declaration.declarations.function_templates[0]
        self.assertEqual(function_template.name, "convert")
        self.assertEqual(function_template.declaration.name, "convert")
        self.assertEqual(len(function_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(function_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(function_template.declaration.cpp.template_parameters[0].name, "U")
        self.assertEqual(len(function_template.declaration.parameters), 1)
        self.assertEqual(function_template.declaration.parameters[0].name, "value")

    def test_parse_headers_keeps_similarly_named_member_function_templates_as_function_templates(self) -> None:
        source = """
namespace demo {

template <class T>
class Box {
public:
    template <class U>
    U Boxify(U value) {
        return value;
    }
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        class_template = result.module.declarations.namespaces[0].declarations.class_templates[0]

        self.assertEqual(class_template.declaration.declarations.constructors, [])
        self.assertEqual(len(class_template.declaration.declarations.function_templates), 1)

        function_template = class_template.declaration.declarations.function_templates[0]
        self.assertEqual(function_template.name, "Boxify")
        self.assertEqual(function_template.declaration.name, "Boxify")
        self.assertEqual(len(function_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(function_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(function_template.declaration.cpp.template_parameters[0].name, "U")

    def test_parse_headers_merge_template_families_across_reopened_namespaces(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
namespace demo {
template <class T>
struct Box;
}
""",
                "b.hpp": """
namespace demo {
template <class T>
struct Box {
    T value {};
};
using IntBox = Box<int>;
}
""",
            },
            header_order=["a.hpp", "b.hpp"],
        )

        self.assertEqual(len(result.module.declarations.namespaces), 1)
        namespace = result.module.declarations.namespaces[0]
        self.assertEqual(namespace.name, "demo")
        self.assertEqual(len(namespace.cpp.location.declarations), 2)
        self.assertEqual(len(namespace.declarations.class_templates), 1)

        class_template = namespace.declarations.class_templates[0]
        self.assertEqual(class_template.name, "Box")
        self.assertEqual(len(class_template.declaration.cpp.template_parameters), 1)
        self.assertEqual(len(class_template.declaration.declarations.variables), 1)
        self.assertEqual(class_template.declaration.declarations.variables[0].name, "value")
        self.assertEqual(len(class_template.declaration.cpp.observed_instances), 1)
        self.assertIsInstance(
            class_template.declaration.cpp.observed_instances[0].arguments[0].type,
            BuiltinCppType,
        )
        self.assertEqual(
            class_template.declaration.cpp.observed_instances[0].arguments[0].type.kind,
            "int",
        )

    def test_parse_headers_merge_split_template_declarations_and_definitions_across_headers(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
namespace demo {

template <class T>
class Box {
public:
    Box();

    template <class U>
    U convert(U value);

private:
    T value_ {};
};

}
""",
                "b.hpp": """
namespace demo {

template <class T>
Box<T>::Box() = default;

template <class T>
template <class U>
U Box<T>::convert(U value) {
    return value;
}

}
""",
            },
            header_order=["a.hpp", "b.hpp"],
        )

        namespace = result.module.declarations.namespaces[0]
        class_template = namespace.declarations.class_templates[0]
        declaration = class_template.declaration

        self.assertEqual(class_template.name, "Box")
        self.assertEqual(len(declaration.cpp.location.declarations), 1)
        self.assertEqual(len(declaration.declarations.constructors), 1)
        self.assertEqual(declaration.declarations.constructors[0].name, "Box")
        self.assertEqual(len(declaration.declarations.function_templates), 1)
        self.assertEqual(declaration.declarations.function_templates[0].name, "convert")
        self.assertIsNotNone(declaration.declarations.function_templates[0].declaration.cpp.location.definition)
        self.assertEqual(len(declaration.declarations.function_templates[0].declaration.parameters), 1)
        self.assertEqual(declaration.declarations.function_templates[0].declaration.parameters[0].name, "value")

    def test_parse_headers_keeps_mixed_overload_groups_with_templates_across_reopened_namespaces(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
namespace demo {

int parse();

template <class T>
T parse(T value);

}
""",
                "b.hpp": """
namespace demo {

int parse() { return 1; }

template <class T>
T parse(T value) {
    return value;
}

}
""",
            },
            header_order=["a.hpp", "b.hpp"],
        )

        namespace = result.module.declarations.namespaces[0]

        self.assertEqual(len([function for function in namespace.declarations.functions if function.name == "parse"]), 1)
        self.assertEqual(len([template for template in namespace.declarations.function_templates if template.name == "parse"]), 1)
        function = namespace.declarations.functions[0]
        function_template = namespace.declarations.function_templates[0]
        self.assertEqual(function.name, "parse")
        self.assertEqual(function_template.name, "parse")
        self.assertEqual(len(function_template.declaration.parameters), 1)
        self.assertEqual(function_template.declaration.parameters[0].name, "value")

    def test_parse_headers_preserves_realistic_overload_mixes_across_reopened_namespaces(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
namespace demo {

int parse();
int parse(int value);

}
""",
                "b.hpp": """
namespace demo {

double parse(double value);

template <class T>
T parse(T value);

}
""",
                "c.hpp": """
namespace demo {

int parse() { return 1; }
int parse(int value) { return value; }
double parse(double value) { return value; }

template <class T>
T parse(T value) {
    return value;
}

}
""",
            },
            header_order=["a.hpp", "b.hpp", "c.hpp"],
        )

        namespace = result.module.declarations.namespaces[0]
        functions = [function for function in namespace.declarations.functions if function.name == "parse"]
        templates = [template for template in namespace.declarations.function_templates if template.name == "parse"]

        self.assertEqual(len(functions), 3)
        self.assertEqual([len(function.parameters) for function in functions], [0, 1, 1])
        self.assertIsInstance(functions[1].parameters[0].cpp.type, BuiltinCppType)
        self.assertEqual(functions[1].parameters[0].cpp.type.kind, "int")
        self.assertIsInstance(functions[2].parameters[0].cpp.type, BuiltinCppType)
        self.assertEqual(functions[2].parameters[0].cpp.type.kind, "double")
        self.assertEqual(len(templates), 1)
        self.assertEqual(len(templates[0].declaration.parameters), 1)
        self.assertEqual(templates[0].declaration.parameters[0].name, "value")

    def test_parse_headers_preserves_overload_declaration_order(self) -> None:
        source = """
namespace demo {

int parse();
int parse(int value);
int parse(double value);

struct Widget {
    void visit();
    void visit(int value);
    void visit(double value);
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        function_overloads = [function for function in namespace.declarations.functions if function.name == "parse"]
        method_overloads = [method for method in namespace.declarations.classes[0].declarations.methods if method.name == "visit"]

        self.assertEqual([len(function.parameters) for function in function_overloads], [0, 1, 1])
        self.assertIsInstance(function_overloads[1].parameters[0].cpp.type, BuiltinCppType)
        self.assertEqual(function_overloads[1].parameters[0].cpp.type.kind, "int")
        self.assertIsInstance(function_overloads[2].parameters[0].cpp.type, BuiltinCppType)
        self.assertEqual(function_overloads[2].parameters[0].cpp.type.kind, "double")

        self.assertEqual([len(method.parameters) for method in method_overloads], [0, 1, 1])
        self.assertIsInstance(method_overloads[1].parameters[0].cpp.type, BuiltinCppType)
        self.assertEqual(method_overloads[1].parameters[0].cpp.type.kind, "int")
        self.assertIsInstance(method_overloads[2].parameters[0].cpp.type, BuiltinCppType)
        self.assertEqual(method_overloads[2].parameters[0].cpp.type.kind, "double")


def _parse_headers_from_sources(
    sources: dict[str, str],
    *,
    header_order: list[str] | None = None,
    parser_config: ParserConfig | None = None,
    known_project_header_names: list[str] | None = None,
):
    """Parse one small temporary header set with the real libclang pipeline."""

    ordered_names = header_order or list(sources)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        headers: list[Path] = []
        for name in ordered_names:
            header = temp_path / name
            header.write_text(sources[name])
            headers.append(header)

        known_project_headers = None
        if known_project_header_names is not None:
            known_project_headers = [temp_path / name for name in known_project_header_names]

        header_files = [
            HeaderFile(
                full_path=header,
                relative_path=header.relative_to(temp_path),
                active=True,
            )
            for header in headers
        ]
        if known_project_headers is not None:
            known_header_paths = {header.resolve() for header in known_project_headers}
            header_files.extend(
                HeaderFile(
                    full_path=header.resolve(),
                    relative_path=header.resolve().relative_to(temp_path),
                    active=False,
                )
                for header in known_project_headers
                if header.resolve() not in {active_header.full_path.resolve() for active_header in header_files}
            )

        return parse_header_selection(
            HeaderSelection(header_files=header_files),
            parser_config
            or ParserConfig(
                auto_detect_toolchain=False,
                cxx_standard="c++20",
            ),
        )
