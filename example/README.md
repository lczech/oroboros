# `example`

This directory contains a tiny standalone C++20 library and demo executable that exercise the kinds of declarations Ouroboros can parse and emit bindings for. We call the library and executable Cosmos, to make it stand out when working through this example; also, it is meant to include the "cosmos" (universe) of all bindable C++ constructions.

## Binding-oriented features included

- nested namespaces
- scoped and unscoped enums
- free functions and overloads
- default arguments
- structs with public fields
- classes, inheritance, and virtual methods
- nested enums inside classes
- operators on value types
- smart-pointer-based ownership
- header-only templates with explicit instantiation
- Doxygen-style comments

## Structure

- `bindings`: code to generate binding code for cosmos using ouroboros
- `inc`: header files of cosmos, used to generate bindings
- `src`: source files of cosmos, used to test the compilation

## Build

```bash
cd example
cmake -B build/
cmake --build build/
./build/cosmos_app
```
