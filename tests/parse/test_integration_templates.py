from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from oroboros.headers import HeaderFile, HeaderSelection
from oroboros.model import *
from oroboros.parse import ParserConfig, parse_header_selection
from tests.support.parse_helpers import parse_headers_from_sources as _parse_headers_from_sources


class ParseIntegrationTemplateTest(unittest.TestCase):
    def _hint_spellings(self, template: CppElement) -> list[str]:
        return [hint.spelling for hint in template.declaration.cpp.template_observation_hints]

    def _hint_locations(self, template: CppElement) -> list[list[SourceLocation]]:
        return [hint.locations for hint in template.declaration.cpp.template_observation_hints]

    def test_parse_headers_materializes_alias_template_declarations_without_duplicate_plain_aliases(self) -> None:
        source = """
            namespace demo {

            template <class T>
            struct Box {
                T value {};
            };

            template <class T>
            using Vec = Box<T>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]

        self.assertEqual(len(namespace.declarations.aliases), 0)
        self.assertEqual(len(namespace.declarations.alias_templates), 1)

        alias_template = namespace.declarations.alias_templates[0]
        self.assertIsInstance(alias_template, CppAliasTemplate)
        self.assertEqual(alias_template.name, "Vec")
        self.assertEqual(alias_template.qualified_name, "demo::Vec")
        self.assertEqual(alias_template.declaration.qualified_name, "demo::Vec")
        self.assertEqual(len(alias_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(
            alias_template.declaration.cpp.template_parameters[0],
            CppTypeTemplateParameter,
        )
        self.assertEqual(alias_template.declaration.cpp.template_parameters[0].name, "T")
        self.assertIsInstance(alias_template.declaration.cpp.target, TemplateInstanceCppType)
        self.assertEqual(alias_template.declaration.cpp.target.template_name, "Box")
        self.assertEqual(len(alias_template.declaration.cpp.target.arguments), 1)
        self.assertIsInstance(alias_template.declaration.cpp.target.arguments[0], CppTypeTemplateArgument)
        self.assertIsInstance(alias_template.declaration.cpp.target.arguments[0].type, NamedCppType)
        self.assertEqual(alias_template.declaration.cpp.target.arguments[0].type.name, "T")
        self.assertEqual(alias_template.declaration.cpp.kind, "using")

    def test_parse_headers_materializes_class_scoped_alias_templates_with_docs_and_visibility(self) -> None:
        source = """
            namespace demo {

            struct Vault {
            protected:
                /// Handle alias for the vault contents.
                template <class T>
                using Handle = T*;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        vault = namespace.declarations.classes[0]

        self.assertEqual(len(vault.declarations.aliases), 0)
        self.assertEqual(len(vault.declarations.alias_templates), 1)
        alias_template = vault.declarations.alias_templates[0]
        self.assertIsInstance(alias_template, CppAliasTemplate)
        self.assertEqual(alias_template.qualified_name, "demo::Vault::Handle")
        self.assertEqual(alias_template.declaration.cpp.visibility, CppVisibility.PROTECTED)
        self.assertIn("Handle alias for the vault contents.", alias_template.declaration.cpp.doc.attached_comment)
        self.assertIsNotNone(alias_template.declaration.cpp.doc)
        self.assertIsInstance(alias_template.declaration.cpp.target, PointerCppType)
        self.assertIsInstance(alias_template.declaration.cpp.target.pointee, NamedCppType)
        self.assertEqual(alias_template.declaration.cpp.target.pointee.name, "T")

    def test_parse_headers_collects_observed_alias_template_instances_from_declaration_types(self) -> None:
        source = """
            namespace demo {

            struct RelicInfo {};

            template <class T>
            struct Box {
                T value {};
            };

            template <class T>
            using Vec = Box<T>;

            using RelicVec = Vec<RelicInfo>;

            struct Holder {
                Vec<RelicInfo> primary;
            };

            Vec<RelicInfo> make_vec();

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        alias_template = namespace.declarations.alias_templates[0]
        self.assertEqual(self._hint_spellings(alias_template), ["Vec<RelicInfo>"])
        self.assertEqual(len(self._hint_locations(alias_template)[0]), 3)

    def test_parse_headers_observed_alias_template_instances_keep_source_type_arguments_when_target_expands_to_multi_parameter_target(self) -> None:
        source = """
            namespace demo {

            struct RelicInfo {};

            template <class T>
            struct Ptr {
                T value {};
            };

            template <class T>
            struct Alloc {
                T value {};
            };

            template <class T, class A>
            struct Container {
                T value {};
            };

            template <class T>
            using Vec = Container<Ptr<T>, Alloc<Ptr<T>>>;

            using RelicVec = Vec<RelicInfo>;

            struct Holder {
                Vec<RelicInfo> primary;
            };

            Vec<RelicInfo> make_vec();

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        alias_template = namespace.declarations.alias_templates[0]
        self.assertEqual(self._hint_spellings(alias_template), ["Vec<RelicInfo>"])
        self.assertEqual(len(self._hint_locations(alias_template)[0]), 3)

    def test_parse_headers_observed_alias_template_instances_keep_dependent_source_type_arguments_when_target_expands_to_multi_parameter_target(self) -> None:
        source = """
            namespace demo {

            template <class T>
            struct Ptr {
                T value {};
            };

            template <class T>
            struct Alloc {
                T value {};
            };

            template <class T, class A>
            struct Container {
                T value {};
            };

            template <class T>
            using Vec = Container<Ptr<T>, Alloc<Ptr<T>>>;

            template <class T>
            struct Holder {
                using alias_type = Vec<T>;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        alias_template = namespace.declarations.alias_templates[0]
        self.assertEqual(self._hint_spellings(alias_template), ["Vec<T>"])

    def test_parse_headers_observed_alias_template_instances_preserve_source_arguments_through_alias_chain(self) -> None:
        source = """
            namespace demo {

            struct RelicInfo {};

            template <class T>
            struct Ptr {
                T value {};
            };

            template <class T>
            struct Alloc {
                T value {};
            };

            template <class T, class A>
            struct Container {
                T value {};
            };

            template <class T>
            using Vec = Container<Ptr<T>, Alloc<Ptr<T>>>;

            template <class T>
            using Vec2 = Vec<T>;

            using RelicVec = Vec2<RelicInfo>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        alias_templates = {template.name: template for template in namespace.declarations.alias_templates}

        vec = alias_templates["Vec"]
        vec2 = alias_templates["Vec2"]

        # Vec itself is never directly used in source — only Vec2<RelicInfo> is written.
        # Only Vec2 receives an observation; Vec's alias body is suppressed.
        self.assertEqual(self._hint_spellings(vec), [])
        self.assertEqual(self._hint_spellings(vec2), ["Vec2<RelicInfo>"])

    def test_parse_headers_observed_alias_template_instances_preserve_template_template_arguments(self) -> None:
        source = """
            namespace demo {

            template <class T>
            struct Box {
                T value {};
            };

            template <class T, template <class> class Wrapper>
            struct Holder {
                Wrapper<T> value {};
            };

            template <class T, template <class> class Wrapper>
            using Alias = Holder<T, Wrapper>;

            using IntAlias = Alias<int, Box>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        alias_template = namespace.declarations.alias_templates[0]
        self.assertEqual(self._hint_spellings(alias_template), ["Alias<int,Box>"])

    def test_parse_headers_template_observation_hints_preserve_qualified_template_template_spellings(self) -> None:
        source = """
            namespace outer {
            template <class T>
            struct Box {};
            }

            namespace demo {

            template <class T, template <class> class Wrapper>
            struct Holder {
                Wrapper<T> value {};
            };

            using IntHolder = Holder<int, outer::Box>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[1]
        holder_template = namespace.declarations.class_templates[0]

        self.assertEqual(self._hint_spellings(holder_template), ["Holder<int,outer::Box>"])

    def test_parse_headers_observed_alias_template_instances_preserve_non_type_arguments_through_transformed_target(self) -> None:
        source = """
            namespace demo {

            struct WrapTag {};

            template <int N, class Tag>
            struct Box {
                int value = N;
            };

            template <int N>
            using Alias = Box<N, WrapTag>;

            using Seven = Alias<7>;

            template <int N>
            struct Holder {
                using alias_type = Alias<N>;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        alias_template = namespace.declarations.alias_templates[0]
        self.assertEqual(
            sorted(self._hint_spellings(alias_template)),
            ["Alias<7>", "Alias<N>"],
        )

    def test_parse_headers_observed_alias_template_instances_preserve_enum_non_type_arguments_through_transformed_target(self) -> None:
        source = """
            namespace demo {

            enum class Flag {
                off,
                on,
            };

            struct WrapTag {};

            template <Flag F, class Tag>
            struct Box {
            };

            template <Flag F>
            using Alias = Box<F, WrapTag>;

            using OnAlias = Alias<Flag::on>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        alias_template = namespace.declarations.alias_templates[0]
        self.assertEqual(self._hint_spellings(alias_template), ["Alias<Flag::on>"])

    def test_parse_headers_does_not_record_spurious_alias_template_instances_from_member_type_access_through_alias_chain(self) -> None:
        source = """
            namespace demo {

            struct Leaf {};

            template <class Ptr, class ContainerRef>
            struct raw_iter {};

            template <class T, class Alloc = T>
            struct Container {
                using iterator = raw_iter<T*, Container<T, Alloc>>;
            };

            template <class T>
            using Vec = Container<T>;

            template <class T>
            using Vec2 = Vec<T>;

            template <class Iter>
            struct DerefIter {};

            using LeafVec = Vec2<Leaf>;
            using IterLeaf = DerefIter<Vec2<Leaf>::iterator>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        alias_templates = {template.name: template for template in namespace.declarations.alias_templates}

        vec = alias_templates["Vec"]
        vec2 = alias_templates["Vec2"]

        # Vec itself is never directly used in source — only Vec2<Leaf> is written.
        # Vec2<Leaf>::iterator triggers no observation because template recovery
        # rejects that member-type-access spelling as a direct template instantiation.
        self.assertEqual(self._hint_spellings(vec), [])
        self.assertEqual(self._hint_spellings(vec2), ["Vec2<Leaf>"])

    def test_parse_headers_non_template_alias_body_does_record_observation(self) -> None:
        # A plain (non-template) alias `using VecLeaf = Vec<Leaf>` should record
        # an observation on Vec with ["Leaf"].  Unlike an alias template body, a
        # TYPE_ALIAS_DECL is a declaration-surface concrete use site, so the
        # surface recorder visits its target type.
        source = """
            namespace demo {

            struct Leaf {};

            template <class T>
            struct Vec {};

            using VecLeaf = Vec<Leaf>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        vec = namespace.declarations.class_templates[0]
        self.assertEqual(self._hint_spellings(vec), ["Vec<Leaf>"])

    def test_parse_headers_alias_template_body_does_not_record_concrete_nested_type_observation(self) -> None:
        # `template<class Dummy> using Fixed = Vec<int>` has a *concrete* Vec<int>
        # in its body.  Even though Vec<int> is not dependent, it must NOT be
        # observed, because the alias body is a definition site, not a use site.
        # Alias-template bodies are excluded from declaration-surface observation.
        source = """
            namespace demo {

            template <class T>
            struct Vec {};

            template <class Dummy>
            using Fixed = Vec<int>;

            using F1 = Fixed<void>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        class_template = namespace.declarations.class_templates[0]
        vec_hints = class_template.declaration.cpp.template_observation_hints

        alias_template = namespace.declarations.alias_templates[0]
        fixed_hints = alias_template.declaration.cpp.template_observation_hints

        # Vec<int> is only inside the alias body — must not be observed.
        self.assertEqual(len(vec_hints), 0)
        # Fixed itself is used via `Fixed<void>` — must be observed.
        self.assertEqual(len(fixed_hints), 1)
        self.assertEqual(fixed_hints[0].spelling, "Fixed<void>")

    def test_parse_headers_alias_template_body_does_not_record_nested_template_observations(self) -> None:
        # `template<class T> using PairVec = Pair<T, Vec<T>>` nests Vec<T> inside
        # the alias body.  Because alias-template bodies are not declaration-surface
        # observation sites, Vec gets no hints from that nested use either.
        source = """
            namespace demo {

            struct Leaf {};

            template <class T>
            struct Vec {};

            template <class T, class U>
            struct Pair {};

            template <class T>
            using PairVec = Pair<T, Vec<T>>;

            using PairLeaf = PairVec<Leaf>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        templates = {t.name: t for t in namespace.declarations.class_templates}
        alias_templates = {t.name: t for t in namespace.declarations.alias_templates}

        vec_hints = templates["Vec"].declaration.cpp.template_observation_hints
        pair_vec_hints = alias_templates["PairVec"].declaration.cpp.template_observation_hints

        # Vec<T> is only inside the alias body (nested inside Pair<T, Vec<T>>)
        # — must not be observed.
        self.assertEqual(len(vec_hints), 0)
        # PairVec itself is used via PairVec<Leaf> — must be observed.
        self.assertEqual(len(pair_vec_hints), 1)
        self.assertEqual(pair_vec_hints[0].spelling, "PairVec<Leaf>")

    def test_parse_headers_preserve_zero_explicit_template_arguments(self) -> None:
        source = """
            namespace demo {

            template <class T = int>
            struct Box {
                T value {};
            };

            using DefaultBox = Box<>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        box_template = namespace.declarations.class_templates[0]
        self.assertEqual(self._hint_spellings(box_template), ["Box<>"])

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

    def test_parse_headers_fold_explicit_class_template_specializations_into_template_observation_hints(self) -> None:
        source = """
            namespace demo {

            template <class T>
            struct Box {
                T value {};
            };

            template <>
            struct Box<int> {
                int value {};
                int doubled() const { return value * 2; }
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]

        self.assertEqual(namespace.declarations.classes, [])
        self.assertEqual(len(namespace.declarations.class_templates), 1)

        box_template = namespace.declarations.class_templates[0]
        self.assertEqual(self._hint_spellings(box_template), ["demo::Box<int>"])
        self.assertEqual(len(self._hint_locations(box_template)[0]), 1)
        self.assertTrue(
            any("Explicit class-template specialization" in warning.message for warning in result.report.warnings),
            msg=f"Expected explicit-specialization warning, got: {result.report.warnings}",
        )

    def test_parse_headers_assigns_overload_indices_to_template_declarations(self) -> None:
        source = """
            namespace demo {

            template <class T>
            T make_value(T value);

            template <class T>
            T make_value(int value);

            struct Widget {
                template <class T>
                void convert(T value);

                template <class T>
                void convert(int value);
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        function_templates = namespace.declarations.function_templates
        method_templates = namespace.declarations.classes[0].declarations.method_templates

        self.assertEqual(
            [template.declaration.cpp.overload_index for template in function_templates],
            [0, 1],
        )
        self.assertEqual(
            [template.declaration.cpp.overload_index for template in method_templates],
            [0, 1],
        )

    def test_parse_headers_populates_template_parameter_defaults_across_template_kinds(self) -> None:
        source = """
            namespace demo {

            template <class T>
            struct Allocator {};

            template <class T, class Alloc = Allocator<T>>
            struct Vec {
                T value {};
            };

            template <class T = int>
            using Alias = Vec<T>;

            template <class T = int, int N = 4>
            T make_value();

            struct Widget {
                template <class T = int const*, class U = Allocator<T>>
                U convert();
            };

            template <template <class> class Wrapper = Vec>
            struct Holder {};

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        vec_template = namespace.declarations.class_templates[1]
        alias_template = namespace.declarations.alias_templates[0]
        function_template = namespace.declarations.function_templates[0]
        widget = namespace.declarations.classes[0]
        method_template = widget.declarations.method_templates[0]
        holder_template = namespace.declarations.class_templates[2]

        vec_allocator_parameter = vec_template.declaration.cpp.template_parameters[1]
        self.assertIsInstance(vec_allocator_parameter.default, CppTypeTemplateArgument)
        self.assertIsInstance(vec_allocator_parameter.default.type, TemplateInstanceCppType)
        self.assertEqual(vec_allocator_parameter.default.type.template_name, "Allocator")
        self.assertEqual(len(vec_allocator_parameter.default.type.arguments), 1)
        self.assertIsInstance(vec_allocator_parameter.default.type.arguments[0], CppOpaqueTemplateArgument)
        self.assertEqual(vec_allocator_parameter.default.type.arguments[0].spelling, "T")

        alias_parameter = alias_template.declaration.cpp.template_parameters[0]
        self.assertIsInstance(alias_parameter.default, CppTypeTemplateArgument)
        self.assertIsInstance(alias_parameter.default.type, BuiltinCppType)
        self.assertEqual(alias_parameter.default.type.kind, "int")

        function_type_parameter = function_template.declaration.cpp.template_parameters[0]
        function_non_type_parameter = function_template.declaration.cpp.template_parameters[1]
        self.assertIsInstance(function_type_parameter.default, CppTypeTemplateArgument)
        self.assertIsInstance(function_type_parameter.default.type, BuiltinCppType)
        self.assertEqual(function_type_parameter.default.type.kind, "int")
        self.assertIsInstance(function_non_type_parameter.default, CppNonTypeTemplateArgument)
        self.assertEqual(function_non_type_parameter.default.value, "4")
        self.assertIsInstance(function_non_type_parameter.default.type, BuiltinCppType)
        self.assertEqual(function_non_type_parameter.default.type.kind, "int")

        method_type_parameter = method_template.declaration.cpp.template_parameters[0]
        method_allocator_parameter = method_template.declaration.cpp.template_parameters[1]
        self.assertIsInstance(method_type_parameter.default, CppTypeTemplateArgument)
        self.assertIsInstance(method_type_parameter.default.type, PointerCppType)
        self.assertIsInstance(method_type_parameter.default.type.pointee, BuiltinCppType)
        self.assertTrue(method_type_parameter.default.type.pointee.is_const)
        self.assertEqual(method_type_parameter.default.type.pointee.kind, "int")
        self.assertIsInstance(method_allocator_parameter.default, CppTypeTemplateArgument)
        self.assertIsInstance(method_allocator_parameter.default.type, TemplateInstanceCppType)
        self.assertEqual(method_allocator_parameter.default.type.template_name, "Allocator")
        self.assertIsInstance(method_allocator_parameter.default.type.arguments[0], CppOpaqueTemplateArgument)
        self.assertEqual(method_allocator_parameter.default.type.arguments[0].spelling, "T")

        holder_parameter = holder_template.declaration.cpp.template_parameters[0]
        self.assertIsInstance(holder_parameter.default, CppTemplateTemplateArgument)
        self.assertEqual(holder_parameter.default.name, "Vec")
        self.assertEqual(len(holder_parameter.default.parameters), 2)
        self.assertIsInstance(holder_parameter.default.parameters[0], CppTypeTemplateParameter)
        self.assertEqual(holder_parameter.default.parameters[0].name, "T")
        self.assertIsInstance(holder_parameter.default.parameters[1], CppTypeTemplateParameter)
        self.assertEqual(holder_parameter.default.parameters[1].name, "Alloc")

    def test_parse_headers_preserve_dependent_typename_default_spellings(self) -> None:
        source = """
            namespace demo {

            template <class T>
            struct Traits {
                using value_type = T;

                template <class U>
                struct Rebind {
                    using type = U*;
                };
            };

            template <class T, class U = typename Traits<T>::value_type>
            struct ValueBox {};

            template <class T, class U = typename Traits<T>::template Rebind<T>::type>
            struct RebindBox {};

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        value_box = namespace.declarations.class_templates[1]
        rebind_box = namespace.declarations.class_templates[2]

        value_parameter = value_box.declaration.cpp.template_parameters[1]
        rebind_parameter = rebind_box.declaration.cpp.template_parameters[1]

        self.assertIsInstance(value_parameter.default, CppTypeTemplateArgument)
        self.assertIsInstance(value_parameter.default.type, NamedCppType)
        self.assertEqual(
            value_parameter.default.type.render(),
            "typename Traits<T>::value_type",
        )

        self.assertIsInstance(rebind_parameter.default, CppTypeTemplateArgument)
        self.assertIsInstance(rebind_parameter.default.type, NamedCppType)
        self.assertEqual(
            rebind_parameter.default.type.render(),
            "typename Traits<T>::template Rebind<T>::type",
        )

    def test_parse_headers_parsed_template_parameter_defaults_enable_instance_creation(self) -> None:
        source = """
            namespace demo {

            template <class T>
            struct Allocator {};

            template <class T, class Alloc = Allocator<T>>
            struct Vec {
                T value {};
            };

            template <class T = int>
            using Alias = Vec<T>;

            template <class T, int N = 4>
            T make_value();

            struct Widget {
                template <class T, int N = 4>
                T convert();
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        vec_template = namespace.declarations.class_templates[1]
        alias_template = namespace.declarations.alias_templates[0]
        function_template = namespace.declarations.function_templates[0]
        method_template = namespace.declarations.classes[0].declarations.method_templates[0]

        vec_instance = add_class_template_instance(
            vec_template,
            [CppTypeTemplateArgument(type=BuiltinCppType(kind="int"))],
        )
        alias_instance = add_alias_template_instance(alias_template, [])
        function_instance = add_function_template_instance(
            function_template,
            [CppTypeTemplateArgument(type=BuiltinCppType(kind="int"))],
        )
        method_instance = add_method_template_instance(
            method_template,
            [CppTypeTemplateArgument(type=BuiltinCppType(kind="int"))],
        )

        self.assertEqual(len(vec_instance.cpp.template_arguments), 1)
        self.assertEqual(len(alias_instance.cpp.template_arguments), 0)
        self.assertEqual(len(function_instance.cpp.template_arguments), 1)
        self.assertEqual(len(method_instance.cpp.template_arguments), 1)

    def test_parse_headers_keep_separate_hints_for_defaulted_non_type_arguments(self) -> None:
        source = """
            namespace demo {

            template <class T, int N = 4>
            struct Box {
                T value {};
            };

            using IntBox = Box<int>;
            using ExplicitIntBox = Box<int, 4>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        box_template = namespace.declarations.class_templates[0]
        self.assertEqual(
            self._hint_spellings(box_template),
            ["Box<int>", "Box<int,4>"],
        )

    def test_parse_headers_coerce_dependent_non_type_observed_arguments(self) -> None:
        source = """
            namespace demo {

            template <bool is_const = true>
            struct Box {
                using self_type = Box<is_const>;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        box_template = result.module.declarations.namespaces[0].declarations.class_templates[0]
        self.assertEqual(self._hint_spellings(box_template), ["Box<is_const>"])

    def test_parse_headers_coerce_dependent_non_type_observed_arguments_in_mixed_templates(self) -> None:
        source = """
            namespace demo {

            template <class T, bool is_const = true>
            struct Box {
                using self_type = Box<T, is_const>;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        box_template = result.module.declarations.namespaces[0].declarations.class_templates[0]
        self.assertEqual(self._hint_spellings(box_template), ["Box<T,is_const>"])

    def test_parse_headers_coerce_dependent_non_type_expression_observed_arguments(self) -> None:
        source = """
            namespace demo {

            template <int N>
            struct Box {
                using next_type = Box<N + 1>;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        box_template = result.module.declarations.namespaces[0].declarations.class_templates[0]
        self.assertEqual(self._hint_spellings(box_template), ["Box<N+1>"])

    def test_parse_headers_coerce_scoped_non_type_observed_arguments(self) -> None:
        source = """
            namespace demo {

            enum class Flag { off, on };

            template <Flag flag>
            struct Box {
                using self_type = Box<flag>;
                using on_type = Box<Flag::on>;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        box_template = result.module.declarations.namespaces[0].declarations.class_templates[0]
        self.assertEqual(
            sorted(self._hint_spellings(box_template)),
            ["Box<Flag::on>", "Box<flag>"],
        )

    def test_parse_headers_coerce_dependent_non_type_observed_arguments_for_alias_templates(self) -> None:
        source = """
            namespace demo {

            template <int N>
            struct Box {
                int value {};
            };

            template <int N>
            using Alias = Box<N>;

            template <int N>
            struct Holder {
                using alias_type = Alias<N>;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        alias_template = result.module.declarations.namespaces[0].declarations.alias_templates[0]
        self.assertEqual(self._hint_spellings(alias_template), ["Alias<N>"])

    def test_parse_headers_keep_separate_hints_for_defaulted_template_template_arguments(self) -> None:
        source = """
            namespace demo {

            template <class T>
            struct Box {
                T value {};
            };

            template <class T, template <class> class Wrapper = Box>
            struct Holder {
                Wrapper<T> value {};
            };

            using IntHolder = Holder<int>;
            using ExplicitIntHolder = Holder<int, Box>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        holder_template = namespace.declarations.class_templates[1]
        self.assertEqual(
            self._hint_spellings(holder_template),
            ["Holder<int>", "Holder<int,Box>"],
        )

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
        self.assertEqual(self._hint_spellings(box_template), ["Box<RelicInfo>"])
        self.assertEqual(len(self._hint_locations(box_template)[0]), 3)

    def test_parse_headers_keep_hint_for_defaulted_trailing_type_arguments(self) -> None:
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
        self.assertEqual(self._hint_spellings(box_template), ["Box<int>"])

    def test_parse_headers_keep_separate_hints_for_implicit_and_explicit_defaults(self) -> None:
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
        self.assertEqual(
            self._hint_spellings(box_template),
            ["Box<int>", "Box<int,double>"],
        )

    def test_parse_headers_collects_template_observation_hints_through_pointer_wrappers(self) -> None:
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
        self.assertEqual(self._hint_spellings(box_template), ["Box<int>"])
        self.assertEqual(len(self._hint_locations(box_template)[0]), 1)

    def test_parse_headers_collects_nested_template_observation_hints(self) -> None:
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

        self.assertEqual(self._hint_spellings(box_template), ["Box<int>"])
        self.assertEqual(self._hint_spellings(holder_template), ["Holder<Box<int>>"])

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

        self.assertEqual(self._hint_spellings(box_template), ["Box<int>"])
        self.assertIsInstance(int_box.cpp.target, TemplateInstanceCppType)
        self.assertEqual(int_box.cpp.target.template_name, "Box")
        self.assertIsInstance(int_box_alias.cpp.target, NamedCppType)
        self.assertEqual(int_box_alias.cpp.target.name, "IntBox")
        self.assertIs(int_box_alias.cpp.target.declaration, int_box)

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
        self.assertEqual(class_template.declaration.declarations.method_templates, [])
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

        self.assertEqual(class_template.declaration.declarations.method_templates, [])
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

        self.assertEqual(class_template.declaration.declarations.method_templates, [])
        self.assertEqual(len(class_template.declaration.declarations.constructors), 1)

        constructor = class_template.declaration.declarations.constructors[0]
        self.assertEqual(constructor.name, "Range")
        self.assertEqual(constructor.cpp.original_name, "Range")
        self.assertEqual(len(constructor.cpp.template_parameters), 1)
        self.assertIsInstance(constructor.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(constructor.cpp.template_parameters[0].name, "Container")
        self.assertEqual(len(constructor.parameters), 1)
        self.assertEqual(constructor.parameters[0].name, "cont")

    def test_parse_headers_keeps_out_of_line_member_function_templates_as_method_templates(self) -> None:
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
        self.assertEqual(len(class_template.declaration.declarations.method_templates), 1)

        method_template = class_template.declaration.declarations.method_templates[0]
        self.assertIsInstance(method_template, CppMethodTemplate)
        self.assertEqual(method_template.name, "convert")
        self.assertEqual(method_template.declaration.name, "convert")
        self.assertEqual(len(method_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(method_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(method_template.declaration.cpp.template_parameters[0].name, "U")
        self.assertEqual(len(method_template.declaration.parameters), 1)
        self.assertEqual(method_template.declaration.parameters[0].name, "value")

    def test_parse_headers_keeps_member_function_templates_as_method_templates(self) -> None:
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
        self.assertEqual(len(class_template.declaration.declarations.method_templates), 1)

        method_template = class_template.declaration.declarations.method_templates[0]
        self.assertIsInstance(method_template, CppMethodTemplate)
        self.assertEqual(method_template.name, "convert")
        self.assertEqual(method_template.declaration.name, "convert")
        self.assertEqual(len(method_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(method_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(method_template.declaration.cpp.template_parameters[0].name, "U")
        self.assertEqual(len(method_template.declaration.parameters), 1)
        self.assertEqual(method_template.declaration.parameters[0].name, "value")

    def test_parse_headers_keeps_similarly_named_member_function_templates_as_method_templates(self) -> None:
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
        self.assertEqual(len(class_template.declaration.declarations.method_templates), 1)

        method_template = class_template.declaration.declarations.method_templates[0]
        self.assertIsInstance(method_template, CppMethodTemplate)
        self.assertEqual(method_template.name, "Boxify")
        self.assertEqual(method_template.declaration.name, "Boxify")
        self.assertEqual(len(method_template.declaration.cpp.template_parameters), 1)
        self.assertIsInstance(method_template.declaration.cpp.template_parameters[0], CppTypeTemplateParameter)
        self.assertEqual(method_template.declaration.cpp.template_parameters[0].name, "U")

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
        self.assertEqual(self._hint_spellings(class_template), ["Box<int>"])

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
        self.assertEqual(len(declaration.declarations.method_templates), 1)
        self.assertEqual(declaration.declarations.method_templates[0].name, "convert")
        self.assertIsNotNone(declaration.declarations.method_templates[0].declaration.cpp.location.definition)
        self.assertEqual(len(declaration.declarations.method_templates[0].declaration.parameters), 1)
        self.assertEqual(declaration.declarations.method_templates[0].declaration.parameters[0].name, "value")

    def test_parse_headers_merge_function_template_docs_defaults_and_definition_locations(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
                    namespace demo {

                    /**
                     * @brief Parse one value from the declaration path.
                     * @param value Value from the declaration.
                     */
                    template <class T>
                    T parse(T value = T{});

                    }
                """,
                "b.hpp": """
                    namespace demo {

                    /**
                     * @brief Parse one value from the richer definition path.
                     * @param value Value from the definition.
                     * @return One parsed value.
                     */
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
        function_template = namespace.declarations.function_templates[0]
        declaration = function_template.declaration

        self.assertEqual(function_template.name, "parse")
        self.assertIsNotNone(declaration.cpp.location.definition)
        self.assertEqual(len(declaration.cpp.location.declarations), 2)
        self.assertEqual(declaration.parameters[0].name, "value")
        self.assertEqual(declaration.parameters[0].cpp.default_value, "T{}")
        self.assertEqual(
            declaration.cpp.doc.parsed.brief,
            "Parse one value from the richer definition path.",
        )
        self.assertEqual(
            declaration.cpp.doc.parsed.parameters["value"],
            "Value from the definition.",
        )
        self.assertEqual(declaration.cpp.doc.parsed.returns, "One parsed value.")
        self.assertEqual(declaration.parameters[0].cpp.doc, "Value from the definition.")

    def test_parse_headers_merge_method_template_docs_defaults_and_definition_locations(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
                    namespace demo {

                    template <class T>
                    class Box {
                    public:
                        /**
                         * @brief Convert one value from the declaration path.
                         * @param value Value from the declaration.
                         */
                        template <class U>
                        U convert(U value = U{}) const &;
                    };

                    }
                """,
                "b.hpp": """
                    namespace demo {

                    /**
                     * @brief Convert one value from the richer definition path.
                     * @param value Value from the definition.
                     * @return One converted value.
                     */
                    template <class T>
                    template <class U>
                    U Box<T>::convert(U value) const & {
                        return value;
                    }

                    }
                """,
            },
            header_order=["a.hpp", "b.hpp"],
        )

        declaration = result.module.declarations.namespaces[0].declarations.class_templates[0].declaration
        method_template = declaration.declarations.method_templates[0]
        method_declaration = method_template.declaration

        self.assertEqual(method_template.name, "convert")
        self.assertIsNotNone(method_declaration.cpp.location.definition)
        self.assertEqual(len(method_declaration.cpp.location.declarations), 2)
        self.assertTrue(method_declaration.cpp.is_const)
        self.assertEqual(method_declaration.cpp.ref_qualifier, "&")
        self.assertEqual(method_declaration.parameters[0].name, "value")
        self.assertEqual(method_declaration.parameters[0].cpp.default_value, "U{}")
        self.assertEqual(
            method_declaration.cpp.doc.parsed.brief,
            "Convert one value from the richer definition path.",
        )
        self.assertEqual(
            method_declaration.cpp.doc.parsed.parameters["value"],
            "Value from the definition.",
        )
        self.assertEqual(method_declaration.cpp.doc.parsed.returns, "One converted value.")
        self.assertEqual(method_declaration.parameters[0].cpp.doc, "Value from the definition.")

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

    def test_parse_headers_does_not_record_spurious_alias_template_instances_from_member_type_access(self) -> None:
        # Regression: alias template Vec<T> (1 param) wraps a 2-param Container<T, Alloc>.
        # When Vec<Leaf>::iterator is used as a template argument to DerefIter, the old code
        # extracted the template name from the spelling via find("<") and attributed the
        # canonical type's 2 arguments to it, creating a spurious 2-arg Vec/Container
        # observation that failed validation with "expected 0, got 2".
        source = """
            namespace demo {

            struct Leaf {};

            // raw_iter models the role of __gnu_cxx::__normal_iterator: a 2-param type
            // that becomes the canonical form of an iterator typedef.
            template <class Ptr, class ContainerRef>
            struct raw_iter {};

            // Container has a default second param (like std::vector's allocator).
            template <class T, class Alloc = T>
            struct Container {
                using iterator = raw_iter<T*, Container<T, Alloc>>;
                using const_iterator = raw_iter<const T*, Container<T, Alloc>>;
            };

            // One-param alias template (like ContainerType = std::vector<unique_ptr<T>>).
            template <class T>
            using Vec = Container<T>;

            // DerefIter models DereferenceIterator: takes one iterator-type argument.
            template <class Iter>
            struct DerefIter {};

            // Direct instantiation: produces exactly one observed instance for Vec with
            // one argument (Leaf).
            using LeafVec = Vec<Leaf>;

            // Member-type-access: Vec<Leaf>::iterator used as template argument.
            // Must NOT create additional observed instances for Vec or Container.
            using IterLeaf = DerefIter<Vec<Leaf>::iterator>;
            using ConstIterLeaf = DerefIter<Vec<Leaf>::const_iterator>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})
        self.assertFalse(result.report.has_errors())

        namespace = result.module.declarations.namespaces[0]

        alias_templates = {t.name: t for t in namespace.declarations.alias_templates}
        vec = alias_templates["Vec"]

        # Vec should have exactly one observed instance (from `using LeafVec = Vec<Leaf>`).
        # The two DerefIter<Vec<Leaf>::iterator/const_iterator> usages must not add any
        # extra observations, regardless of how many canonical type args the iterator has.
        hints = self._hint_spellings(vec)
        self.assertEqual(hints, ["Vec<Leaf>"], "Vec must have exactly one direct-use template hint")

    def test_parse_headers_does_not_record_spurious_observations_for_multiple_member_type_access_usages(self) -> None:
        # Same regression as above but with multiple distinct instantiation types to verify
        # the count is proportional to direct usages only.
        source = """
            namespace demo {

            struct Leaf {};
            struct Node {};
            struct Edge {};

            template <class Ptr, class ContainerRef>
            struct raw_iter {};

            template <class T, class Alloc = T>
            struct Container {
                using iterator = raw_iter<T*, Container<T, Alloc>>;
            };

            template <class T>
            using Vec = Container<T>;

            template <class Iter>
            struct DerefIter {};

            // Three direct instantiations -> three observed instances for Vec.
            using LeafVec = Vec<Leaf>;
            using NodeVec = Vec<Node>;
            using EdgeVec = Vec<Edge>;

            // Six member-type-access usages -> must add zero extra Vec observations.
            using IterLeaf  = DerefIter<Vec<Leaf>::iterator>;
            using IterNode  = DerefIter<Vec<Node>::iterator>;
            using IterEdge  = DerefIter<Vec<Edge>::iterator>;

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})
        self.assertFalse(result.report.has_errors())

        namespace = result.module.declarations.namespaces[0]
        alias_templates = {t.name: t for t in namespace.declarations.alias_templates}
        vec = alias_templates["Vec"]

        hints = self._hint_spellings(vec)
        self.assertEqual(
            hints,
            ["Vec<Leaf>", "Vec<Node>", "Vec<Edge>"],
            "Vec must have exactly three direct-use template hints with no extras "
            "from the member-type-access usages",
        )
