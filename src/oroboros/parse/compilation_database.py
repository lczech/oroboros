from __future__ import annotations

"""Infer parser settings from one clang compilation database."""

from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence

from ..diagnostics import Diagnostic, DiagnosticReport
from .config import ParserConfig

CompilationDatabaseScope = Literal["all_commands", "source_roots"]
CompilationDatabaseConflictPolicy = Literal["warn", "strict"]

_COMPILER_WRAPPER_NAMES = frozenset({"ccache", "sccache"})
_SCALAR_EXTRA_FLAG_LABELS = {
    "target": "-target",
    "sysroot": "--sysroot",
    "isysroot": "-isysroot",
    "stdlib": "-stdlib",
    "nostdinc": "-nostdinc",
    "nostdinc++": "-nostdinc++",
    "nostdlibinc": "-nostdlibinc",
}


@dataclass(slots=True)
class ParserConfigInferenceResult:
    """Store one inferred parser config plus structured inference diagnostics."""

    config: ParserConfig = field(default_factory=ParserConfig)
    report: DiagnosticReport = field(default_factory=DiagnosticReport)


@dataclass(slots=True)
class _ParsedCompileCommand:
    """Store the semantic parser-relevant flags from one compile command."""

    filename: Path
    directory: Path
    compiler: str | None = None
    language: str | None = None
    cxx_standard: str | None = None
    resource_dir: Path | None = None
    include_dirs: list[Path] = field(default_factory=list)
    defines: list[str] = field(default_factory=list)
    undefines: list[str] = field(default_factory=list)
    repeatable_extra_args: list[tuple[str, str]] = field(default_factory=list)
    scalar_extra_args: dict[str, str | bool] = field(default_factory=dict)


def infer_parser_config_from_compilation_database(
    compilation_database_path: str | Path,
    *,
    scope: CompilationDatabaseScope = "source_roots",
    source_roots: Sequence[str | Path] | None = None,
    conflict_policy: CompilationDatabaseConflictPolicy = "warn",
) -> ParserConfigInferenceResult:
    """Infer one parser config from one clang compilation database."""

    report = DiagnosticReport()
    database_directory = _resolve_compilation_database_directory(
        compilation_database_path,
        report,
    )
    if database_directory is None:
        return ParserConfigInferenceResult(report=report)

    compilation_database = _load_compilation_database(
        database_directory,
        report,
    )
    if compilation_database is None:
        return ParserConfigInferenceResult(report=report)

    selected_commands = _select_compile_commands(
        compilation_database,
        database_directory=database_directory,
        scope=scope,
        source_roots=source_roots,
        report=report,
    )
    if not selected_commands:
        return ParserConfigInferenceResult(report=report)

    parsed_commands = [_parse_compile_command(command) for command in selected_commands]
    inferred_config = _merge_parsed_compile_commands(
        parsed_commands,
        conflict_policy=conflict_policy,
        report=report,
    )
    return ParserConfigInferenceResult(
        config=inferred_config,
        report=report,
    )


def _resolve_compilation_database_directory(
    compilation_database_path: str | Path,
    report: DiagnosticReport,
) -> Path | None:
    """Resolve one file-or-directory input into the database directory."""

    requested_path = Path(compilation_database_path).expanduser()
    resolved_path = requested_path.resolve()

    if not resolved_path.exists():
        report.add(
            Diagnostic(
                severity="error",
                stage="config",
                code="config.compdb.not_found",
                message=(
                    "Compilation database path was not found. Expected one "
                    "`compile_commands.json` file or a directory containing it."
                ),
                locations=[],
                detail=f"requested path: {requested_path}",
            )
        )
        return None

    if resolved_path.is_file():
        if resolved_path.name != "compile_commands.json":
            report.add(
                Diagnostic(
                    severity="error",
                    stage="config",
                    code="config.compdb.invalid_file",
                    message=(
                        "Compilation database file input must be named "
                        "`compile_commands.json`."
                    ),
                    detail=f"received file: {resolved_path}",
                )
            )
            return None
        return resolved_path.parent

    database_file = resolved_path / "compile_commands.json"
    if not database_file.is_file():
        report.add(
            Diagnostic(
                severity="error",
                stage="config",
                code="config.compdb.not_found",
                message=(
                    "Compilation database directory did not contain one "
                    "`compile_commands.json` file."
                ),
                detail=f"searched directory: {resolved_path}",
            )
        )
        return None

    return resolved_path


