# Project: C++ To Python Binding Generator

Oroboros builds nanobind first, and later pybind11, from C++ headers.

## Goal

Generate bindings from C++ headers through a staged pipeline:

1. `parse`: build a semantic C++ model from libclang
2. `translate`: derive Python-facing names/docs/signatures from `.cpp` plus `.bind`
3. `emit`: generate backend-specific binding code

The model is the main customization surface. Users should be able to parse a
header set, edit the model from Python, and then generate bindings.

## Core Rules

- Keep parser logic, policy logic, configuration, translation, and emission separate.
- Use `clang.cindex` / libclang as the semantic source of truth.
- Prefer clang-backed identity and semantic information over string parsing.
- Small local token/text checks are acceptable for narrow declaration-surface recovery.
- Do not do broader semantic reconstruction from spelling/text without confirming first.
- Avoid project-specific behavior in parser core; put policy in configuration or later stages.
- Do not edit `vault/` unless explicitly asked.

## Intended User Workflow

Users should be able to:

- discover a project’s headers
- choose an active subset to bind right now
- parse that active subset into one semantic model
- customize the model in Python
- emit nanobind bindings that mirror header/layout structure
- later emit stubs and test scaffolding

Important workflow decisions:

- configuration is Python-only
- header dependency order and header activation are separate concepts
- Python submodules should mirror C++ namespaces inside one compiled extension
- top-level namespace exposure should be configurable
- generated binding files should support incremental rewrites
- both raw C++ comments and normalized docs must be preserved

## Development Environment

- Python 3.12+
- Prefer `micromamba run -n oroboros ...`
- If micromamba cannot write to `~/.cache`, use:
  `XDG_CACHE_HOME=/tmp/micromamba-cache MAMBA_ROOT_PREFIX=/home/lucas/Software/micromamba-envs`
- Known-good test command:
  `PYTHONPATH=src XDG_CACHE_HOME=/tmp/micromamba-cache MAMBA_ROOT_PREFIX=/home/lucas/Software/micromamba-envs micromamba run -n oroboros python -m unittest discover -s tests`
- Prefer `unittest` unless `pytest` is known to be installed

## Current Architectural Decisions

- Implement nanobind first
- Keep the backend split clean so pybind11 can be added later
- Keep header discovery/activation in `headers/`, above parsing
- Public parse entrypoint consumes one `HeaderSelection`
- Parsing builds one translation unit from the active headers in configured order
- Clang sees transitive includes normally, but Oroboros only materializes declarations from active project headers
- Use one semantic declaration tree, not a flat list and not a raw AST mirror
- Keep one semantic node per semantic entity; repeated declarations enrich it
- Parser-local identity may use clang USRs, but those should not be stored in the public semantic model unless a concrete need appears

## Semantic Model

### General Shape

Use one semantic declaration tree:

- module owns top-level namespaces and declarations
- namespaces own nested namespaces, classes, enums, functions, variables, aliases
- classes/structs own constructors, destructors, methods, method templates, variables, nested enums, nested classes
- template-family nodes group one generic declaration with chosen instances

The underlying storage should stay as ordered typed lists. Convenience lookup
helpers can sit on top.

### Facets

Most semantic elements expose:

- `.cpp`: parsed C++ facts, read-mostly
- `.bind`: binding-generation policy for that element
- `.py`: Python-facing exposure choices
- `.defaults`: inherited defaults for descendants

Non-bindable structural elements may intentionally expose only the facets that
make sense. Today, destructors are modeled as parsed C++ facts only.

### Types

Types should be structured, not plain strings. The current design should preserve:

- builtin types
- named types
- pointers
- lvalue/rvalue references
- arrays
- function types
- const qualification
- template instantiations

`CppType` objects are embedded value objects, not tree nodes.

### Parameters

Parameters are first-class owned objects, but not full declaration scopes.

They should carry at least:

- C++ name
- structured C++ type
- default value
- source location when available
- parameter docs

Parameters expose `.cpp`, `.bind`, and `.py`, but not `.defaults`.

## Binding Model Guidelines

- `.bind` describes mechanics, activation, ownership, hooks, operator policy, etc.
- `.py` describes Python-facing names, docs, submodules, and signatures
- `.defaults.*` provides inherited descendant defaults through the declaration tree
- effective settings resolve upward by scope until an explicit override is found

Type-binding policy for parsed `CppType` values should stay separate from the
types themselves. `CppType` remains structured parsed C++ data; binding
representation and adaptation choices live in `.bind` configuration/defaults
and later translation.

For external, STL, and framework-provided types, Oroboros should support a
layered policy system with both type-specificity and declaration-scope
precedence:

1. explicit site override
   - parameter
   - return value
   - variable/property
2. scoped defaults
   - function/method
   - class
   - namespace
   - module
3. global exact-type policy
   - concrete type such as `std::vector<int>`
4. global template-family policy
   - type pattern such as `std::vector<T>`
5. global catch-all fallback policy
   - configurable, not backend hard-coded

This should allow one stable default for a type family, more specific defaults
for particular instantiations, and explicit local overrides where a particular
API wants a different Python-facing representation.

Examples of representation-level policy include:

- ordinary type-caster conversion
- helper-bound container/class exposure
- assumed externally prebound type
- explicit adapter paths such as `ndarray`

