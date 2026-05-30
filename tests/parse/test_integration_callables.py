from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from oroboros.headers import HeaderFile, HeaderSelection
from oroboros.model import *
from oroboros.parse import ParserConfig, parse_header_selection
from tests.support.parse_helpers import parse_headers_from_sources as _parse_headers_from_sources


class ParseIntegrationCallableTest(unittest.TestCase):
    def test_parse_headers_assigns_overload_indices_to_overloaded_callables(self) -> None:
        source = """
            namespace demo {

            int measure();
            int measure(int value);

            struct Widget {
                Widget();
                Widget(int value);

                void resize();
                void resize(int amount);
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        functions = namespace.declarations.functions
        widget = namespace.declarations.classes[0]
        constructors = widget.declarations.constructors
        methods = widget.declarations.methods

        self.assertEqual([function.cpp.overload_index for function in functions], [0, 1])
        self.assertEqual([constructor.cpp.overload_index for constructor in constructors], [0, 1])
        self.assertEqual([method.cpp.overload_index for method in methods], [0, 1])

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

    def test_parse_headers_merge_redeclared_operator_and_conversion_members(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
                    namespace demo {

                    class Widget {
                    public:
                        /**
                         * @brief Invoke one widget from the declaration path.
                         * @param value Value from the declaration.
                         */
                        int operator()(int value = 7) const &;

                        explicit operator bool() const &;
                    };

                    }
                """,
                "b.hpp": """
                    namespace demo {

                    /**
                     * @brief Invoke one widget from the richer definition path.
                     * @param value Value from the definition.
                     * @return One invoked value.
                     */
                    int Widget::operator()(int value) const & {
                        return value;
                    }

                    Widget::operator bool() const & {
                        return true;
                    }

                    }
                """,
            },
            header_order=["a.hpp", "b.hpp"],
        )

        widget = result.module.declarations.namespaces[0].declarations.classes[0]
        call = next(method for method in widget.declarations.methods if method.name == "operator()")
        conversion = next(method for method in widget.declarations.methods if method.name == "operator bool")

        self.assertEqual(call.cpp.operator.kind, "symbolic")
        self.assertEqual(call.cpp.operator.symbol, "()")
        self.assertIsNotNone(call.cpp.location.definition)
        self.assertTrue(call.cpp.is_const)
        self.assertEqual(call.cpp.ref_qualifier, "&")
        self.assertEqual(call.parameters[0].name, "value")
        self.assertEqual(call.parameters[0].cpp.default_value, "7")
        self.assertEqual(
            call.cpp.doc.parsed.brief,
            "Invoke one widget from the richer definition path.",
        )
        self.assertEqual(call.cpp.doc.parsed.parameters["value"], "Value from the definition.")
        self.assertEqual(call.cpp.doc.parsed.returns, "One invoked value.")
        self.assertEqual(call.parameters[0].cpp.doc, "Value from the definition.")

        self.assertEqual(conversion.cpp.operator.kind, "conversion")
        self.assertIsNotNone(conversion.cpp.location.definition)
        self.assertTrue(conversion.cpp.is_const)
        self.assertEqual(conversion.cpp.ref_qualifier, "&")
        self.assertTrue(conversion.cpp.operator.is_explicit)
        self.assertIsInstance(conversion.cpp.operator.conversion_type, BuiltinCppType)
        self.assertEqual(conversion.cpp.operator.conversion_type.kind, "bool")

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

    def test_parse_headers_populates_special_member_and_converting_constructor_classifiers(self) -> None:
        source = """
            namespace demo {

            struct Widget {
                Widget() = default;
                Widget(int value);
                Widget(Widget const&) = default;
                Widget(Widget&&) = default;

                Widget& operator=(Widget const&) = default;
                Widget& operator=(Widget&&) = default;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        widget = result.module.declarations.namespaces[0].declarations.classes[0]
        constructors = widget.declarations.constructors
        methods = widget.declarations.methods

        default_constructor = next(constructor for constructor in constructors if len(constructor.parameters) == 0)
        converting_constructor = next(
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
        )
        move_constructor = next(
            constructor
            for constructor in constructors
            if len(constructor.parameters) == 1
            and isinstance(constructor.parameters[0].cpp.type, RValueReferenceCppType)
        )
        copy_assignment = next(
            method
            for method in methods
            if method.name == "operator="
            and isinstance(method.parameters[0].cpp.type, LValueReferenceCppType)
        )
        move_assignment = next(
            method
            for method in methods
            if method.name == "operator="
            and isinstance(method.parameters[0].cpp.type, RValueReferenceCppType)
        )

        self.assertEqual(default_constructor.cpp.special_member_kind, "default_constructor")
        self.assertFalse(default_constructor.cpp.is_converting_constructor)

        self.assertIsNone(converting_constructor.cpp.special_member_kind)
        self.assertTrue(converting_constructor.cpp.is_converting_constructor)

        self.assertEqual(copy_constructor.cpp.special_member_kind, "copy_constructor")
        self.assertTrue(copy_constructor.cpp.is_converting_constructor)

        self.assertEqual(move_constructor.cpp.special_member_kind, "move_constructor")
        self.assertTrue(move_constructor.cpp.is_converting_constructor)

        self.assertEqual(copy_assignment.cpp.special_member_kind, "copy_assignment")
        self.assertEqual(move_assignment.cpp.special_member_kind, "move_assignment")

    def test_parse_headers_populates_method_ref_qualifiers(self) -> None:
        source = """
            namespace demo {

            struct Widget {
                void touch() &;
                void consume() &&;
                int value() const &;
                int operator()(int count) &;
                Widget operator++(int) &&;
                explicit operator bool() &&;

                template <class T>
                T convert(T item) &&;
            };

            void Widget::touch() & {}

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        widget = result.module.declarations.namespaces[0].declarations.classes[0]
        methods = widget.declarations.methods

        touch = next(method for method in methods if method.name == "touch")
        consume = next(method for method in methods if method.name == "consume")
        value = next(method for method in methods if method.name == "value")
        call = next(method for method in methods if method.name == "operator()")
        postfix_increment = next(
            method for method in methods if method.name == "operator++" and len(method.parameters) == 1
        )
        conversion = next(method for method in methods if method.name == "operator bool")
        method_template = widget.declarations.method_templates[0]

        self.assertEqual(touch.cpp.ref_qualifier, "&")
        self.assertEqual(len(touch.cpp.location.declarations), 2)
        self.assertEqual(consume.cpp.ref_qualifier, "&&")
        self.assertEqual(value.cpp.ref_qualifier, "&")
        self.assertTrue(value.cpp.is_const)
        self.assertEqual(call.cpp.ref_qualifier, "&")
        self.assertEqual(postfix_increment.cpp.ref_qualifier, "&&")
        self.assertTrue(postfix_increment.cpp.operator.is_postfix)
        self.assertEqual(conversion.cpp.ref_qualifier, "&&")
        self.assertEqual(conversion.cpp.operator.kind, "conversion")
        self.assertEqual(method_template.declaration.cpp.ref_qualifier, "&&")

    def test_parse_headers_do_not_confuse_other_ampersands_with_ref_qualifiers(self) -> None:
        source = """
            namespace demo {

            struct Widget {
                int& data();
                void take(int&& value);
                bool operator&&(Widget const& other) const;

                friend Widget operator&(Widget const& left, Widget const& right);
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        data = next(method for method in widget.declarations.methods if method.name == "data")
        take = next(method for method in widget.declarations.methods if method.name == "take")
        logical_and = next(method for method in widget.declarations.methods if method.name == "operator&&")
        bitwise_and = next(function for function in namespace.declarations.functions if function.name == "operator&")

        self.assertIsNone(data.cpp.ref_qualifier)
        self.assertIsNone(take.cpp.ref_qualifier)
        self.assertIsNone(logical_and.cpp.ref_qualifier)
        self.assertFalse(hasattr(bitwise_and.cpp, "ref_qualifier"))

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

        self.assertEqual(widget.declarations.method_templates, [])
        self.assertEqual(function_template.qualified_name, "demo::operator==")
        self.assertEqual(function_template.declaration.cpp.operator.kind, "symbolic")
        self.assertEqual(function_template.declaration.cpp.operator.symbol, "==")
        self.assertEqual(len(function_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(function_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(function_template.declaration.cpp.template_parameters[0].name, "T")
        self.assertEqual(len(function_template.declaration.parameters), 2)
        self.assertEqual(function_template.declaration.parameters[0].name, "left")
        self.assertEqual(function_template.declaration.parameters[1].name, "right")

    def test_parse_headers_materialize_hidden_friend_operator_inside_class_template(self) -> None:
        source = """
            namespace demo {

            template <class T>
            struct Box {
                friend bool operator==(Box const& left, Box const& right) {
                    return true;
                }
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        class_template = namespace.declarations.class_templates[0]
        function = next(
            function
            for function in namespace.declarations.functions
            if function.name == "operator=="
        )

        self.assertEqual(class_template.declaration.declarations.methods, [])
        self.assertEqual(function.qualified_name, "demo::operator==")
        self.assertEqual(function.cpp.operator.kind, "symbolic")
        self.assertEqual(function.cpp.operator.symbol, "==")
        self.assertEqual(len(function.parameters), 2)

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
        method_template = widget.declarations.method_templates[0]

        self.assertIsInstance(method_template, CppMethodTemplate)
        self.assertEqual(method_template.name, "operator()")
        self.assertEqual(method_template.qualified_name, "demo::Widget::operator()")
        self.assertEqual(method_template.declaration.cpp.operator.kind, "symbolic")
        self.assertEqual(method_template.declaration.cpp.operator.symbol, "()")
        self.assertTrue(method_template.declaration.cpp.is_const)
        self.assertEqual(len(method_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(method_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(method_template.declaration.cpp.template_parameters[0].name, "T")
        self.assertIsInstance(method_template.declaration.cpp.return_type, NamedCppType)
        self.assertEqual(method_template.declaration.cpp.return_type.name, "T")
        self.assertEqual(len(method_template.declaration.parameters), 1)
        self.assertEqual(method_template.declaration.parameters[0].name, "value")

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
        self.assertFalse(any("is_defaulted" in warning.message for warning in result.report.warnings))

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
