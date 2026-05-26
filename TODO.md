# TODO

Actionable backlog only. Keep long-term design intent and invariants in
`AGENTS.md`.

## Next Up

- Effective settings resolution across `.bind` and `.defaults`
- Translation from `.cpp` plus `.bind` into `.py`
- Activation-aware model behavior and filtered traversal of active bindable elements
- Better `CppType` query helpers for policy/emitter decisions
- Template instance selection/materialization ergonomics
- Layered type-binding policy resolution for external/STL/framework types:
  - exact site overrides for parameters/returns/variables
  - scoped defaults from function/class/namespace/module
  - global exact-type policies like `std::vector<int>`
  - global template-family policies like `std::vector<T>`
  - configurable global catch-all fallback policy

## Remaining Parser Work

### Areas that still need refinement

- C-API / `extern "C"` maturity follow-ups:
  - C-style function-pointer-heavy signatures and callback patterns need more real-world coverage
  - C-oriented ownership/lifetime conventions are still largely policy-layer work rather than parsed facts
  - Macros / `#define` constants remain out of parser scope and will need a separate strategy if they matter
  - Conditional-compilation matrix parsing/merge could be a valuable advanced feature for platform- or feature-gated APIs,
    but is probably overkill for the default path and should wait for a concrete need
- Redeclaration enrichment beyond the current conservative first pass
- Comment recovery edge cases around unusual placement/macros
- Structured type parsing and declaration linking for more clang type kinds
- Alias-target linking/emission behavior
- Access control / visibility coverage
- Variable metadata follow-ups such as `constinit` and `inline`, if later policy needs them
- Documentation/tag refinement such as `@throws`, `@exception`, `@remark`, and richer code/cross-reference handling

## Binding Model Work

- Richer hook model than plain `list[str]`
- Real property model for variables
- Iterator exposure policy
- External/prebound-type policy so parsed APIs can refer to types whose
  bindings/casters come from nanobind helpers, STL binders, or user code
- Container/STL binding policy separate from raw parsed `CppType` structure
- Policy matching/query layer for type patterns and exact concrete types
- Role-specific type policy where needed:
  - argument/input representation
  - return representation
  - field/property representation
- Buffer / ndarray / C-array adaptation policy for C-style pointer-and-size APIs
- More precise callable/argument policy:
  - keyword-only / positional-only
  - `noconvert`
  - `None` acceptance
- Better overload-group handling
- More complete return-value and ownership policy coverage
- Implicit conversion policy
- Custom constructor / init emission choices
- Namespace/module policy
- Richer enum export/flag/arithmetic behavior
- Richer class policy:
  - dynamic attributes
  - final / subclassability controls
  - trampoline/publicist generation controls
- Pickle / copy / deepcopy policy
- Custom wrappers/adaptors for awkward C++ APIs

## Translation Work

- Derived naming for template instances
- Operator translation into Python-facing names / dunder methods
- Python signature synthesis from callable shape, defaults, and `py.sig`
- Python doc translation/customization flow that preserves user edits by default

## Emitter Work

### Nanobind-first backend work

- Nanobind emitter implementation
- STL/container policy configuration
- `ndarray` policy and shape metadata
- Class flags such as dynamic attributes
- Explicit `__new__`-style construction policy where needed
- Exception registration/translation configuration

### General emitter work

- Template-family emission via generated C++ helper templates
- Incremental write behavior for generated files
- Namespace-to-Python-module emission behavior
- Emission ordering helpers that respect declaration and dependency order
- Pybind11 emitter after the nanobind pipeline is stable

## Configuration And Project Layer

- Keep `headers/` cleanly separated from parsing
- Revisit parser helper layering once the parse stage stabilizes
- Extend `ParserConfig` only where it buys real value:
  - compilation database integration
  - possible future recovery/debug toggles if needed
- Project-level configuration for:
  - module naming
  - top-level namespace handling
  - selected template instances
  - activation-header workflow
  - exception translation policy
  - possible future config-matrix parsing for selected preprocessor define combinations
- Emitter/backend configuration for output layout, signatures, and backend choice

## Test Coverage Still Worth Adding

- Real libclang integration test for scope-relative named type spellings
- Real libclang integration test for alias-preserving written spellings
- Real libclang integration test for typedef-preserving written spellings
- Real libclang integration test for reopened namespaces with multiple locations/comments
- Real libclang integration test for nested declaration linking inside spelling-parsed template arguments
- Real libclang integration test for operator-heavy example fixtures across member, hidden-friend, and templated operators

## Outputs Beyond Bindings

- Python stub generation
- Binding test scaffolding
- Better diagnostics and warnings tied to source locations

## Later / Nice To Revisit

- Box-type support if it proves useful
- Broader standard-library/framework-type policy once parse/translate/emit is stable
- Periodic review of `NotImplementedError` boundaries

## Missing or thin parsed facts

- Additional clang-exposed facts that may become binding-relevant:
  - function `inline` status if later policy or diagnostics need it
- Richer exception specifications beyond `is_noexcept`
- Additional method qualifiers such as `volatile`, if a real binding need appears
- `constexpr` / `consteval` metadata
- More structured template specialization behavior if a real binding need justifies it
- Classification for currently unclassified operator forms such as user-defined literal operators, if a concrete binding need appears