def _load_compilation_database(
    database_directory: Path,
    report: DiagnosticReport,
) -> Any | None:
    """Load one clang compilation database from disk."""

    try:
        from clang import cindex
    except ImportError as error:
        report.add(
            Diagnostic(
                severity="error",
                stage="config",
                code="config.compdb.clang_unavailable",
                message=(
                    "libclang Python bindings are not available, so the "
                    "compilation database could not be loaded."
                ),
                detail=str(error),
            )
        )
        return None

    try:
        return cindex.CompilationDatabase.fromDirectory(str(database_directory))
    except cindex.CompilationDatabaseError as error:
        report.add(
            Diagnostic(
                severity="error",
                stage="config",
                code="config.compdb.load_failed",
                message="Failed to load the clang compilation database.",
                detail=(
                    f"database directory: {database_directory}\n"
                    f"libclang error: {error}"
                ),
            )
        )
        return None


def _select_compile_commands(
    compilation_database: Any,
    *,
    database_directory: Path,
    scope: CompilationDatabaseScope,
    source_roots: Sequence[str | Path] | None,
    report: DiagnosticReport,
) -> list[Any]:
    """Select the compile commands that should feed config inference."""

    all_compile_commands = compilation_database.getAllCompileCommands()
    if all_compile_commands is None:
        report.add(
            Diagnostic(
                severity="warning",
                stage="config",
                code="config.compdb.no_commands",
                message=(
                    "The compilation database did not contain any compile "
                    "commands, so no parser config could be inferred."
                ),
            )
        )
        return []

    commands = sorted(
        list(all_compile_commands),
        key=lambda command: (
            str(_resolve_command_path(command.directory, command.filename)),
            str(Path(command.directory).resolve()),
        ),
    )

    if scope == "all_commands":
        return commands

    normalized_source_roots = _normalize_source_roots(
        source_roots,
        database_directory=database_directory,
        report=report,
    )
    selected_commands = [
        command
        for command in commands
        if _command_matches_any_source_root(command, normalized_source_roots)
    ]

    if selected_commands:
        return selected_commands

    report.add(
        Diagnostic(
            severity="warning",
            stage="config",
            code="config.compdb.no_matching_commands",
            message=(
                "No compile commands matched the requested source-root scope, "
                "so no parser config could be inferred."
            ),
            detail=(
                "source roots:\n"
                + "\n".join(f"  {root}" for root in normalized_source_roots)
            ),
        )
    )
    return []


def _normalize_source_roots(
    source_roots: Sequence[str | Path] | None,
    *,
    database_directory: Path,
    report: DiagnosticReport,
) -> list[Path]:
    """Normalize the selected source roots, inferring a default when needed."""

    if source_roots:
        return [Path(root).expanduser().resolve() for root in source_roots]

    inferred_root = database_directory.parent.resolve()
    report.add(
        Diagnostic(
            severity="note",
            stage="config",
            code="config.compdb.default_source_roots",
            message=(
                "No source roots were provided; defaulting to the parent of "
                "the compilation database directory."
            ),
            detail=f"inferred source root: {inferred_root}",
        )
    )
    return [inferred_root]


def _command_matches_any_source_root(command: Any, source_roots: Sequence[Path]) -> bool:
    """Return whether one compile command's source file belongs to one source root."""

    filename = _resolve_command_path(command.directory, command.filename)
    return any(_path_is_within_root(filename, root) for root in source_roots)


