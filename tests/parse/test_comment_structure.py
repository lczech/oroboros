from __future__ import annotations

import unittest

from oroboros.parse.comment_structure import parse_cpp_doc


class ParseCommentsTest(unittest.TestCase):
    def test_parse_cpp_doc_normalizes_multiple_comment_styles_consistently(self) -> None:
        raw_comments = [
            """
/// Build one widget.
///
/// @param value Input value.
/// @return One widget.
""",
            """
/*!
 * Build one widget.
 *
 * \\param value Input value.
 * \\return One widget.
 */
""",
            """
/**
 * Build one widget.
 *
 * @param value Input value.
 * @return One widget.
 */
""",
            """
// Build one widget.
//
// @param value Input value.
// @return One widget.
""",
        ]

        for raw_comment in raw_comments:
            with self.subTest(raw_comment=raw_comment.splitlines()[1].strip() if "\n" in raw_comment else raw_comment):
                cpp_doc = parse_cpp_doc(raw_comment)
                self.assertIsNotNone(cpp_doc)
                self.assertEqual(cpp_doc.brief, "Build one widget.")
                self.assertEqual(cpp_doc.parameters["value"], "Input value.")
                self.assertEqual(cpp_doc.returns, "One widget.")

    def test_parse_cpp_doc_prefers_explicit_brief_and_details(self) -> None:
        raw_comment = """
/**
 * @brief Build one widget.
 * @details Used by the demo API.
 *
 * Extra implementation-facing detail.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertEqual(
            cpp_doc.description,
            "Used by the demo API.\n\nExtra implementation-facing detail.",
        )

    def test_parse_cpp_doc_splits_multiline_brief_from_following_plain_description(self) -> None:
        raw_comment = """
