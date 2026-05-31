from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import tempfile
from textwrap import dedent
import unittest

from clang.cindex import TokenKind

from oroboros.headers import HeaderFile, HeaderSelection
from oroboros.parse import ParserConfig, parse_header_selection
from oroboros.parse.build_model import BuildContext
from oroboros.parse.comment_recovery import resolve_cursor_comment
from oroboros.parse.cursor_data import CursorTokenInfo


class ParseCommentIntegrationTest(unittest.TestCase):
    def test_resolve_cursor_comment_suppresses_warning_for_nonlocal_clang_raw_comment_when_recovered_comment_exists(self) -> None:
        header = Path("/tmp/project/demo.hpp").resolve()
        recovered_comment = """
/**
 * @brief Widget docs.
 */
""".strip()
        stale_raw_comment = """
// =================================================================================================
//     Forward Declarations
// =================================================================================================
""".strip()
        cursor = SimpleNamespace(
            spelling="Widget",
            raw_comment=stale_raw_comment,
            location=SimpleNamespace(
                file=SimpleNamespace(name=str(header)),
                line=10,
                column=7,
            ),
            extent=SimpleNamespace(
                start=SimpleNamespace(line=10, offset=100),
                end=SimpleNamespace(line=20, offset=150),
            ),
            is_definition=lambda: True,
            get_usr=lambda: None,
        )
        context = BuildContext(
            active_headers={header},
            known_project_headers={header},
            config=ParserConfig(),
            translation_unit=object(),
        )
        context.file_tokens_by_path[header] = [
            CursorTokenInfo(
                kind=TokenKind.COMMENT,
                spelling=recovered_comment,
                start_line=5,
                start_column=1,
                start_offset=50,
                end_line=9,
                end_column=4,
                end_offset=99,
            ),
        ]

        resolution = resolve_cursor_comment(cursor, context)

        self.assertEqual(resolution.selected_attached_comment, recovered_comment)
        self.assertEqual(resolution.selection_reason, "recovered_leading_block")
        self.assertFalse(context.report.diagnostics)

    def test_parse_headers_extracts_real_doxygen_comments(self) -> None:
        source = """
namespace demo {

/// Represent one widget in the real parsed headers.
struct Widget {};

/**
 * Build one widget from the current demo state.
 *
 * @param value Input value used by the example builder.
 * @return One newly created widget.
 */
Widget make_widget(int value);

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        function = namespace.declarations.functions[0]

        self.assertIsNotNone(widget.cpp.doc.attached_comment)
        self.assertIsNotNone(widget.cpp.doc.clang_raw_comment)
        self.assertIn("Represent one widget", widget.cpp.doc.attached_comment)
        self.assertIn("Represent one widget", widget.cpp.doc.clang_raw_comment)
        self.assertIsNotNone(widget.cpp.doc)
        self.assertEqual(widget.cpp.doc.parsed.brief, "Represent one widget in the real parsed headers.")
        self.assertIsNotNone(function.cpp.doc.attached_comment)
        self.assertIsNotNone(function.cpp.doc.clang_raw_comment)
        self.assertIn("Build one widget", function.cpp.doc.attached_comment)
        self.assertIn("@return One newly created widget.", function.cpp.doc.attached_comment)
        self.assertIsNotNone(function.cpp.doc)
        self.assertEqual(function.cpp.doc.parsed.brief, "Build one widget from the current demo state.")
        self.assertEqual(
            function.cpp.doc.parsed.parameters["value"],
            "Input value used by the example builder.",
        )
        self.assertEqual(function.cpp.doc.parsed.returns, "One newly created widget.")
        self.assertEqual(function.parameters[0].cpp.doc, "Input value used by the example builder.")

    def test_parse_headers_extracts_plain_comments_into_normalized_docs(self) -> None:
        source = """
namespace demo {

// Represent one widget.
//
// Used by the demo API.
struct Widget {};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        widget = result.module.declarations.namespaces[0].declarations.classes[0]