def _path_is_within_root(path: Path, root: Path) -> bool:
    """Return whether one path is located inside one candidate root."""

    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _parse_compile_command(command: Any) -> _ParsedCompileCommand:
    """Parse one compile command into parser-relevant semantic flags."""

    working_directory = Path(command.directory).expanduser().resolve()
    source_file = _resolve_command_path(command.directory, command.filename)
    arguments = list(command.arguments)

    parsed = _ParsedCompileCommand(
        filename=source_file,
        directory=working_directory,
        compiler=_normalize_compiler_argument(arguments),
    )

    index = 1
    while index < len(arguments):
        argument = arguments[index]

        if argument in {"-c", "-o", "-MF", "-MT", "-MQ"}:
            index += 2
            continue

        if argument in {"-I", "-D", "-U", "-x", "-std", "-resource-dir"}:
            index = _consume_simple_option(parsed, arguments, index, argument)
            continue

        if argument in {
            "-isystem",
            "-target",
            "--target",
            "--sysroot",
            "-isysroot",
            "-include",
            "-imacros",
            "-iquote",
            "-idirafter",
            "-iframework",
            "-F",
            "-stdlib",
        }:
            index = _consume_extra_option(parsed, arguments, index, argument)
            continue

        if argument in {"-nostdinc", "-nostdinc++", "-nostdlibinc"}:
            parsed.scalar_extra_args[_scalar_extra_arg_key(argument)] = True
            index += 1
            continue

        if argument.startswith("-I") and argument != "-I":
            parsed.include_dirs.append(_resolve_argument_path(working_directory, argument[2:]))
            index += 1
            continue

        if argument.startswith("-D") and argument != "-D":
            parsed.defines.append(argument[2:])
            index += 1
            continue

        if argument.startswith("-U") and argument != "-U":
            parsed.undefines.append(argument[2:])
            index += 1
            continue

        if argument.startswith("-x") and argument != "-x":
            parsed.language = argument[2:]
            index += 1
            continue

        if argument.startswith("-std="):
            parsed.cxx_standard = argument.partition("=")[2]
            index += 1
            continue

        if argument.startswith("-resource-dir="):
            parsed.resource_dir = _resolve_argument_path(
                working_directory,
                argument.partition("=")[2],
            )
            index += 1
            continue

        if argument.startswith("--target="):
            parsed.scalar_extra_args["target"] = argument.partition("=")[2]
            index += 1
            continue

        if argument.startswith("--sysroot="):
            parsed.scalar_extra_args["sysroot"] = str(
                _resolve_argument_path(working_directory, argument.partition("=")[2])
            )
            index += 1
            continue

        if argument.startswith("-stdlib="):
            parsed.scalar_extra_args["stdlib"] = argument.partition("=")[2]
            index += 1
            continue

        if argument == str(source_file) or argument == command.filename:
            index += 1
            continue

        index += 1

    return parsed


def _consume_simple_option(
    parsed: _ParsedCompileCommand,
    arguments: list[str],
    index: int,
    option: str,
) -> int:
    """Consume one option with one following payload and update one parsed command."""

    if index + 1 >= len(arguments):
        return index + 1

    value = arguments[index + 1]
    if option == "-I":
        parsed.include_dirs.append(_resolve_argument_path(parsed.directory, value))
    elif option == "-D":
        parsed.defines.append(value)
    elif option == "-U":
        parsed.undefines.append(value)
    elif option == "-x":
        parsed.language = value
    elif option == "-std":
        parsed.cxx_standard = value
    elif option == "-resource-dir":
        parsed.resource_dir = _resolve_argument_path(parsed.directory, value)
    return index + 2


def _consume_extra_option(
    parsed: _ParsedCompileCommand,
    arguments: list[str],
    index: int,
    option: str,
) -> int:
    """Consume one semantically relevant extra clang option."""

    if index + 1 >= len(arguments):
        return index + 1

    raw_value = arguments[index + 1]
    if option in {"-target", "--target"}:
        parsed.scalar_extra_args["target"] = raw_value
        return index + 2

    if option == "--sysroot":
        parsed.scalar_extra_args["sysroot"] = str(
            _resolve_argument_path(parsed.directory, raw_value)
        )
        return index + 2

    if option == "-isysroot":
        parsed.scalar_extra_args["isysroot"] = str(
            _resolve_argument_path(parsed.directory, raw_value)
        )
        return index + 2

    if option == "-stdlib":
        parsed.scalar_extra_args["stdlib"] = raw_value
        return index + 2

    value = str(_resolve_argument_path(parsed.directory, raw_value))
    parsed.repeatable_extra_args.append((option, value))
    return index + 2


