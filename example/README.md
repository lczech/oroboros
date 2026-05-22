# `example`

This directory contains the mythology-themed `cosmos` example library and a tiny demo executable. `cosmos` is meant to grow alongside Oroboros: it starts as a small parser fixture today, and over time can expand into a broader "universe" of binding-oriented C++ examples.

## Current parser-oriented features

- top-level and nested namespaces
- scoped and unscoped enums
- free functions
- classes and structs
- constructors, methods, and parameters
- public and private member variables
- static member variables and free variables
- nested enums inside classes
- preserved raw comments plus normalized doc parsing for Doxygen/plain comments
- multiple inheritance via `Demigod : Mortal, Deity`

## Planned later layers

- `basics`: the current parser-first declarations
- `advanced`: richer C++ modeling such as aliases, comments, and templates
- `nanobind` features: focused fixtures for backend-specific binding patterns once emission work begins

## Structure

- `inc`: public headers parsed by Oroboros
- `src`: matching implementations and a tiny demo application
- `python`: helper scripts and activation-header experiments for Oroboros workflows

## Run the current parser

```bash
PYTHONPATH=src python3 example/python/generate.py
```

This updates `example/python/active_headers.hpp`, then feeds the resulting
`HeaderSelection` into `oroboros.parse_header_selection(...)` and prints the
resulting semantic tree plus any clang diagnostics.

The example headers now also include richer doc blocks, nested declaration
docs, and trailing member/enumerator comments so the printed parse tree can be
used to inspect comment normalization and recovery behavior as well.

The command expects a working `clang.cindex` Python setup. In practice that
means installing the `clang` Python package and making sure `libclang` itself is
available to that environment.

The example driver also asks `clang++` for its builtin resource directory and
system include search paths, then forwards those to libclang through
`ParserConfig(auto_detect_toolchain=True)`. That keeps the parser aligned with
the active compiler toolchain instead of hard-coding host-specific include
directories.

For now, the parser driver intentionally excludes the umbrella header
`cosmos/cosmos.hpp` and parses the concrete headers instead. That keeps the
example aligned with the current parser stage, which does not yet merge
redeclarations from both an umbrella include and the underlying leaf headers.

## Build

```bash
cd example
cmake -B build/
cmake --build build/
./build/cosmos_app
```