/**
 * @brief Build one widget from the current
 * state and cached factory configuration.
 *
 * Use this overload for the common path.
 * It keeps the default ownership rules.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(
            cpp_doc.brief,
            "Build one widget from the current state and cached factory configuration.",
        )
        self.assertEqual(
            cpp_doc.description,
            "Use this overload for the common path. It keeps the default ownership rules.",
        )

    def test_parse_cpp_doc_extracts_mixed_known_unknown_tags_and_plain_prose(self) -> None:
        raw_comment = """
/**
 * @brief Build one widget.
 * @param value Input value.
 * @remark Keep this visible.
 *
 * Plain prose follows here.
 * @custom One custom tag we do not parse yet.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertEqual(cpp_doc.parameters["value"], "Input value.")
        self.assertIn("@remark Keep this visible.", cpp_doc.description)
        self.assertIn("Plain prose follows here.", cpp_doc.description)
        self.assertIn("@custom One custom tag we do not parse yet.", cpp_doc.description)

    def test_parse_cpp_doc_extracts_doxygen_tags(self) -> None:
        raw_comment = """
/**
 * Build one widget from the current state.
 *
 * @param value Input value used by the factory.
 * @return One newly created widget.
 * @note This is only an example.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget from the current state.")
        self.assertEqual(cpp_doc.parameters, {"value": "Input value used by the factory."})
        self.assertEqual(cpp_doc.returns, "One newly created widget.")
        self.assertEqual(cpp_doc.notes, ["This is only an example."])

    def test_parse_cpp_doc_extracts_qt_style_tags(self) -> None:
        raw_comment = """
/*!
 * Build one widget.
 * \\param value Input value.
 * \\return One widget.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertEqual(cpp_doc.parameters["value"], "Input value.")
        self.assertEqual(cpp_doc.returns, "One widget.")

    def test_parse_cpp_doc_extracts_template_return_value_and_deprecated_tags(self) -> None:
        raw_comment = """
/**
 * @brief Build one widget.
 * @tparam Factory Factory type used to create the widget.
 * @retval true A widget was created successfully.
 * @retval false No widget could be created.
 * @deprecated Prefer build_widget_v2().
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertEqual(
            cpp_doc.template_parameters["Factory"],
            "Factory type used to create the widget.",
        )
        self.assertEqual(
            cpp_doc.return_values,
            {
                "true": "A widget was created successfully.",
                "false": "No widget could be created.",
            },
        )
        self.assertEqual(cpp_doc.deprecated, "Prefer build_widget_v2().")

    def test_parse_cpp_doc_collects_multi_paragraph_tag_bodies(self) -> None:
        raw_comment = """
/**
 * @brief Build one widget.
 * @param value First parameter paragraph.
 *
 *   Second parameter paragraph after a blank line.
 * @tparam Factory First template paragraph.
 *
 *   Second template paragraph.
 * @return First return paragraph.
 *
 *   Second return paragraph.
 * @warning First warning paragraph.
 *
 *   Second warning paragraph.
 * @deprecated First deprecated paragraph.
 *
 *   Second deprecated paragraph.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(
            cpp_doc.parameters["value"],
            "First parameter paragraph.\n\nSecond parameter paragraph after a blank line.",
        )
        self.assertEqual(
            cpp_doc.template_parameters["Factory"],
            "First template paragraph.\n\nSecond template paragraph.",
        )
        self.assertEqual(
            cpp_doc.returns,
            "First return paragraph.\n\nSecond return paragraph.",
        )
        self.assertEqual(
            cpp_doc.warnings,
            ["First warning paragraph.\n\nSecond warning paragraph."],
        )
        self.assertEqual(
            cpp_doc.deprecated,
            "First deprecated paragraph.\n\nSecond deprecated paragraph.",
        )

    def test_parse_cpp_doc_collects_multiline_parameter_docs(self) -> None:
        raw_comment = """
/**
 * Build one widget.
 * @param value Input value used by the factory
 *   and reused by the fallback path.
 * @param mode Optional mode selector.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(
            cpp_doc.parameters["value"],
            "Input value used by the factory and reused by the fallback path.",
        )
        self.assertEqual(cpp_doc.parameters["mode"], "Optional mode selector.")

    def test_parse_cpp_doc_accepts_parameter_direction_annotations(self) -> None:
        raw_comment = """
/**
 * Build one widget.
 * @param[in] value Input value used by the factory.
 * @param[out] result Output slot used by the builder.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.parameters["value"], "Input value used by the factory.")
        self.assertEqual(cpp_doc.parameters["result"], "Output slot used by the builder.")

    def test_parse_cpp_doc_treats_plain_comments_as_prose(self) -> None:
        raw_comment = """
// Build one widget.
//
// Used by the demo API.
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertEqual(cpp_doc.description, "Used by the demo API.")

    def test_parse_cpp_doc_handles_odd_block_indentation(self) -> None:
        raw_comment = """
        /**
         *    Build one widget.
         *
         *    Used by the demo API.
         */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertEqual(cpp_doc.description, "Used by the demo API.")

    def test_parse_cpp_doc_normalizes_common_inline_markup(self) -> None:
        raw_comment = r"""
/**
 * Build one widget with @c WidgetFactory.
 *
 * See also @ref demo::Widget and
 * @link demo::Builder the builder API @endlink.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget with `WidgetFactory`.")
        self.assertEqual(
            cpp_doc.description,
            "See also demo::Widget and the builder API (demo::Builder).",
        )

    def test_parse_cpp_doc_normalizes_code_blocks_into_markdown_fences(self) -> None:
        raw_comment = """