def _merge_parsed_compile_commands(
    parsed_commands: Sequence[_ParsedCompileCommand],
    *,
    conflict_policy: CompilationDatabaseConflictPolicy,
    report: DiagnosticReport,
) -> ParserConfig:
    """Merge one selected command set into one best-effort parser config."""

    anchor_command = parsed_commands[0]
    include_dirs = _merge_paths(command.include_dirs for command in parsed_commands)
    defines, undefines = _merge_macros(
        parsed_commands,
        conflict_policy=conflict_policy,
        report=report,
    )

    inferred_language = _merge_scalar_field(
        parsed_commands,
        field_name="language",
        diagnostic_label="language mode",
        conflict_policy=conflict_policy,
        report=report,
        anchor_command=anchor_command,
    )
    inferred_standard = _merge_scalar_field(
        parsed_commands,
        field_name="cxx_standard",
        diagnostic_label="C++ standard",
        conflict_policy=conflict_policy,
        report=report,
        anchor_command=anchor_command,
    )
    inferred_resource_dir = _merge_scalar_field(
        parsed_commands,
        field_name="resource_dir",
        diagnostic_label="clang resource directory",
        conflict_policy=conflict_policy,
        report=report,
        anchor_command=anchor_command,
    )
    inferred_compiler = _merge_scalar_field(
        parsed_commands,
        field_name="compiler",
        diagnostic_label="toolchain compiler",
        conflict_policy=conflict_policy,
        report=report,
        anchor_command=anchor_command,
    )

    repeatable_extra_args = _merge_repeatable_extra_args(parsed_commands)
    scalar_extra_args = _merge_scalar_extra_args(
        parsed_commands,
        conflict_policy=conflict_policy,
        report=report,
        anchor_command=anchor_command,
    )

    merged_config = ParserConfig()
    merged_config.include_dirs = include_dirs
    merged_config.defines = defines
    merged_config.undefines = undefines
    if inferred_language is not None:
        merged_config.language = inferred_language
    if inferred_standard is not None:
        merged_config.cxx_standard = inferred_standard
    if inferred_resource_dir is not None:
        merged_config.resource_dir = inferred_resource_dir
    if inferred_compiler is not None:
        merged_config.toolchain_compiler = inferred_compiler
    merged_config.extra_args = _render_extra_args(
        repeatable_extra_args,
        scalar_extra_args,
    )
    return merged_config


def _merge_paths(path_groups: Iterable[Sequence[Path]]) -> list[Path]:
    """Merge one ordered path collection while preserving first-seen order."""

    merged_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for path_group in path_groups:
        for path in path_group:
            resolved_path = Path(path).expanduser().resolve()
            if resolved_path in seen_paths:
                continue
            seen_paths.add(resolved_path)
            merged_paths.append(resolved_path)
    return merged_paths