        self.assertIsNotNone(widget.cpp.doc.attached_comment)
        self.assertIsNotNone(widget.cpp.doc)
        self.assertEqual(widget.cpp.doc.parsed.brief, "Represent one widget.")
        self.assertEqual(widget.cpp.doc.parsed.description, "Used by the demo API.")

    def test_parse_headers_normalize_brief_details_multiline_params_and_links(self) -> None:
        source = r"""
namespace demo {

/**
 * @brief Build one widget.
 * @details Use @link demo::Widget the widget API @endlink for advanced flows.
 * @param value Input value used by the factory
 *   and reused by the fallback path.
 * @return One widget.
 */
Widget make_widget(int value);

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        function = result.module.declarations.namespaces[0].declarations.functions[0]

        self.assertIsNotNone(function.cpp.doc)
        self.assertEqual(function.cpp.doc.parsed.brief, "Build one widget.")
        self.assertEqual(
            function.cpp.doc.parsed.description,
            "Use the widget API (demo::Widget) for advanced flows.",
        )
        self.assertEqual(
            function.cpp.doc.parsed.parameters["value"],
            "Input value used by the factory and reused by the fallback path.",
        )
        self.assertEqual(function.cpp.doc.parsed.returns, "One widget.")
        self.assertEqual(
            function.parameters[0].cpp.doc,
            "Input value used by the factory and reused by the fallback path.",
        )

    def test_parse_headers_split_multiline_brief_from_plain_description(self) -> None:
        source = """
namespace demo {

/**
 * @brief Build one widget from the current
 * state and cached factory configuration.
 *
 * Use this overload for the common path.
 * It keeps the default ownership rules.
 */
Widget make_widget();

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        function = result.module.declarations.namespaces[0].declarations.functions[0]

        self.assertIsNotNone(function.cpp.doc)
        self.assertEqual(
            function.cpp.doc.parsed.brief,
            "Build one widget from the current state and cached factory configuration.",
        )
        self.assertEqual(
            function.cpp.doc.parsed.description,
            "Use this overload for the common path. It keeps the default ownership rules.",
        )

    def test_parse_headers_collect_warning_and_see_alias_docs(self) -> None:
        source = r"""
namespace demo {

/**
 * @brief Build one widget.
 * @warning Avoid reused state.
 * @sa demo::make_other_widget
 * @see demo::Widget
 */
Widget make_widget();

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        function = result.module.declarations.namespaces[0].declarations.functions[0]

        self.assertIsNotNone(function.cpp.doc)
        self.assertEqual(function.cpp.doc.parsed.brief, "Build one widget.")
        self.assertEqual(function.cpp.doc.parsed.warnings, ["Avoid reused state."])
        self.assertEqual(
            function.cpp.doc.parsed.see_also,
            ["demo::make_other_widget", "demo::Widget"],
        )

    def test_parse_headers_extract_template_return_value_and_deprecated_docs(self) -> None:
        source = """
namespace demo {

/**
 * @brief Build one widget.
 * @tparam Factory Factory type used to create the widget.
 * @retval true A widget was created successfully.
 * @retval false No widget could be created.
 * @deprecated Prefer build_widget_v2().
 */
template <class Factory>
bool build_widget();

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        function_template = result.module.declarations.namespaces[0].declarations.function_templates[0]
        function = function_template.declaration

        self.assertIsNotNone(function.cpp.doc)
        self.assertEqual(function.cpp.doc.parsed.brief, "Build one widget.")
        self.assertEqual(
            function.cpp.doc.parsed.template_parameters["Factory"],
            "Factory type used to create the widget.",
        )
        self.assertEqual(
            function.cpp.doc.parsed.return_values,
            {
                "true": "A widget was created successfully.",
                "false": "No widget could be created.",
            },
        )
        self.assertEqual(function.cpp.doc.parsed.deprecated, "Prefer build_widget_v2().")

