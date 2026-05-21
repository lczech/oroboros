# Parse Pipeline

The current parser is intentionally split into a few narrow pieces. The goal is
to keep libclang invocation, cursor walking, model building, and later policy
logic separate.

## High-level flow

Today the intended public parse flow is:

```python
selection = discover_headers("/path/to/include", umbrella_header="demo/all.hpp")
# Optionally:
# selection = select_active_headers(selection, "/path/to/activated_headers.hpp")

result = parse_header_selection(selection, config)
module = result.module
```

Where:

- `selection` is one `HeaderSelection` carrying both the known project-header
  inventory and the active subset
- `config` is a `ParserConfig`
- the result contains the built semantic module plus diagnostics and warnings

The public `headers/` layer sits one step above parsing:

- `headers/find_headers.py`
  discovers project headers either by recursive base-dir scan or by following
  one umbrella header's include closure within that base dir
- `headers/select_headers.py`
  optionally applies one activation header to mark a subset as active
- `parse/api.py`
  consumes the resulting `HeaderSelection`

## Translation unit strategy

Internally, the parser still builds one ordered list of active headers from the
selection and turns that into one synthetic include source, for example:

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

- `headers/model.py`
  Structured `HeaderSelection` input type used between header workflow and
  parsing
- `headers/find_headers.py`
  Header discovery helpers and umbrella-header include traversal
- `headers/select_headers.py`
  Activation-header parsing and selection shaping
- `parse/api.py`
  Public parse entrypoint `parse_header_selection(...)`
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
- the known project-header set
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
- class and function template declarations
- enums and enumerators
- aliases and typedefs
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
- observed class-template instances from declaration-surface type uses
- raw comment blocks

Still incomplete or follow-up work:

- normalized doc parsing on top of the already preserved raw comments
- operators
- destructors and conversion functions
- richer redeclaration enrichment
- `VAR_DECL`
- richer use-site template-template argument inference

## Validation during parsing

By default, `parse_header_selection(...)` validates the built semantic model before it
returns it:

- structural validation via `validate_tree()`
- semantic validation via `validate_semantics()`

This catches internal parser mistakes early and also helps keep manual model
customization honest later.