Activation/deactivation belongs to the binding layer:

- headers decide what enters the model at all
- `.bind.active` decides what remains bindable within that model

## Comments And Docs

The model should preserve both:

- `cpp.attached_comment`: parser-selected attached comment text
- `cpp.clang_raw_comment`: raw comment text reported by clang for provenance
- `cpp.doc`: normalized structured `CppDoc`

Later translation derives:

- `py.doc`: Python-facing documentation

Current comment strategy:

- ask clang for `raw_comment`
- recover nearby attached comments from tokens
- reconcile clang and recovery per cursor
- merge repeated declarations afterwards through normal redeclaration policy

Recovered blank-line-separated detached comments should be discarded without noisy warnings.

## Parser Scope

The parser should:

- build the declaration tree
- fill `.cpp`
- default-construct `.bind`, `.py`, and `.defaults`
- preserve provenance and diagnostics
- avoid backend/emitter decisions

### Current Implemented Coverage

The parser/model currently materializes:

- namespaces
- classes and structs
- unions
- class, function, method, and alias template declarations
- enums and enumerators
- aliases and typedefs
- free functions
- methods
- constructors
- destructors
- conversion functions
- variables
  - namespace/free variables
  - member variables
  - static member variables
  - member-variable field traits such as bitfield width and `mutable`
- parameters
- base classes
- source locations and provenance containers
- visibility where clang exposes it
- class-like abstract-record classification
- callable flags:
  - `const`
  - method/function-template ref-qualifiers `&` / `&&`
  - `virtual`
  - `noexcept`
  - constructor `explicit`
  - constructor/method special-member classification
  - converting-constructor classification
  - deleted/defaulted state
  - parameter default values
- parsed operator metadata for binding-relevant operator declarations
- structured recursive type parsing for common declaration-surface types
  - including function-pointer / callback-shaped types
- raw comments plus normalized docs
- token-based comment recovery and clang/recovery reconciliation

### Current Template Boundary

- template families and generic declarations are real model nodes
- selected instances are lightweight binding targets, not copied specialized trees
- use-site template-instantiated types carry structured template arguments
- observed class template instances can be collected from declaration-surface type uses
- explicit class-template specializations are not modeled as standalone specialized
  declaration trees yet; when the primary template family is materialized they
  currently contribute observed concrete arguments, otherwise they are ignored
- template parameter defaults are parsed into structured template arguments
- class-template partial specializations are intentionally not modeled for now:
  they are not required for binding concrete selected instances, and would add
  significant model/parser complexity beyond the current binding-focused scope
- use-site template-template arguments are still limited
- block-scope function-body observations remain intentionally out of scope

## Parse Package Layout

- `headers/model.py`: `HeaderSelection`
- `headers/find_headers.py`: header discovery helpers
- `headers/select_headers.py`: activation-header parsing and shaping
- `clang_driver.py`: libclang invocation / translation unit creation
- `build_model.py`: parse entrypoint and shared parser-local state
- `clang_walk.py`: cursor traversal and dispatch
- `cursor_data.py`: low-level clang cursor helpers
- `build_facets.py`: cursor-to-`.cpp` facet extraction
- `build_templates.py`: template-parameter extraction
- `comment_structure.py`: raw-comment normalization into structured docs
- `comment_recovery.py`: token-based attachment recovery and reconciliation
- `element_registry.py`: USR-based node reuse and namespace reopening
- `merge_declarations.py`: redeclaration merging and parser warnings
- `process_declarations.py`: declaration-kind-specific processing

## Important Modeling Rules

- Keep standard-library/framework types as `CppType` data, not declaration nodes
- Preserve written type spellings for emission portability
- Use canonical/structural types for reasoning and policy
- Treat hooks as explicit structured escape hatches, not synthetic parsed declarations
- Prefer external C++ hook files, while allowing inline hook fragments later if useful

## Remaining Parser Work

Highest-value remaining parser gaps:

- richer callable qualifiers beyond current coverage, if a real binding need appears
- fuller redeclaration enrichment where later declarations add useful facts
- more structured template behavior if a concrete binding need justifies it

Parsing is otherwise considered feature-complete enough for the current
binding-focused scope. Remaining work is now mostly semantic enrichment or
later-stage binding-model work rather than major missing clang declaration
coverage.

## Later Work Beyond Parsing

- effective settings resolution across `.bind` and `.defaults`
- translation from `.cpp`/`.bind` into `.py`
- nanobind emitter
- pybind11 emitter
- stub generation
- binding test scaffolding
- richer backend policy for STL/container handling, properties, iterators, and signatures
- binding-model support for externally provided or prebound types
- richer enum policy such as flag/arithmetic behavior
- richer class policy such as dynamic attributes, final/subclassability, and
  trampoline/publicist generation controls
- buffer / ndarray / C-array adaptation policy for C-style APIs
- richer ownership, pickle, copy/deepcopy, and container/iterator policies

## Naming Conventions

Prefer explicit `Cpp...` model class names, for example:

- `CppModule`
- `CppNamespace`
- `CppClass`
- `CppEnum`
- `CppFunction`
- `CppMethod`
- `CppConstructor`
- `CppVariable`
- `CppClassTemplate`
- `CppFunctionTemplate`
- `CppMethodTemplate`

Use `model/` as the package name rather than `ir/` or `elements/`.