    def test_parse_headers_attach_trailing_comments_to_member_variables_and_enumerators(self) -> None:
        source = """
namespace demo {

struct Widget {
    int size;   ///< Current size in elements.
    int count;  /**< Total number of stored entries. */
};

enum class Mode {
    fast = 1,   ///< Fast mode.
    slow = 2,   /**< Slow mode. */
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        mode = namespace.declarations.enums[0]

        self.assertIsNotNone(widget.declarations.variables[0].cpp.doc.attached_comment)
        self.assertEqual(widget.declarations.variables[0].cpp.doc.parsed.brief, "Current size in elements.")
        self.assertIsNotNone(widget.declarations.variables[1].cpp.doc.attached_comment)
        self.assertEqual(
            widget.declarations.variables[1].cpp.doc.parsed.brief,
            "Total number of stored entries.",
        )
        self.assertIsNotNone(mode.enumerators[0].cpp.doc.attached_comment)
        self.assertEqual(mode.enumerators[0].cpp.doc.parsed.brief, "Fast mode.")
        self.assertIsNotNone(mode.enumerators[1].cpp.doc.attached_comment)
        self.assertEqual(mode.enumerators[1].cpp.doc.parsed.brief, "Slow mode.")

    def test_parse_headers_attach_comments_to_enum_declarations_and_nested_class_scope(self) -> None:
        source = """
namespace demo {

/// Top-level mode docs.
enum class Mode {
    fast = 1,
};

/**
 * Widget docs.
 */
struct Widget {
    /// Nested helper docs.
    struct Helper {};

    /// Current size in elements.
    int size;

    /// Execute the widget operation.
    int run() const;

    /// Nested state docs.
    enum class State {
        idle = 0,   ///< Idle state.
    };
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        mode = namespace.declarations.enums[0]
        widget = namespace.declarations.classes[0]
        helper = widget.declarations.classes[0]
        method = widget.declarations.methods[0]
        nested_state = widget.declarations.enums[0]

        self.assertEqual(mode.cpp.doc.parsed.brief, "Top-level mode docs.")
        self.assertEqual(widget.cpp.doc.parsed.brief, "Widget docs.")
        self.assertEqual(helper.cpp.doc.parsed.brief, "Nested helper docs.")
        self.assertEqual(widget.declarations.variables[0].cpp.doc.parsed.brief, "Current size in elements.")
        self.assertEqual(method.cpp.doc.parsed.brief, "Execute the widget operation.")
        self.assertEqual(nested_state.cpp.doc.parsed.brief, "Nested state docs.")
        self.assertEqual(nested_state.enumerators[0].cpp.doc.parsed.brief, "Idle state.")

    def test_parse_headers_do_not_attach_closing_namespace_comments_as_namespace_docs(self) -> None:
        source = """
// ================================================================================================
//   demo::detail
// ================================================================================================
namespace demo::detail {

/// Widget docs.
struct Widget {};

}  // namespace demo::detail
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0].declarations.namespaces[0]
        widget = namespace.declarations.classes[0]

        self.assertIsNotNone(namespace.cpp.doc.attached_comment)
        self.assertNotIn("namespace demo::detail", namespace.cpp.doc.attached_comment)
        self.assertIn("demo::detail", namespace.cpp.doc.attached_comment)
        self.assertEqual(widget.cpp.doc.parsed.brief, "Widget docs.")
        self.assertFalse(any("Recovered attached comment" in warning.message for warning in result.report.warnings))

    def test_parse_headers_attach_plain_trailing_comments_and_indented_code_blocks(self) -> None:
        source = """
namespace demo {

struct Widget {
    int size;   // Current size in elements.
};

/**
 * Build one widget.
 *
 * Example usage:
 *
 *     Widget widget;
 *     widget.build();
 */
Widget make_widget();

enum class Mode {
    fast = 1,   // Fast mode.
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        function = namespace.declarations.functions[0]
        mode = namespace.declarations.enums[0]