def _merge_macros(
    parsed_commands: Sequence[_ParsedCompileCommand],
    *,
    conflict_policy: CompilationDatabaseConflictPolicy,
    report: DiagnosticReport,
) -> tuple[list[str], list[str]]:
    """Merge `-D` and `-U` flags, dropping conflicting macro names."""

    define_occurrences: OrderedDict[str, OrderedDict[str, list[Path]]] = OrderedDict()
    undefine_occurrences: OrderedDict[str, list[Path]] = OrderedDict()

    for command in parsed_commands:
        for define in command.defines:
            macro_name = _macro_name(define)
            define_occurrences.setdefault(macro_name, OrderedDict()).setdefault(define, []).append(
                command.filename
            )
        for undefine in command.undefines:
            undefine_occurrences.setdefault(undefine, []).append(command.filename)

    conflicting_names = {
        macro_name
        for macro_name, definitions in define_occurrences.items()
        if len(definitions) > 1 or macro_name in undefine_occurrences
    } | {
        macro_name
        for macro_name in undefine_occurrences
        if macro_name in define_occurrences
    }

    for macro_name in sorted(conflicting_names):
        definition_variants = define_occurrences.get(macro_name, OrderedDict())
        undefined_from = undefine_occurrences.get(macro_name, [])
        _record_conflict_diagnostic(
            conflict_policy=conflict_policy,
            report=report,
            code="config.compdb.macro_conflict",
            message=(
                "Conflicting macro settings were found while inferring one "
                f"global parser config for `{macro_name}`. Dropping that macro."
            ),
            detail=_format_macro_conflict_detail(
                macro_name,
                definition_variants=definition_variants,
                undefined_from=undefined_from,
            ),
        )

    merged_defines: list[str] = []
    seen_define_names: set[str] = set()
    for command in parsed_commands:
        for define in command.defines:
            macro_name = _macro_name(define)
            if macro_name in conflicting_names or macro_name in seen_define_names:
                continue
            seen_define_names.add(macro_name)
            merged_defines.append(define)

    merged_undefines: list[str] = []
    seen_undefine_names: set[str] = set()
    for command in parsed_commands:
        for undefine in command.undefines:
            if undefine in conflicting_names or undefine in seen_undefine_names:
                continue
            seen_undefine_names.add(undefine)
            merged_undefines.append(undefine)

    return merged_defines, merged_undefines


def _merge_scalar_field(
    parsed_commands: Sequence[_ParsedCompileCommand],
    *,
    field_name: str,
    diagnostic_label: str,
    conflict_policy: CompilationDatabaseConflictPolicy,
    report: DiagnosticReport,
    anchor_command: _ParsedCompileCommand,
) -> Any | None:
    """Merge one scalar parsed-command field with conflict reporting."""

    observed_values = [getattr(command, field_name) for command in parsed_commands]
    concrete_values = [value for value in observed_values if value is not None]
    if not concrete_values:
        return None

    unique_concrete_values = list(OrderedDict.fromkeys(concrete_values))
    missing_count = sum(value is None for value in observed_values)
    if len(unique_concrete_values) == 1 and missing_count == 0:
        return unique_concrete_values[0]

    chosen_value = getattr(anchor_command, field_name)
    if chosen_value is None:
        chosen_value = unique_concrete_values[0]

    _record_conflict_diagnostic(
        conflict_policy=conflict_policy,
        report=report,
        code="config.compdb.scalar_conflict",
        message=(
            f"Conflicting compile-command values were found for inferred "
            f"{diagnostic_label}."
            + (
                f" Using anchor value `{chosen_value}`."
                if conflict_policy == "warn"
                else " Leaving that parser setting unset."
            )
        ),
        detail=_format_scalar_conflict_detail(
            parsed_commands,
            field_name=field_name,
            diagnostic_label=diagnostic_label,
            chosen_value=chosen_value if conflict_policy == "warn" else None,
        ),
    )

    if conflict_policy == "strict":
        return None
    return chosen_value


