from __future__ import annotations

from pathlib import Path
import unittest

from oroboros.model import *
from oroboros.model.inspect import format_element, format_tree, summarize_tree
from oroboros.parse import ParseResult, ParserDiagnostic
from oroboros.parse.inspect import format_diagnostics, format_parse_result, summarize_parse_result


class ModelInspectTest(unittest.TestCase):
    def test_format_element_describes_supported_node_kinds(self) -> None:
        namespace = CppNamespace(name="demo")
        class_ = CppClass(name="Widget")
        function = CppFunction(name="make_widget")
        method = CppMethod(name="size")
        parameter = CppParameter(name="value")
        member_variable = CppVariable(name="size_")
        member_variable.cpp.kind = "member_variable"
        static_member_variable = CppVariable(name="instance_count")
        static_member_variable.cpp.kind = "static_member_variable"
        scope_variable = CppVariable(name="global_count")

        self.assertEqual(format_element(namespace), "namespace demo")
        self.assertEqual(format_element(class_), "class Widget")
        self.assertEqual(format_element(function), "function make_widget")
        self.assertEqual(format_element(method), "method size")
        self.assertEqual(format_element(parameter), "parameter value")
        self.assertEqual(format_element(member_variable), "member variable size_")
        self.assertEqual(format_element(static_member_variable), "static member variable instance_count")
        self.assertEqual(format_element(scope_variable), "variable global_count")

    def test_format_tree_renders_indented_subtree(self) -> None:
        module = CppModule(name="module")
        namespace = module.add_namespace(CppNamespace(name="demo"))
        class_ = namespace.add_class(CppClass(name="Widget"))
        method = class_.add_method(CppMethod(name="size"))
        method.add_parameter(CppParameter(name="value"))
        namespace.add_function(CppFunction(name="make_widget"))

        rendered = format_tree(module)

        self.assertEqual(
            rendered,
            "\n".join(
                [
                    "- namespace demo",
                    "  - class Widget",
                    "    - method size",
                    "      - parameter value",
                    "  - function make_widget",
                ]
            ),
        )

    def test_summarize_tree_counts_semantic_nodes(self) -> None:
        module = CppModule(name="module")
        namespace = module.add_namespace(CppNamespace(name="demo"))
        class_ = namespace.add_class(CppClass(name="Widget"))
        class_.add_method(CppMethod(name="size"))
        class_.add_variable(CppVariable(name="size_")).cpp.kind = "member_variable"
        class_.add_static_variable(CppVariable(name="instance_count")).cpp.kind = "static_member_variable"
        namespace.add_variable(CppVariable(name="global_count"))
        namespace.add_function(CppFunction(name="make_widget"))

        summary = summarize_tree(module)

        self.assertIn("Model summary:", summary)
        self.assertIn("total elements: 8", summary)
        self.assertIn("namespaces: 1", summary)
        self.assertIn("classes: 1", summary)
        self.assertIn("functions: 1", summary)
        self.assertIn("methods: 1", summary)
        self.assertIn("variables: 3", summary)
        self.assertIn("scope variables: 1", summary)
        self.assertIn("member variables: 1", summary)
        self.assertIn("static member variables: 1", summary)
        self.assertIn("parameters: 0", summary)


class ParseInspectTest(unittest.TestCase):
    def test_format_diagnostics_renders_empty_and_non_empty_lists(self) -> None:
        self.assertEqual(format_diagnostics([]), "Clang diagnostics: none")

        diagnostics = [
            ParserDiagnostic(
                severity="warning",
                message="demo warning",
            )
        ]
        rendered = format_diagnostics(diagnostics)

        self.assertIn("Clang diagnostics:", rendered)
        self.assertIn("[warning] <unknown location>: demo warning", rendered)

    def test_summarize_parse_result_reports_basic_counts(self) -> None:
        module = CppModule(name="module")
        namespace = module.add_namespace(CppNamespace(name="demo"))
        namespace.add_function(CppFunction(name="make_widget"))
        result = ParseResult(
            module=module,
            headers=[Path("/tmp/project/demo.hpp")],
            diagnostics=[
                ParserDiagnostic(severity="warning", message="warning"),
                ParserDiagnostic(severity="error", message="error"),
            ],
            warnings=["inactive dependency"],
            skipped_kind_counts={"TYPEDEF_DECL": 2, "UNION_DECL": 1},
        )

        summary = summarize_parse_result(result)

        self.assertIn("Parse summary:", summary)
        self.assertIn("input headers: 1", summary)
        self.assertIn("clang diagnostics: 2", summary)
        self.assertIn("parser warnings: 1", summary)
        self.assertIn("skipped unsupported entities: 3", summary)
        self.assertIn("skipped cursor kinds: 2", summary)
        self.assertIn("errors: 1", summary)
        self.assertIn("warnings: 1", summary)
        self.assertIn("functions: 1", summary)

    def test_format_parse_result_includes_summary_tree_and_diagnostics(self) -> None:
        module = CppModule(name="module")
        namespace = module.add_namespace(CppNamespace(name="demo"))
        namespace.add_function(CppFunction(name="make_widget"))
        result = ParseResult(
            module=module,
            headers=[Path("/tmp/project/demo.hpp")],
            diagnostics=[
                ParserDiagnostic(
                    severity="fatal",
                    message="stddef.h not found",
                )
            ],
            warnings=["Skipped unsupported libclang cursor kinds: TYPEDEF_DECL (2), UNION_DECL (1)"],
            skipped_kind_counts={"TYPEDEF_DECL": 2, "UNION_DECL": 1},
        )

        rendered = format_parse_result(result)

        self.assertIn("Parse summary:", rendered)
        self.assertIn("Parser input headers:", rendered)
        self.assertIn("/tmp/project/demo.hpp", rendered)
        self.assertIn("Semantic tree:", rendered)
        self.assertIn("- namespace demo", rendered)
        self.assertIn("- function make_widget", rendered)
        self.assertIn("[fatal] <unknown location>: stddef.h not found", rendered)
        self.assertIn("Skipped unsupported cursor kinds:\n  TYPEDEF_DECL: 2\n  UNION_DECL: 1", rendered)
        self.assertIn(
            "Parser warnings:\n  Skipped unsupported libclang cursor kinds: TYPEDEF_DECL (2), UNION_DECL (1)",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
