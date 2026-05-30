from __future__ import annotations

import unittest

from oroboros.model import *
from tests.support.parse_helpers import parse_headers_from_sources as _parse_headers_from_sources


class ParseIntegrationSpecialMembersTest(unittest.TestCase):
    def test_parse_headers_materializes_destructor_cpp_facts_and_docs(self) -> None:
        source = """
            namespace demo {

            class Widget {
            public:
                /** Destroy one widget. */
                virtual ~Widget() = default;
            };

            class Locked {
            private:
                ~Locked() = delete;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = next(class_ for class_ in namespace.declarations.classes if class_.name == "Widget")
        locked = next(class_ for class_ in namespace.declarations.classes if class_.name == "Locked")

        widget_destructor = widget.declarations.destructor
        locked_destructor = locked.declarations.destructor

        self.assertIsNotNone(widget_destructor)
        self.assertEqual(widget_destructor.name, "~Widget")
        self.assertEqual(widget_destructor.cpp.original_name, "~Widget")
        self.assertEqual(widget_destructor.cpp.visibility, CppVisibility.PUBLIC)
        self.assertTrue(widget_destructor.cpp.is_virtual)
        self.assertTrue(widget_destructor.cpp.is_defaulted)
        self.assertFalse(widget_destructor.cpp.is_deleted)
        self.assertEqual(widget_destructor.cpp.doc.parsed.brief, "Destroy one widget.")
        self.assertEqual(widget.declarations.methods, [])

        self.assertIsNotNone(locked_destructor)
        self.assertEqual(locked_destructor.name, "~Locked")
        self.assertEqual(locked_destructor.cpp.visibility, CppVisibility.PRIVATE)
        self.assertTrue(locked_destructor.cpp.is_deleted)
        self.assertFalse(locked_destructor.cpp.is_virtual)
        self.assertFalse(locked_destructor.cpp.is_defaulted)

    def test_parse_headers_merges_redeclared_destructor_definition_locations(self) -> None:
        source = """
            namespace demo {

            class Widget {
            public:
                /** Destroy the widget from its declaration. */
                ~Widget();
            };

            inline Widget::~Widget() {}

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        widget = result.module.declarations.namespaces[0].declarations.classes[0]
        destructor = widget.declarations.destructor

        self.assertIsNotNone(destructor)
        self.assertEqual(destructor.cpp.doc.parsed.brief, "Destroy the widget from its declaration.")
        self.assertEqual(len(destructor.cpp.location.declarations), 2)
        self.assertIsNotNone(destructor.cpp.location.definition)

    def test_parse_headers_materializes_pure_virtual_destructor_with_definition(self) -> None:
        source = """
            namespace demo {

            class Spirit {
            public:
                virtual ~Spirit() = 0;
            };

            inline Spirit::~Spirit() {}

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        spirit = result.module.declarations.namespaces[0].declarations.classes[0]
        destructor = spirit.declarations.destructor

        self.assertIsNotNone(destructor)
        self.assertTrue(destructor.cpp.is_virtual)
        self.assertTrue(destructor.cpp.is_pure_virtual)
        self.assertFalse(destructor.cpp.is_deleted)
        self.assertFalse(destructor.cpp.is_defaulted)
        self.assertIsNotNone(destructor.cpp.location.definition)

    def test_parse_headers_materializes_class_template_destructors(self) -> None:
        source = """
            namespace demo {

            template <class T>
            struct Box {
                ~Box() = default;
            };

            }
        """

        result = _parse_headers_from_sources({"demo.hpp": source})

        class_template = result.module.declarations.namespaces[0].declarations.class_templates[0]
        destructor = class_template.declaration.declarations.destructor

        self.assertIsNotNone(destructor)
        self.assertEqual(destructor.name, "~Box")
        self.assertTrue(destructor.cpp.is_defaulted)
        self.assertFalse(destructor.cpp.is_virtual)