def _merge_scalar_extra_args(
    parsed_commands: Sequence[_ParsedCompileCommand],
    *,
    conflict_policy: CompilationDatabaseConflictPolicy,
    report: DiagnosticReport,
    anchor_command: _ParsedCompileCommand,
) -> dict[str, str | bool]:
    """Merge scalar extra args such as `-target` and `-nostdinc`."""

    merged_values: dict[str, str | bool] = {}
    all_keys = OrderedDict.fromkeys(
        key
        for command in parsed_commands
        for key in command.scalar_extra_args
    )

    for key in all_keys:
        observed_values = [
            command.scalar_extra_args.get(key, False if key.startswith("nostd") else None)
            for command in parsed_commands
        ]
        unique_values = list(OrderedDict.fromkeys(observed_values))

        if key.startswith("nostd"):
            if unique_values == [False]:
                continue
            if unique_values == [True]:
                merged_values[key] = True
                continue
        else:
            concrete_values = [value for value in observed_values if value is not None]
            if not concrete_values:
                continue
            unique_concrete_values = list(OrderedDict.fromkeys(concrete_values))
            missing_count = sum(value is None for value in observed_values)
            if len(unique_concrete_values) == 1 and missing_count == 0:
                merged_values[key] = unique_concrete_values[0]
                continue

        anchor_value = anchor_command.scalar_extra_args.get(
            key,
            False if key.startswith("nostd") else None,
        )
        chosen_value = anchor_value
        if chosen_value in {None, False} and not key.startswith("nostd"):
            chosen_value = next(
                value for value in observed_values if value is not None
            )

        _record_conflict_diagnostic(
            conflict_policy=conflict_policy,
            report=report,
            code="config.compdb.scalar_conflict",
            message=(
                f"Conflicting compile-command values were found for inferred "
                f"{_SCALAR_EXTRA_FLAG_LABELS.get(key, key)}."
                + (
                    f" Using anchor value `{chosen_value}`."
                    if conflict_policy == "warn"
                    else " Leaving that parser setting unset."
                )
            ),
            detail=_format_scalar_extra_conflict_detail(
                parsed_commands,
                key=key,
                chosen_value=chosen_value if conflict_policy == "warn" else None,
            ),
        )

        if conflict_policy == "warn" and chosen_value not in {None, False}:
            merged_values[key] = chosen_value
        if conflict_policy == "warn" and key.startswith("nostd") and chosen_value is True:
            merged_values[key] = True

    return merged_values


def _merge_repeatable_extra_args(
    parsed_commands: Sequence[_ParsedCompileCommand],
) -> list[tuple[str, str]]:
    """Merge repeatable extra args while preserving first-seen order."""

    merged_arguments: list[tuple[str, str]] = []
    seen_arguments: set[tuple[str, str]] = set()
    for command in parsed_commands:
        for argument in command.repeatable_extra_args:
            if argument in seen_arguments:
                continue
            seen_arguments.add(argument)
            merged_arguments.append(argument)
    return merged_arguments


def _render_extra_args(
    repeatable_extra_args: Sequence[tuple[str, str]],
    scalar_extra_args: dict[str, str | bool],
) -> list[str]:
    """Render the merged semantic extra args back into clang argv form."""

    rendered_arguments: list[str] = []
    rendered_arguments.extend(
        token
        for option, value in repeatable_extra_args
        for token in (option, value)
    )

    for key in ("target", "sysroot", "isysroot", "stdlib", "nostdinc", "nostdinc++", "nostdlibinc"):
        if key not in scalar_extra_args:
            continue
        value = scalar_extra_args[key]
        if key == "target":
            rendered_arguments.extend(["-target", str(value)])
        elif key == "sysroot":
            rendered_arguments.append(f"--sysroot={value}")
        elif key == "isysroot":
            rendered_arguments.extend(["-isysroot", str(value)])
        elif key == "stdlib":
            rendered_arguments.append(f"-stdlib={value}")
        elif value is True:
            rendered_arguments.append(_SCALAR_EXTRA_FLAG_LABELS[key])
    return rendered_arguments


def _record_conflict_diagnostic(
    *,
    conflict_policy: CompilationDatabaseConflictPolicy,
    report: DiagnosticReport,
    code: str,
    message: str,
    detail: str,
) -> None:
    """Record one warning-or-error diagnostic according to one conflict policy."""

    report.add(
        Diagnostic(
            severity="warning" if conflict_policy == "warn" else "error",
            stage="config",
            code=code,
            message=message,
            detail=detail,
        )
    )