        self.assertIsNotNone(widget.declarations.variables[0].cpp.doc.attached_comment)
        self.assertEqual(widget.declarations.variables[0].cpp.doc.parsed.brief, "Current size in elements.")
        self.assertIsNotNone(function.cpp.doc)
        self.assertEqual(
            function.cpp.doc.parsed.description,
            "Example usage:\n\n```\nWidget widget;\nwidget.build();\n```",
        )
        self.assertIsNotNone(mode.enumerators[0].cpp.doc.attached_comment)
        self.assertEqual(mode.enumerators[0].cpp.doc.parsed.brief, "Fast mode.")

    def test_parse_headers_do_not_warn_for_indentation_only_recovery_difference(self) -> None:
        source = """
namespace demo {

// We use the slots as indicators which elements in the slots of a block have been set already.
    // Using 64 slots fixed for now, for efficiency. Might parameterize as template param,
    // so that the buffer can be made smaller if needed for large elements instead.
struct BlockSlotBits {};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        block_slot_bits = result.module.declarations.namespaces[0].declarations.classes[0]

        self.assertIsNotNone(block_slot_bits.cpp.doc.attached_comment)
        self.assertIsNotNone(block_slot_bits.cpp.doc)
        self.assertEqual(
            block_slot_bits.cpp.doc.parsed.brief,
            "We use the slots as indicators which elements in the slots of a block have been set already. Using 64 slots fixed for now, for efficiency. Might parameterize as template param, so that the buffer can be made smaller if needed for large elements instead.",
        )
        self.assertFalse(any(warning.code == "parse.comment_recovery.mismatch" for warning in result.report.warnings))

    def test_parse_headers_keep_blank_lines_inside_indented_code_blocks(self) -> None:
        source = """
namespace demo {

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
Widget make_widget();

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        function = result.module.declarations.namespaces[0].declarations.functions[0]

        self.assertIsNotNone(function.cpp.doc)
        self.assertEqual(
            function.cpp.doc.parsed.description,
            "Example usage:\n\n```\nWidget widget;\n\nwidget.build();\n```\n\nContinue with normal prose afterwards.",
        )

    def test_parse_headers_do_not_attach_comments_separated_by_blank_lines(self) -> None:
        source = """
namespace demo {

// Some unrelated note.

class Widget {};

// Another unrelated note.

int make_widget();

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]
        function = namespace.declarations.functions[0]

        self.assertTrue(widget.cpp.doc is None or widget.cpp.doc.attached_comment is None)
        self.assertTrue(widget.cpp.doc is None or widget.cpp.doc.parsed is None)
        self.assertTrue(function.cpp.doc is None or function.cpp.doc.attached_comment is None)
        self.assertTrue(function.cpp.doc is None or function.cpp.doc.parsed is None)
        self.assertFalse(any("Recovered attached comment" in warning.message for warning in result.report.warnings))

    def test_parse_headers_suppress_detached_namespace_banner_warnings(self) -> None:
        source = """
// ================================================================================================
//   demo
// ================================================================================================

namespace demo {

struct Widget {};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]

        self.assertTrue(namespace.cpp.doc is None or namespace.cpp.doc.attached_comment is None)
        self.assertTrue(namespace.cpp.doc is None or namespace.cpp.doc.parsed is None)
        self.assertEqual(widget.name, "Widget")
        self.assertFalse(any("Recovered attached comment" in warning.message for warning in result.report.warnings))

    def test_parse_headers_do_not_attach_detached_header_comment_to_namespace_after_includes(self) -> None:
        source = """
/**
 * @brief Header notes that do not document the namespace below.
 */

#include <cstddef>

namespace demo {

struct Widget {};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        namespace = result.module.declarations.namespaces[0]
        widget = namespace.declarations.classes[0]

        self.assertTrue(namespace.cpp.doc is None or namespace.cpp.doc.attached_comment is None)
        self.assertTrue(namespace.cpp.doc is None or namespace.cpp.doc.parsed is None)
        self.assertEqual(widget.name, "Widget")
        self.assertFalse(any(warning.code == "parse.merge.conflicting_comments" for warning in result.report.warnings))

    def test_parse_headers_discard_stale_nonlocal_namespace_raw_comment_reused_across_headers(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
/**
 * @namespace demo
 *
 * @brief Container namespace for all demo symbols.
 */
namespace demo {

struct First {};

}
""",
                "b.hpp": """
/**
 * @brief Header notes that do not document the namespace below.
 */

namespace demo {

struct Second {};

}
""",
                "c.hpp": """
namespace demo {

struct Third {};

}
""",
            },
            header_order=["a.hpp", "b.hpp", "c.hpp"],
        )

