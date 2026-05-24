from __future__ import annotations

import unittest

from oroboros.model import *
from tests.support.model_builders import make_class, make_module, make_namespace


class ModelSpecialMembersTest(unittest.TestCase):
    def test_destructor_is_adopted_as_a_singular_class_child(self) -> None:
        destructor = CppDestructor(name="~Widget")
        cls = make_class(name="Widget", destructor=destructor)
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        self.assertIs(cls.declarations.destructor, destructor)
        self.assertIs(cls.destructor, destructor)
        self.assertIs(destructor.owner, cls)
        self.assertEqual(destructor.qualified_name, "demo::Widget::~Widget")
        self.assertIs(cls["~Widget"], destructor)
        self.assertIn("~Widget", cls.element_names)

        summary = summarize_tree(module)
        self.assertIn("destructors: 1", summary)
        self.assertIn("destructor ~Widget", format_tree(module))

    def test_add_destructor_rejects_a_second_distinct_destructor(self) -> None:
        cls = make_class(name="Widget")
        cls.add_destructor(CppDestructor(name="~Widget"))

        with self.assertRaises(ValueError):
            cls.add_destructor(CppDestructor(name="~Widget"))

    def test_validate_semantics_rejects_destructor_name_mismatches(self) -> None:
        cls = make_class(
            name="Widget",
            destructor=CppDestructor(name="~OtherWidget"),
        )
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_pure_virtual_destructor_without_virtual(self) -> None:
        destructor = CppDestructor(name="~Widget")
        destructor.cpp.is_pure_virtual = True
        cls = make_class(name="Widget", destructor=destructor)
        namespace = make_namespace(name="demo", classes=[cls])
        module = make_module(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()
