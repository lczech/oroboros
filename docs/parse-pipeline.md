# Parse Pipeline

The current parser is intentionally split into a few narrow pieces. The goal is
to keep libclang invocation, cursor walking, model building, and later policy
logic separate.

## High-level flow

Today the intended parse entrypoint is:

```python
result = parse_headers(headers, config)
module = result.module
```

Where:

- `headers` is one ordered list of active project headers
- `config` is a `ParserConfig`
- the result contains the built semantic module plus diagnostics and warnings

## Translation unit strategy

The parser builds one synthetic include source containing the selected headers
in order, for example:

```cpp
#include "/path/to/a.hpp"
#include "/path/to/b.hpp"
#include "/path/to/c.hpp"
```

Libclang then parses that as one translation unit. Transitive includes are seen
normally by clang, but Oroboros only materializes declarations whose source
locations belong to the chosen active project-header set.

## Current parser package split

The current internal parser layout is:

- `parse/api.py`
  Public parse entrypoints such as `parse_headers(...)`
- `parse/config.py`
  `ParserConfig` for clang invocation and parser behavior
- `parse/result.py`
  Public parse result and diagnostic value objects
- `parse/clang_driver.py`
  Clang invocation and synthetic include source creation
- `parse/build_model.py`
  Public semantic-model build entrypoint and shared parser-local build state
- `parse/clang_walk.py`
  Cursor traversal, declaration dispatch, namespace reopening, skipped-kind
  tracking, and USR-based node reuse
- `parse/build_facets.py`
  Cursor-to-`.cpp` facet construction and lower-level cursor helpers
- `parse/types.py`
  Clang type to semantic `CppType` conversion
- `parse/toolchain.py`
  Toolchain autodetection for resource directory and system include paths

## Current build-state responsibilities

`BuildContext` stores parser-local mutable state during model building, such as:

- the active header set
- parser config
- the clang-USR-to-element map
- pending type-declaration links
- semantic warnings
- skipped cursor-kind counts

This state is intentionally parser-local and is not persisted into the semantic
model itself.

## Identity and redeclarations

The parser uses libclang USRs internally to keep one semantic node per semantic
entity:

- repeated declarations
- forward declarations
- later definitions

Instead of creating duplicate model nodes, later occurrences enrich the
existing node where possible.

This identity map is also used to connect `NamedCppType.declaration` back to
parsed declarations when libclang exposes enough information to do so.

## Current semantic coverage

The implemented parser already materializes:

- namespaces
- classes and structs
- enums and enumerators
- free functions
- methods
- constructors
- fields
- parameters
- class base relationships
- source locations and provenance
- visibility where clang exposes it
- basic callable flags such as `const`, `virtual`, and `noexcept`
- recursive structured `CppType` objects
- deferred `NamedCppType.declaration` links where clang exposes declaration
  identity clearly enough
- raw comment blocks

Still incomplete or follow-up work:

- normalized doc parsing on top of the already preserved raw comments
- aliases
- templates
- operators
- destructors and conversion functions
- richer redeclaration enrichment
- additional C++ qualifiers and metadata

## Validation during parsing

By default, `parse_headers(...)` validates the built semantic model before it
returns it:

- structural validation via `validate_tree()`
- semantic validation via `validate_semantics()`

This catches internal parser mistakes early and also helps keep manual model
customization honest later.