        namespace = result.module.declarations.namespaces[0]

        self.assertEqual(namespace.cpp.doc.parsed.brief, "Container namespace for all demo symbols.")
        self.assertEqual(
            [declaration.name for declaration in namespace.declarations.classes],
            ["First", "Second", "Third"],
        )
        self.assertFalse(any(warning.code == "parse.merge.conflicting_comments" for warning in result.report.warnings))

    def test_parse_headers_attach_comments_across_methods_constructors_templates_aliases_and_reopened_namespaces(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
/// Demo namespace docs.
namespace demo {

/// Widget handle alias.
using WidgetHandle = int;

/// Widget typedef alias.
typedef int WidgetId;

/**
 * Widget template docs.
 * @tparam T Stored value type.
 */
template <class T>
struct Box {
    /// Construct one box.
    Box();

    /// Measure the stored value.
    int measure() const;
};

}
""",
                "b.hpp": """
namespace demo {

template <class T>
Box<T>::Box() = default;

template <class T>
int Box<T>::measure() const {
    return 0;
}

}
""",
            },
            header_order=["a.hpp", "b.hpp"],
        )

        namespace = result.module.declarations.namespaces[0]
        widget_handle = namespace.declarations.aliases[0]
        widget_id = namespace.declarations.aliases[1]
        class_template = namespace.declarations.class_templates[0]
        constructor = class_template.declaration.declarations.constructors[0]
        method = class_template.declaration.declarations.methods[0]

        self.assertEqual(namespace.cpp.doc.parsed.brief, "Demo namespace docs.")
        self.assertEqual(widget_handle.cpp.doc.parsed.brief, "Widget handle alias.")
        self.assertEqual(widget_id.cpp.doc.parsed.brief, "Widget typedef alias.")
        self.assertEqual(class_template.declaration.cpp.doc.parsed.brief, "Widget template docs.")
        self.assertEqual(
            class_template.declaration.cpp.doc.parsed.template_parameters["T"],
            "Stored value type.",
        )
        self.assertEqual(constructor.cpp.doc.parsed.brief, "Construct one box.")
        self.assertEqual(method.cpp.doc.parsed.brief, "Measure the stored value.")

    def test_parse_headers_prefer_definition_comment_over_forward_declaration_comment(self) -> None:
        source = """
namespace demo {

// Forward declaration of a type we need.
class ABC;

/**
 * @brief The class does cool things.
 */
class ABC {
public:
    int value {};
};

}
"""

        result = _parse_headers_from_sources({"demo.hpp": source})

        abc = result.module.declarations.namespaces[0].declarations.classes[0]

        self.assertEqual(
            abc.cpp.doc.attached_comment,
            "/**\n * @brief The class does cool things.\n */",
        )
        self.assertEqual(abc.cpp.doc.parsed.brief, "The class does cool things.")
        mismatch_warnings = [
            warning
            for warning in result.report.warnings
            if "Recovered attached comment" in warning.message
        ]
        self.assertFalse(mismatch_warnings, msg=f"Expected no recovery warning, got: {result.report.warnings}")
        merge_notes = [
            note
            for note in result.report.notes
            if note.code == "parse.merge.preferred_comments"
        ]
        self.assertTrue(merge_notes, msg=f"Expected merge note, got: {result.report.diagnostics}")
        self.assertIsNotNone(merge_notes[0].detail)
        self.assertEqual(len(merge_notes[0].locations), 2)
        self.assertEqual(
            sorted(location.line for location in merge_notes[0].locations),
            [5, 10],
        )
        self.assertIn("existing parsed comment:", merge_notes[0].detail)
        self.assertIn("// Forward declaration of a type we need.", merge_notes[0].detail)
        self.assertIn("new parsed comment:", merge_notes[0].detail)
        self.assertIn("@brief The class does cool things.", merge_notes[0].detail)
        self.assertIn("selected: new", merge_notes[0].detail)

    def test_parse_headers_prefer_structured_definition_docs_for_redeclared_classes_across_headers(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
namespace demo {

/**
 * @brief Forward declaration docs.
 */
class Widget;

}
""",
                "b.hpp": """
namespace demo {

/**
 * @brief Widget docs from the richer definition path.
 */
class Widget {
public:
    int value {};
};

}
""",
            },
            header_order=["a.hpp", "b.hpp"],
        )