def _format_scalar_conflict_detail(
    parsed_commands: Sequence[_ParsedCompileCommand],
    *,
    field_name: str,
    diagnostic_label: str,
    chosen_value: Any | None,
) -> str:
    """Render one scalar-field conflict summary with source-file provenance."""

    grouped_files: OrderedDict[str, list[Path]] = OrderedDict()
    for command in parsed_commands:
        value = getattr(command, field_name)
        key = "<unset>" if value is None else str(value)
        grouped_files.setdefault(key, []).append(command.filename)

    lines = [
        f"setting: {diagnostic_label}",
        f"selected compile commands: {len(parsed_commands)}",
    ]
    if chosen_value is not None:
        lines.append(f"chosen value: {chosen_value}")
    lines.append("observed values:")
    for value, files in grouped_files.items():
        lines.append(
            f"  {value}: {len(files)} command(s); "
            f"examples: {_format_example_files(files)}"
        )
    return "\n".join(lines)


def _format_scalar_extra_conflict_detail(
    parsed_commands: Sequence[_ParsedCompileCommand],
    *,
    key: str,
    chosen_value: str | bool | None,
) -> str:
    """Render one scalar extra-arg conflict summary."""

    grouped_files: OrderedDict[str, list[Path]] = OrderedDict()
    default_value = False if key.startswith("nostd") else None
    for command in parsed_commands:
        value = command.scalar_extra_args.get(key, default_value)
        rendered_value = "<unset>" if value is None else str(value)
        grouped_files.setdefault(rendered_value, []).append(command.filename)

    lines = [
        f"setting: {_SCALAR_EXTRA_FLAG_LABELS.get(key, key)}",
        f"selected compile commands: {len(parsed_commands)}",
    ]
    if chosen_value is not None:
        lines.append(f"chosen value: {chosen_value}")
    lines.append("observed values:")
    for value, files in grouped_files.items():
        lines.append(
            f"  {value}: {len(files)} command(s); "
            f"examples: {_format_example_files(files)}"
        )
    return "\n".join(lines)


def _format_macro_conflict_detail(
    macro_name: str,
    *,
    definition_variants: OrderedDict[str, list[Path]],
    undefined_from: Sequence[Path],
) -> str:
    """Render one macro-conflict detail payload."""

    lines = [f"macro: {macro_name}", "observed settings:"]
    for definition, files in definition_variants.items():
        lines.append(
            f"  -D{definition}: {len(files)} command(s); "
            f"examples: {_format_example_files(files)}"
        )
    if undefined_from:
        lines.append(
            f"  -U{macro_name}: {len(undefined_from)} command(s); "
            f"examples: {_format_example_files(undefined_from)}"
        )
    return "\n".join(lines)


def _format_example_files(files: Sequence[Path], *, limit: int = 3) -> str:
    """Render a short provenance file sample for one diagnostic detail."""

    if not files:
        return "<none>"
    return ", ".join(str(path) for path in files[:limit])


def _macro_name(define: str) -> str:
    """Extract one macro name from one raw `-D` payload."""

    return define.partition("=")[0]


def _resolve_command_path(command_directory: str | Path, path_text: str | Path) -> Path:
    """Resolve one compile-command path against that command's working directory."""

    directory = Path(command_directory).expanduser()
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (directory / path).resolve()


def _resolve_argument_path(command_directory: Path, argument_value: str) -> Path:
    """Resolve one path-valued compiler flag against the command's working directory."""

    value_path = Path(argument_value).expanduser()
    if value_path.is_absolute():
        return value_path.resolve()
    return (command_directory / value_path).resolve()


def _normalize_compiler_argument(arguments: Sequence[str]) -> str | None:
    """Normalize one compiler argv prefix to the actual compiler executable when possible."""

    if not arguments:
        return None

    compiler_argument = arguments[0]
    compiler_name = Path(compiler_argument).name
    if compiler_name not in _COMPILER_WRAPPER_NAMES:
        return compiler_argument
    if len(arguments) > 1:
        return arguments[1]
    return None


def _scalar_extra_arg_key(option: str) -> str:
    """Map one scalar extra-arg flag into its internal merge key."""

    return {
        "-nostdinc": "nostdinc",
        "-nostdinc++": "nostdinc++",
        "-nostdlibinc": "nostdlibinc",
    }[option]
