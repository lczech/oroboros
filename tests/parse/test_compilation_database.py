from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from oroboros.diagnostics import format_report
from oroboros.parse import infer_parser_config_from_compilation_database


class CompilationDatabaseInferenceTest(unittest.TestCase):
    def test_infers_parser_config_from_directory_and_uses_default_source_root_scope(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            build_dir = project_root / "build"
            build_dir.mkdir()

            selected_source = project_root / "src" / "alpha.cpp"
            excluded_source = project_root.parent / "external" / "beta.cpp"
            self._write_compilation_database(
                build_dir,
                entries=[
                    self._entry(
                        directory=project_root,
                        file=selected_source,
                        arguments=[
                            "/usr/bin/c++",
                            "-Iinclude",
                            "-DPROJECT=1",
                            "-UOLD_API",
                            "-std=c++20",
                            "-target",
                            "x86_64-unknown-linux-gnu",
                            "--sysroot",
                            "sdk",
                            "-include",
                            "prefix.hpp",
                            "-isystem",
                            "system",
                            "-c",
                            str(selected_source),
                        ],
                    ),
                    self._entry(
                        directory=excluded_source.parent,
                        file=excluded_source,
                        arguments=[
                            "/usr/bin/c++",
                            "-DEXTERNAL=1",
                            "-c",
                            str(excluded_source),
                        ],
                    ),
                ],
            )

            result = infer_parser_config_from_compilation_database(build_dir)

        self.assertEqual(
            result.config.include_dirs,
            [(project_root / "include").resolve()],
        )
        self.assertEqual(result.config.defines, ["PROJECT=1"])
        self.assertEqual(result.config.undefines, ["OLD_API"])
        self.assertEqual(result.config.cxx_standard, "c++20")
        self.assertEqual(result.config.toolchain_compiler, "/usr/bin/c++")
        self.assertEqual(
            result.config.extra_args,
            [
                "-include",
                str((project_root / "prefix.hpp").resolve()),
                "-isystem",
                str((project_root / "system").resolve()),
                "-target",
                "x86_64-unknown-linux-gnu",
                f"--sysroot={(project_root / 'sdk').resolve()}",
            ],
        )
        self.assertEqual(result.report.errors, [])
        self.assertEqual(result.report.warnings, [])
        self.assertEqual(
            [diagnostic.code for diagnostic in result.report.notes],
            ["config.compdb.default_source_roots"],
        )

    def test_infers_from_compile_commands_file_and_explicit_source_roots(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            build_dir = project_root / "build"
            build_dir.mkdir()

            library_source = project_root / "src" / "library.cpp"
            test_source = project_root / "tests" / "suite.cpp"
            compilation_database = self._write_compilation_database(
                build_dir,
                entries=[
                    self._entry(
                        directory=project_root,
                        file=library_source,
                        arguments=[
                            "/usr/bin/c++",
                            "-DLIBRARY=1",
                            "-c",
                            str(library_source),
                        ],
                    ),
                    self._entry(
                        directory=project_root,
                        file=test_source,
                        arguments=[
                            "/usr/bin/c++",
                            "-DTESTING=1",
                            "-c",
                            str(test_source),
                        ],
                    ),
                ],
            )

            result = infer_parser_config_from_compilation_database(
                compilation_database,
                source_roots=[project_root / "tests"],
            )

        self.assertEqual(result.config.defines, ["TESTING=1"])
        self.assertEqual(result.report.warnings, [])
        self.assertEqual(result.report.errors, [])
        self.assertEqual(result.report.notes, [])

    def test_warn_policy_keeps_anchor_scalar_and_drops_conflicting_macros(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            build_dir = project_root / "build"
            build_dir.mkdir()

            first_source = project_root / "src" / "alpha.cpp"
            second_source = project_root / "src" / "beta.cpp"
            self._write_compilation_database(
                build_dir,
                entries=[
                    self._entry(
                        directory=project_root,
                        file=first_source,
                        arguments=[
                            "/usr/bin/c++",
                            "-std=c++20",
                            "-DVERSION=1",
                            "-DKEEP=1",
                            "-c",
                            str(first_source),
                        ],
                    ),
                    self._entry(
                        directory=project_root,
                        file=second_source,
                        arguments=[
                            "/usr/bin/c++",
                            "-std=c++17",
                            "-DVERSION=2",
                            "-DKEEP=1",
                            "-c",
                            str(second_source),
                        ],
                    ),
                ],
            )

            result = infer_parser_config_from_compilation_database(
                build_dir,
                conflict_policy="warn",
            )

        self.assertEqual(result.config.cxx_standard, "c++20")
        self.assertEqual(result.config.defines, ["KEEP=1"])
        self.assertEqual(
            sorted(diagnostic.code for diagnostic in result.report.warnings),
            ["config.compdb.macro_conflict", "config.compdb.scalar_conflict"],
        )
        self.assertEqual(result.report.errors, [])

    def test_missing_scalar_values_do_not_conflict_when_one_concrete_value_exists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            build_dir = project_root / "build"
            build_dir.mkdir()

            first_source = project_root / "src" / "alpha.cpp"
            second_source = project_root / "src" / "beta.cpp"
            self._write_compilation_database(
                build_dir,
                entries=[
                    self._entry(
                        directory=project_root,
                        file=first_source,
                        arguments=[
                            "/usr/bin/c++",
                            "-std=c++20",
                            "-c",
                            str(first_source),
                        ],
                    ),
                    self._entry(
                        directory=project_root,
                        file=second_source,
                        arguments=[
                            "/usr/bin/c++",
                            "-c",
                            str(second_source),
                        ],
                    ),
                ],
            )

            result = infer_parser_config_from_compilation_database(build_dir)

        self.assertEqual(result.config.cxx_standard, "c++20")
        self.assertEqual(result.report.warnings, [])

    def test_reports_ignored_arguments_and_handles_compiler_wrappers(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            build_dir = project_root / "build"
            build_dir.mkdir()

            source_file = project_root / "src" / "alpha.cpp"
            self._write_compilation_database(
                build_dir,
                entries=[
                    self._entry(
                        directory=project_root,
                        file=source_file,
                        arguments=[
                            "/usr/bin/ccache",
                            "/usr/bin/c++",
                            "-pthread",
                            "-c",
                            str(source_file),
                        ],
                    ),
                ],
            )

            result = infer_parser_config_from_compilation_database(build_dir)

        self.assertEqual(result.config.toolchain_compiler, "/usr/bin/c++")
        self.assertIn("-pthread", result.ignored_arguments)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.report.warnings],
            ["config.compdb.unhandled_arguments"],
        )

    def test_strict_policy_reports_errors_and_omits_conflicting_scalar_extra_args(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            build_dir = project_root / "build"
            build_dir.mkdir()

            first_source = project_root / "src" / "alpha.cpp"
            second_source = project_root / "src" / "beta.cpp"
            self._write_compilation_database(
                build_dir,
                entries=[
                    self._entry(
                        directory=project_root,
                        file=first_source,
                        arguments=[
                            "/usr/bin/c++",
                            "-target",
                            "x86_64-unknown-linux-gnu",
                            "-c",
                            str(first_source),
                        ],
                    ),
                    self._entry(
                        directory=project_root,
                        file=second_source,
                        arguments=[
                            "/usr/bin/c++",
                            "-target",
                            "aarch64-unknown-linux-gnu",
                            "-c",
                            str(second_source),
                        ],
                    ),
                ],
            )

            result = infer_parser_config_from_compilation_database(
                build_dir,
                conflict_policy="strict",
            )

        self.assertEqual(result.config.extra_args, [])
        self.assertEqual(
            [diagnostic.code for diagnostic in result.report.errors],
            ["config.compdb.scalar_conflict"],
        )

    def test_format_report_includes_config_diagnostics_stage(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            build_dir = project_root / "build"
            build_dir.mkdir()
            self._write_compilation_database(
                build_dir,
                entries=[],
            )

            result = infer_parser_config_from_compilation_database(build_dir)

        rendered = format_report(result.report)

        self.assertIn("Config diagnostics:", rendered)

    def _write_compilation_database(
        self,
        build_dir: Path,
        *,
        entries: list[dict[str, object]],
    ) -> Path:
        build_dir.mkdir(parents=True, exist_ok=True)
        database_path = build_dir / "compile_commands.json"
        database_path.write_text(json.dumps(entries), encoding="utf-8")
        return database_path

    def _entry(
        self,
        *,
        directory: Path,
        file: Path,
        arguments: list[str],
    ) -> dict[str, object]:
        return {
            "directory": str(directory),
            "file": str(file),
            "arguments": arguments,
        }