        widget = result.module.declarations.namespaces[0].declarations.classes[0]

        self.assertEqual(len(widget.cpp.location.declarations), 2)
        self.assertEqual(
            widget.cpp.doc.attached_comment,
            "/**\n * @brief Widget docs from the richer definition path.\n */",
        )
        self.assertEqual(widget.cpp.doc.parsed.brief, "Widget docs from the richer definition path.")
        self.assertEqual(len(widget.declarations.variables), 1)
        self.assertEqual(widget.declarations.variables[0].name, "value")

    def test_parse_headers_prefer_recovered_forward_comment_on_later_redeclarations(self) -> None:
        sources = {
            "a.hpp": """
namespace demo {

/// First forward docs.
struct Widget;

}
""",
            "b.hpp": """
namespace demo {

/// Second forward docs are longer.
struct Widget;

}
""",
        }

        result = _parse_headers_from_sources(
            sources,
            header_order=["a.hpp", "b.hpp"],
        )

        widget = result.module.declarations.namespaces[0].declarations.classes[0]

        self.assertEqual(len(widget.cpp.location.declarations), 2)
        self.assertEqual(widget.cpp.doc.attached_comment, "/// Second forward docs are longer.")
        self.assertEqual(widget.cpp.doc.parsed.brief, "Second forward docs are longer.")

    def test_parse_headers_preserve_attached_structured_docs_across_redeclarations(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
namespace demo {

/**
 * Forward declaration docs.
 * @param value Value from the forward declaration.
 */
int make_widget(int value);

}
""",
                "b.hpp": """
namespace demo {

/**
 * Build one widget from the current state and the richer rebuilt definition docs.
 * @param value Value from the definition.
 * @return One widget.
 */
int make_widget(int value);

}
""",
            },
            header_order=["a.hpp", "b.hpp"],
        )

        function = result.module.declarations.namespaces[0].declarations.functions[0]

        self.assertEqual(
            function.cpp.doc.parsed.brief,
            "Build one widget from the current state and the richer rebuilt definition docs.",
        )
        self.assertEqual(function.cpp.doc.parsed.parameters["value"], "Value from the definition.")
        self.assertEqual(function.cpp.doc.parsed.returns, "One widget.")
        self.assertEqual(function.parameters[0].cpp.doc, "Value from the definition.")

    def test_parse_headers_merges_template_provenance_and_comments_across_headers(self) -> None:
        result = _parse_headers_from_sources(
            {
                "a.hpp": """
namespace demo {

/// Forward declaration docs.
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

}
""",
            },
            header_order=["a.hpp", "b.hpp"],
        )

        namespace = result.module.declarations.namespaces[0]
        class_template = namespace.declarations.class_templates[0]

        self.assertEqual(class_template.name, "Box")
        self.assertEqual(len(class_template.declaration.cpp.location.declarations), 2)
        self.assertIsNotNone(class_template.declaration.cpp.doc.attached_comment)
        self.assertIn("Forward declaration docs.", class_template.declaration.cpp.doc.attached_comment)
        self.assertEqual(len(class_template.declaration.declarations.variables), 1)
        self.assertEqual(class_template.declaration.declarations.variables[0].name, "value")


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
            header.write_text(dedent(sources[name]))
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


if __name__ == "__main__":
    unittest.main()