/**
 * Build one widget.
 *
 * Example usage:
 * @code{.cpp}
 * Widget widget;
 * widget.build();
 * @endcode
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertEqual(
            cpp_doc.description,
            "Example usage:\n\n```cpp\nWidget widget;\nwidget.build();\n```",
        )

    def test_parse_cpp_doc_supports_multiple_code_blocks_and_languages(self) -> None:
        raw_comment = """
/**
 * Build one widget.
 *
 * First example:
 * @code
 * Widget widget;
 * @endcode
 *
 * Second example:
 *
 *     widget.build()
 *
 * Final Python example:
 * @code{.py}
 * widget = make_widget()
 * @endcode
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(
            cpp_doc.description,
            "First example:\n\n```cpp\nWidget widget;\n```\n\nSecond example:\n\n```\nwidget.build()\n```\n\nFinal Python example:\n\n```py\nwidget = make_widget()\n```",
        )

    def test_parse_cpp_doc_preserves_unknown_inline_markup_and_punctuation(self) -> None:
        raw_comment = r"""
/**
 * Build one widget near @ref demo::Widget, @c WidgetFactory, and
 * @link demo::Builder the builder API @endlink while leaving @broken untouched.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(
            cpp_doc.brief,
            "Build one widget near demo::Widget, `WidgetFactory`, and the builder API (demo::Builder) while leaving @broken untouched.",
        )

    def test_parse_cpp_doc_normalizes_indented_code_blocks_into_markdown_fences(self) -> None:
        raw_comment = """
/**
 * Build one widget.
 *
 * Example usage:
 *
 *     Widget widget;
 *     widget.build();
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertEqual(
            cpp_doc.description,
            "Example usage:\n\n```\nWidget widget;\nwidget.build();\n```",
        )

    def test_parse_cpp_doc_keeps_blank_lines_inside_indented_code_blocks(self) -> None:
        raw_comment = """
/**
 * Build one widget.
 *
 * Example usage:
 *
 *     Widget widget;
 *
 *     widget.build();
 *
 * Continue with normal prose afterwards.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertEqual(
            cpp_doc.description,
            "Example usage:\n\n```\nWidget widget;\n\nwidget.build();\n```\n\nContinue with normal prose afterwards.",
        )

    def test_parse_cpp_doc_handles_tabs_and_comment_starting_with_code_block(self) -> None:
        raw_comment = """
/**
 *\tWidget widget;
 *\twidget.build();
 *
 * Continue with normal prose afterwards.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertIsNone(cpp_doc.brief)
        self.assertEqual(
            cpp_doc.description,
            "```\nWidget widget;\nwidget.build();\n```\n\nContinue with normal prose afterwards.",
        )

    def test_parse_cpp_doc_collects_repeated_warning_and_see_alias_tags(self) -> None:
        raw_comment = """
/**
 * @brief Build one widget.
 * @warning Avoid reused state.
 * @warning Keep the factory alive.
 * @sa demo::make_other_widget
 * @see demo::Widget
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertEqual(
            cpp_doc.warnings,
            ["Avoid reused state.", "Keep the factory alive."],
        )
        self.assertEqual(
            cpp_doc.see_also,
            ["demo::make_other_widget", "demo::Widget"],
        )

    def test_parse_cpp_doc_collects_repeated_deprecated_paragraphs(self) -> None:
        raw_comment = """
/**
 * @brief Build one widget.
 * @deprecated Prefer make_widget_v2().
 * @deprecated This overload will be removed in the next major release.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(
            cpp_doc.deprecated,
            "Prefer make_widget_v2().\n\nThis overload will be removed in the next major release.",
        )

    def test_parse_cpp_doc_handles_single_line_brief_block(self) -> None:
        raw_comment = "/** @brief Build one widget. */"

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertIsNone(cpp_doc.description)

    def test_parse_cpp_doc_preserves_unknown_tags_in_description(self) -> None:
        raw_comment = """
/**
 * Build one widget.
 * @remark Keep this text visible.
 * @custom Widget{} still needs a custom parser later.
 */
"""

        cpp_doc = parse_cpp_doc(raw_comment)

        self.assertIsNotNone(cpp_doc)
        self.assertEqual(cpp_doc.brief, "Build one widget.")
        self.assertIn("@remark Keep this text visible.", cpp_doc.description)
        self.assertIn("@custom Widget{} still needs a custom parser later.", cpp_doc.description)


if __name__ == "__main__":
    unittest.main()
