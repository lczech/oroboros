from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from oroboros.model import (
    ArrayCppType,
    BuiltinCppType,
    CppAlias,
    CppVisibility,
    FunctionCppType,
    LValueReferenceCppType,
    NamedCppType,
    PointerCppType,
    TemplateInstanceCppType,
)
from oroboros.parse import ParserConfig, parse_headers


class ParseIntegrationTest(unittest.TestCase):
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

        namespace = result.module.namespaces[0]
        enum_ = namespace.enums[0]
        cls = namespace.classes[0]
        function = namespace.functions[0]

        self.assertEqual(namespace.name, "demo")
        self.assertEqual(enum_.name, "Realm")
        self.assertEqual(enum_.enumerators[0].name, "earth")
        self.assertEqual(cls.name, "Widget")
        self.assertEqual(len(cls.constructors), 1)
        self.assertEqual(len(cls.fields), 1)
        self.assertEqual(cls.fields[0].name, "value")
        self.assertEqual(len(cls.methods), 1)
        self.assertEqual(cls.methods[0].name, "size")
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

        namespace = result.module.namespaces[0]
        widget = namespace.classes[0]
        holder = namespace.classes[1]
        function = namespace.functions[0]
        method = holder.methods[0]

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

        namespace = result.module.namespaces[0]
        function = namespace.functions[0]
        method = namespace.classes[0].methods[0]

        self.assertEqual(len(function.parameters), 1)
        self.assertEqual(function.parameters[0].name, "value")
        self.assertEqual(len(method.parameters), 1)
        self.assertEqual(method.parameters[0].name, "amount")

    def test_parse_headers_reopens_namespaces_across_active_headers(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
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

        self.assertEqual(len(result.module.namespaces), 1)
        namespace = result.module.namespaces[0]
        self.assertEqual(namespace.name, "demo")
        self.assertEqual(len(namespace.classes), 1)
        self.assertEqual(namespace.classes[0].name, "Widget")
        self.assertEqual(len(namespace.functions), 1)
        self.assertEqual(namespace.functions[0].name, "make_widget")

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

        namespace = result.module.namespaces[0]
        functions = {function.name: function for function in namespace.functions}

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

    def test_parse_headers_extracts_real_doxygen_comments(self) -> None:
        source = """
namespace demo {

/// Represent one widget in the real parsed headers.
struct Widget {};

/**
 * Build one widget from the current demo state.
 *
 * @return One newly created widget.
 */
Widget make_widget();

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.namespaces[0]
        widget = namespace.classes[0]
        function = namespace.functions[0]

        self.assertIsNotNone(widget.cpp.comment)
        self.assertIn("Represent one widget", widget.cpp.comment)
        self.assertIsNotNone(function.cpp.comment)
        self.assertIn("Build one widget", function.cpp.comment)
        self.assertIn("@return One newly created widget.", function.cpp.comment)

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

        namespace = result.module.namespaces[0]
        widget = namespace.classes[0]
        make_alias = namespace.functions[0]
        make_typedef = namespace.functions[1]
        alias = namespace.aliases[0]
        typedef_alias = namespace.aliases[1]

        self.assertEqual([alias.name for alias in namespace.aliases], ["Alias", "WidgetAlias"])
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

        namespace = result.module.namespaces[0]
        widget = namespace.classes[0]
        holder = namespace.classes[1]
        widget_handle = namespace.aliases[0]
        local_widget = holder.aliases[0]

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

        namespace = result.module.namespaces[0]
        omen_kind = namespace.namespaces[0].enums[0]
        holder = namespace.classes[0]
        field_type = holder.fields[0].cpp.type
        method = holder.methods[0]

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

        widget = result.module.namespaces[0].classes[0]
        constructor = widget.constructors[0]
        render = widget.methods[0]
        warmup = widget.methods[1]
        size = widget.methods[2]
        cache_size = widget.fields[0]

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
        self.assertFalse(cache_size.cpp.is_static)

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

        namespace = result.module.namespaces[0]
        functions = {function.name: function for function in namespace.functions}

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
        self.assertIsInstance(nested_type.arguments[0], TemplateInstanceCppType)
        self.assertEqual(nested_type.arguments[0].template_name, "Pair")
        self.assertEqual(len(nested_type.arguments[0].arguments), 2)
        self.assertIsInstance(nested_type.arguments[0].arguments[0], BuiltinCppType)
        self.assertEqual(nested_type.arguments[0].arguments[0].kind, "int")
        self.assertIsInstance(nested_type.arguments[0].arguments[1], NamedCppType)
        self.assertEqual(nested_type.arguments[0].arguments[1].name, "Widget")

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

        constructor = result.module.namespaces[0].classes[0].constructors[0]

        self.assertEqual(len(constructor.parameters), 1)
        self.assertEqual(constructor.parameters[0].name, "value")

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

        namespace = result.module.namespaces[0]
        function_overloads = [function for function in namespace.functions if function.name == "parse"]
        method_overloads = [method for method in namespace.classes[0].methods if method.name == "visit"]

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

        return parse_headers(
            headers,
            ParserConfig(
                auto_detect_toolchain=False,
                cxx_standard="c++20",
            ),
        )
