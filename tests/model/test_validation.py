from __future__ import annotations

from pathlib import Path
import unittest

from oroboros.model import *
from tests.support.model_builders import make_class, make_class_template_declaration, make_module, make_namespace


class ModelValidationTest(unittest.TestCase):
    def test_validate_tree_accepts_consistent_child_owner_links(self) -> None:
        module = make_module(name="bindings")
        namespace = module.add_namespace(make_namespace(name="demo"))
        cls = namespace.add_class(make_class(name="Widget"))
        method = cls.add_method(CppMethod(name="size"))
        method.add_parameter(CppParameter(name="value"))

        module.validate_tree()

    def test_validate_tree_rejects_direct_list_mutation_without_owner_update(self) -> None:
        module = make_module(name="bindings")
        namespace = module.add_namespace(make_namespace(name="demo"))
        namespace.declarations.classes.append(make_class(name="Widget"))

        with self.assertRaises(ModelValidationError):
            module.validate_tree()

    def test_validate_semantics_accepts_consistent_declaration_linked_named_types(self) -> None:
        cls = make_class(name="Widget")
        method = CppMethod(
            name="set_widget",
            parameters=[
                CppParameter(
                    name="value",
                    cpp=CppParameterCppFacet(
                        type=NamedCppType(name="Widget", declaration=cls),
                    ),
                )
            ],
        )
        cls.add_method(method)
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_rejects_named_type_name_mismatch(self) -> None:
        cls = make_class(name="Widget")
        function = CppFunction(
            name="take_widget",
            parameters=[
                CppParameter(
                    name="value",
                    cpp=CppParameterCppFacet(
                        type=NamedCppType(name="OtherWidget", declaration=cls),
                    ),
                )
            ],
        )
        namespace = make_namespace(name="demo", classes=[cls], functions=[function])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError) as context:
            module.validate_semantics()

        self.assertIn('module.namespace["demo"]', str(context.exception))
        self.assertIn('function["take_widget"][0]', str(context.exception))
        self.assertIn('parameter["value"]', str(context.exception))
        self.assertNotIn(".declarations.", str(context.exception))

    def test_validate_semantics_rejects_non_class_base_declarations(self) -> None:
        enum_ = CppEnum(name="Kind")
        cls = make_class(name="Widget")
        cls.cpp.bases.append(
            CppClassBase(
                type=NamedCppType(name="Kind", declaration=enum_),
            )
        )
        namespace = make_namespace(name="demo", classes=[cls], enums=[enum_])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_parameters_owned_by_non_function_like_scopes(self) -> None:
        namespace = make_namespace(name="demo")
        parameter = CppParameter(name="value")
        namespace.declarations.functions.append(parameter)
        parameter.owner = namespace
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_constructor_name_mismatches(self) -> None:
        cls = make_class(
            name="Widget",
            constructors=[CppConstructor(name="OtherWidget")],
        )
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_method_flag_combinations(self) -> None:
        pure_virtual_only = CppMethod(name="foo")
        pure_virtual_only.cpp.is_pure_virtual = True

        static_virtual = CppMethod(name="bar")
        static_virtual.cpp.is_static = True
        static_virtual.cpp.is_virtual = True

        static_ref_qualified = CppMethod(name="zap")
        static_ref_qualified.cpp.is_static = True
        static_ref_qualified.cpp.ref_qualifier = "&"

        cls = make_class(
            name="Widget",
            methods=[pure_virtual_only, static_virtual, static_ref_qualified],
        )
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_union_bases_and_virtual_methods(self) -> None:
        base = make_class(name="Base")
        union_ = make_class(name="Storage")
        union_.cpp.kind = "union"
        union_.cpp.bases.append(
            CppClassBase(type=NamedCppType(name="Base", declaration=base))
        )
        union_method = CppMethod(name="visit")
        union_method.cpp.is_virtual = True
        union_.add_method(union_method)
        namespace = make_namespace(name="demo", classes=[base, union_])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_pure_virtual_union_methods(self) -> None:
        union_ = make_class(name="Storage")
        union_.cpp.kind = "union"
        union_method = CppMethod(name="visit")
        union_method.cpp.is_virtual = True
        union_method.cpp.is_pure_virtual = True
        union_.add_method(union_method)
        namespace = make_namespace(name="demo", classes=[union_])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_virtual_union_method_templates(self) -> None:
        union_ = make_class(name="Storage")
        union_.cpp.kind = "union"
        method_template = CppMethodTemplate(name="convert")
        method_template.declaration.cpp.is_virtual = True
        union_.add_method_template(method_template)
        namespace = make_namespace(name="demo", classes=[union_])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_pure_virtual_union_method_templates(self) -> None:
        union_ = make_class(name="Storage")
        union_.cpp.kind = "union"
        method_template = CppMethodTemplate(name="convert")
        method_template.declaration.cpp.is_virtual = True
        method_template.declaration.cpp.is_pure_virtual = True
        union_.add_method_template(method_template)
        namespace = make_namespace(name="demo", classes=[union_])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_accepts_non_virtual_unions(self) -> None:
        union_ = make_class(name="Storage")
        union_.cpp.kind = "union"
        union_.add_method(CppMethod(name="active_count"))
        namespace = make_namespace(name="demo", classes=[union_])
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_rejects_union_class_template_bases_and_virtual_methods(self) -> None:
        base = make_class(name="Base")
        union_template = CppClassTemplate(name="Storage")
        union_template.declaration.cpp.kind = "union"
        union_template.declaration.cpp.bases.append(
            CppClassBase(type=NamedCppType(name="Base", declaration=base))
        )
        method = CppMethod(name="visit")
        method.cpp.is_virtual = True
        union_template.declaration.add_method(method)
        namespace = make_namespace(name="demo", classes=[base], class_templates=[union_template])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_ref_qualifier_values(self) -> None:
        method = CppMethod(name="foo")
        method.cpp.ref_qualifier = "value-ish"

        cls = make_class(name="Widget", methods=[method])
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_cpp_original_name_mismatches(self) -> None:
        cls = make_class(name="Widget")
        cls.cpp.original_name = "OriginalWidget"
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_duplicate_non_overload_child_names(self) -> None:
        namespace = make_namespace(
            name="demo",
            classes=[make_class(name="Widget"), make_class(name="Widget")],
        )
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_duplicate_alias_names_in_one_scope(self) -> None:
        namespace = make_namespace(name="demo")
        namespace.add_alias(CppAlias(name="Index")).cpp.target = NamedCppType(name="std::size_t")
        namespace.add_alias(CppAlias(name="Index")).cpp.target = BuiltinCppType(kind="unsigned_long")
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_duplicate_alias_template_names_in_one_scope(self) -> None:
        first = CppAliasTemplate(name="Vec")
        first.declaration.cpp.target = TemplateInstanceCppType(
            template_name="Box",
            arguments=[CppTypeTemplateArgument(type=NamedCppType(name="T"))],
        )
        second = CppAliasTemplate(name="Vec")
        second.declaration.cpp.target = PointerCppType(
            pointee=NamedCppType(name="T"),
        )
        namespace = make_namespace(name="demo", alias_templates=[first, second])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_aliases_without_target_types(self) -> None:
        namespace = make_namespace(name="demo", aliases=[CppAlias(name="Index")])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_alias_templates_without_target_types(self) -> None:
        namespace = make_namespace(name="demo", alias_templates=[CppAliasTemplate(name="Vec")])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_template_family_name_mismatches(self) -> None:
        function_template = CppFunctionTemplate(name="make_value")
        function_template.declaration.name = "other_value"
        namespace = make_namespace(name="demo", function_templates=[function_template])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_template_instance_arguments(self) -> None:
        function_template = CppFunctionTemplate(name="make_value")
        function_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        instance = add_function_template_instance(
            function_template,
            [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
        )
        instance.cpp.template_arguments = [CppNonTypeTemplateArgument(value="4")]
        namespace = make_namespace(name="demo", function_templates=[function_template])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_alias_template_instance_arguments(self) -> None:
        alias_template = CppAliasTemplate(name="Vec")
        alias_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        alias_template.declaration.cpp.target = TemplateInstanceCppType(
            template_name="Box",
            arguments=[CppTypeTemplateArgument(type=NamedCppType(name="T"))],
        )
        instance = add_alias_template_instance(
            alias_template,
            [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
        )
        instance.cpp.template_arguments = [CppNonTypeTemplateArgument(value="4")]
        namespace = make_namespace(name="demo", alias_templates=[alias_template])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_named_type_declaration_targets(self) -> None:
        target_function = CppFunction(name="make_widget")
        using_function = CppFunction(
            name="take_widget",
            parameters=[
                CppParameter(
                    name="value",
                    cpp=CppParameterCppFacet(
                        type=NamedCppType(name="make_widget", declaration=target_function),
                    ),
                )
            ],
        )
        namespace = make_namespace(
            name="demo",
            functions=[target_function, using_function],
        )
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_inconsistent_location_provenance(self) -> None:
        function = CppFunction(name="make_widget")
        function.cpp.location = CppLocationInfo(
            primary=SourceLocation(file=Path("api/widget.hpp"), line=10, column=5),
            declarations=[
                SourceLocation(file=Path("api/widget_fwd.hpp"), line=3, column=1),
                SourceLocation(file=Path("api/widget_fwd.hpp"), line=3, column=1),
            ],
            definition=SourceLocation(file=Path("api/widget.hpp"), line=20, column=1),
        )
        namespace = make_namespace(name="demo", functions=[function])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_overload_index_groups(self) -> None:
        first = CppMethod(name="foo")
        first.cpp.overload_index = 0
        second = CppMethod(name="foo")
        second.cpp.overload_index = 2
        cls = make_class(name="Widget", methods=[first, second])
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_observed_template_instances(self) -> None:
        function_template = CppFunctionTemplate(name="make_value")
        function_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        function_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(
                arguments=[CppNonTypeTemplateArgument(value="4")],
            )
        )
        namespace = make_namespace(name="demo", function_templates=[function_template])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_free_functions_owned_by_class_like_scopes(self) -> None:
        cls = make_class(name="Widget")
        stray_function = CppFunction(name="helper")
        cls.declarations.classes.append(stray_function)
        stray_function.owner = cls
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_implausible_cpp_identifier_names(self) -> None:
        function = CppFunction(name="bad-name")
        namespace = make_namespace(name="demo", functions=[function])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_accepts_operator_names(self) -> None:
        method = CppMethod(name="operator+")
        method.cpp.operator = CppOperator(kind="symbolic", symbol="+")
        cls = make_class(name="Widget", methods=[method])
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_accepts_dependent_typename_spellings_for_linked_alias_targets(self) -> None:
        document = make_class(name="JsonDocument")
        value_type = document.add_alias(CppAlias(name="value_type"))
        value_type.cpp.target = BuiltinCppType(kind="int")
        difference_type = document.add_alias(CppAlias(name="difference_type"))
        difference_type.cpp.target = BuiltinCppType(kind="long")

        iterator = CppClassTemplate(name="JsonIterator")
        iterator.declaration.add_alias(CppAlias(name="value_type")).cpp.target = NamedCppType(
            name="typename JsonDocument::value_type",
            declaration=value_type,
        )
        iterator.declaration.add_alias(CppAlias(name="difference_type")).cpp.target = NamedCppType(
            name="typename JsonDocument::difference_type",
            declaration=difference_type,
        )

        namespace = make_namespace(name="format", classes=[document], class_templates=[iterator])
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_accepts_template_argument_scope_spellings_for_linked_nested_types(self) -> None:
        widget_range = CppClassTemplate(name="WidgetRange")
        iterator = widget_range.declaration.add_class(make_class(name="Iterator"))
        self_type = iterator.add_alias(CppAlias(name="self_type"))
        self_type.cpp.target = NamedCppType(
            name="WidgetRange<MT, T>::Iterator",
            declaration=iterator,
        )

        namespace = make_namespace(name="demo", class_templates=[widget_range])
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_accepts_fully_qualified_template_owner_spellings_for_linked_nested_types(self) -> None:
        widget_range = CppClassTemplate(name="WidgetRange")
        iterator = widget_range.declaration.add_class(make_class(name="Iterator"))
        self_type = iterator.add_alias(CppAlias(name="self_type"))
        self_type.cpp.target = NamedCppType(
            name="::demo::WidgetRange<MT, T>::Iterator",
            declaration=iterator,
        )

        namespace = make_namespace(name="demo", class_templates=[widget_range])
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_accepts_dependent_typename_nested_class_spellings(self) -> None:
        widget_range = CppClassTemplate(name="WidgetRange")
        iterator = widget_range.declaration.add_class(make_class(name="Iterator"))
        self_type = iterator.add_alias(CppAlias(name="self_type"))
        self_type.cpp.target = NamedCppType(
            name="typename WidgetRange<MT, T>::Iterator",
            declaration=iterator,
        )

        namespace = make_namespace(name="demo", class_templates=[widget_range])
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_accepts_elaborated_nested_class_spellings(self) -> None:
        widget_range = CppClassTemplate(name="WidgetRange")
        iterator = widget_range.declaration.add_class(make_class(name="StackElement"))
        self_type = iterator.add_alias(CppAlias(name="self_type"))
        self_type.cpp.target = NamedCppType(
            name="struct StackElement",
            declaration=iterator,
        )

        namespace = make_namespace(name="demo", class_templates=[widget_range])
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_accepts_elaborated_class_spellings(self) -> None:
        cls = make_class(name="Widget")
        namespace = make_namespace(name="demo", classes=[cls])
        namespace.add_alias(CppAlias(name="widget_type")).cpp.target = NamedCppType(
            name="class Widget",
            declaration=cls,
        )
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_accepts_elaborated_union_spellings(self) -> None:
        cls = make_class(name="Storage")
        namespace = make_namespace(name="demo", classes=[cls])
        namespace.add_alias(CppAlias(name="storage_type")).cpp.target = NamedCppType(
            name="union Storage",
            declaration=cls,
        )
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_accepts_elaborated_enum_spellings(self) -> None:
        enum_ = CppEnum(name="Kind")
        namespace = make_namespace(name="demo", enums=[enum_])
        namespace.add_alias(CppAlias(name="kind_type")).cpp.target = NamedCppType(
            name="enum Kind",
            declaration=enum_,
        )
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_accepts_dependent_template_disambiguator_spellings(self) -> None:
        traits = CppClassTemplate(name="Traits")
        rebind = traits.declaration.add_class(make_class(name="Rebind"))
        type_alias = rebind.add_alias(CppAlias(name="type"))
        type_alias.cpp.target = BuiltinCppType(kind="int")

        holder = CppClassTemplate(name="Holder")
        holder.declaration.add_alias(CppAlias(name="value_type")).cpp.target = NamedCppType(
            name="typename Traits<T>::template Rebind<U>::type",
            declaration=type_alias,
        )

        namespace = make_namespace(name="demo", class_templates=[traits, holder])
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_accepts_fully_qualified_dependent_template_disambiguator_spellings(self) -> None:
        traits = CppClassTemplate(name="Traits")
        rebind = traits.declaration.add_class(make_class(name="Rebind"))
        type_alias = rebind.add_alias(CppAlias(name="type"))
        type_alias.cpp.target = BuiltinCppType(kind="int")

        holder = CppClassTemplate(name="Holder")
        holder.declaration.add_alias(CppAlias(name="value_type")).cpp.target = NamedCppType(
            name="typename ::demo::Traits<T>::template Rebind<U>::type",
            declaration=type_alias,
        )

        namespace = make_namespace(name="demo", class_templates=[traits, holder])
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_rejects_linked_named_types_with_wrong_terminal_name(self) -> None:
        document = make_class(name="JsonDocument")
        value_type = document.add_alias(CppAlias(name="value_type"))
        value_type.cpp.target = BuiltinCppType(kind="int")

        namespace = make_namespace(name="format")
        namespace.add_alias(CppAlias(name="bad_alias")).cpp.target = NamedCppType(
            name="typename JsonDocument::difference_type",
            declaration=value_type,
        )
        namespace.add_class(document)
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_linked_nested_types_with_wrong_terminal_name(self) -> None:
        widget_range = CppClassTemplate(name="WidgetRange")
        iterator = widget_range.declaration.add_class(make_class(name="Iterator"))
        self_type = iterator.add_alias(CppAlias(name="self_type"))
        self_type.cpp.target = NamedCppType(
            name="WidgetRange<MT, T>::ConstIterator",
            declaration=iterator,
        )

        namespace = make_namespace(name="demo", class_templates=[widget_range])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_accepts_wrong_owner_when_terminal_name_matches_link(self) -> None:
        first_range = CppClassTemplate(name="WidgetRange")
        first_iterator = first_range.declaration.add_class(make_class(name="Iterator"))
        second_range = CppClassTemplate(name="OtherRange")
        second_range.declaration.add_class(make_class(name="Iterator"))

        alias_holder = make_class(name="AliasHolder")
        alias_holder.add_alias(CppAlias(name="iter_type")).cpp.target = NamedCppType(
            name="OtherRange<MT, T>::Iterator",
            declaration=first_iterator,
        )

        namespace = make_namespace(
            name="demo",
            class_templates=[first_range, second_range],
            classes=[alias_holder],
        )
        module = make_module(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_rejects_alias_names_with_invalid_characters(self) -> None:
        namespace = make_namespace(name="demo")
        namespace.add_alias(CppAlias(name="Index-Alias")).cpp.target = NamedCppType(name="std::size_t")
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_whitespace_only_enumerator_values(self) -> None:
        enumerator = CppEnumerator(name="primary")
        enumerator.cpp.value_spelling = "   "
        enum_ = CppEnum(name="Kind", enumerators=[enumerator])
        namespace = make_namespace(name="demo", enums=[enum_])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()
