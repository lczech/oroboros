# TODO

This file is the working backlog for implementation tasks.

Keep long-term design intent, invariants, and architecture decisions in
`AGENTS.md`. Keep actionable next steps, open implementation gaps, and
prioritized engineering work here.

## Model Core

### High priority

- Effective settings resolution across `.bind` and `.defaults`.
  Needed for things like `active`, `return_value_policy`, `keep_alive`,
  holder types, hooks, and future policy inheritance.
- Translation layer from `.cpp` plus `.bind` into `.py`.
  Fill default Python names, docs, signatures, and operator exposure without
  overwriting explicit user edits unless requested.
- Activation-aware model behavior.
  Support effective active/inactive resolution and filtered traversal of only
  bindable active elements.
- Better type-query helpers on `CppType`.
  Add small helpers for common policy/emitter questions such as builtin vs
  named type, pointer/reference/value, constness, innermost named type, and
  template-family recognition.
- Template ergonomics for users.
  Selecting, materializing, and customizing template instances should become
  easier than working directly with low-level instance lists.

### Medium priority

- Shared callable-base facets if duplication grows further.
  Especially for common callable metadata shared between functions, methods,
  constructors, and template declarations.
- Clarify parameter semantics in the model design docs.
  Parameters are intentionally first-class objects, but not full declaration
  scopes in the same sense as namespaces and classes.
- Document parameter doc fields explicitly as lightweight strings derived from
  Doxygen parameter documentation, not full `CppDoc` or `PyDoc` objects.
- Consider a shared declaration-metadata facet only if repeated fields keep
  growing across namespaces, classes, enums, fields, and callables.

## C++ Semantic Coverage

### Still missing or incomplete

- Normalized comment and documentation parsing.
  Raw comment blocks are already preserved, but they still need to be parsed
  into the richer documentation model and parameter-doc fields.
- Unsupported libclang declaration kinds that should be tracked explicitly.
  The current walker materializes namespaces, classes/structs, enums,
  free functions, methods, constructors, fields, and parameters. Still
  missing at the cursor-dispatch level are:
  - `VAR_DECL` for free variables and static data members
  - `TYPE_ALIAS_DECL` and `TYPEDEF_DECL` for `using` / `typedef`
  - `CLASS_TEMPLATE` and `FUNCTION_TEMPLATE` for template declarations
  - `DESTRUCTOR`
  - `CONVERSION_FUNCTION`
  - `UNION_DECL`
- Alias templates.
- Destructors.
- Static or free variables and constants.
- Unions.
- Richer exception specifications beyond `is_noexcept`.
- Richer method qualifiers such as ref-qualifiers.
- Deleted/defaulted/constexpr/consteval metadata.
- Template specialization nodes and specialization-aware behavior.
- Preprocessor-conditioned API presence, if it becomes necessary.

### Partially covered, but likely still needs refinement

- Redeclaration enrichment.
  The parser now reuses semantic nodes by clang USR, merges provenance, and
  links named types back to declarations. Parameter-slot enrichment for
  repeated callables is now handled positionally, but fuller kind-specific
  redeclaration enrichment is still conservative first-pass behavior.
- Raw comment handling.
  Repeated-declaration comment conflicts are now resolved by parser policy, but
  the overall documentation flow is still incomplete until normalized docs and
  parameter docs are built on top.
- Structured type parsing and declaration linking.
  Recursive `CppType` parsing and deferred `NamedCppType.declaration` linking
  now exist, but more clang type kinds, richer qualifiers, and better
  user-facing type-query helpers are still needed.
- Type aliases / `using` / `typedef`.
  Lightweight alias metadata exists, but full alias handling and policy use is
  still incomplete.
- Access control and visibility.
  Visibility now exists on several semantic nodes, but access-specifier-driven
  behavior and parser coverage may still need refinement.
- Templates in general.
  Families, declarations, observed instances, and selected instances exist,
  but substitution/specialization behavior is still not complete.

## Binding Policy Model

### High priority

- Richer hook model than plain `list[str]`.
  Model hook kinds explicitly instead of storing raw strings only.
- Property model.
  Current field getter/setter knobs are not yet a real first-class property
  decision model.
- Iterator exposure policy.
- More precise callable and argument policy modeling.
  Include keyword-only, positional-only, `noconvert`, `None` acceptance, and
  similar argument-shape decisions.
- Better overload-group handling beyond preserving `overload_index`.
- More complete return-value-policy and ownership-policy coverage.

### Medium priority

- Implicit conversion policy.
- Custom constructor / init emission choices.
- Module / submodule policy for namespaces.
- Enum export-style and flag behavior beyond the current minimal fields.
- Custom wrappers / adaptors for awkward C++ APIs.

## Translation Layer

- Derived naming for template instances.
  This belongs in translation, not in raw parse state. It should be
  configurable and able to use spelled names, canonicalized names, or custom
  naming replacements.
- Operator translation into Python-facing names or dunder methods.
- Python signature synthesis.
  Combine parsed callable shape, parameter defaults, and `py.sig` overrides
  into a coherent Python-facing signature model.
- Python doc translation and customization flow.
  Preserve the current "fill missing values only" rule unless overwrite mode is
  requested.

## Emitter / Backend Work

### Nanobind-facing gaps

- STL/container policy configuration.
  Especially caster-vs-bind decisions such as `bind_vector` / `bind_map`.
- `ndarray` policy and shape metadata.
- Class flags such as dynamic attributes and similar backend-facing options.
- Explicit `__new__`-style construction policy where nanobind needs it.
- Exception registration / translation configuration.

### General emitter work

- Nanobind emitter implementation.
- Pybind11 emitter implementation after the nanobind pipeline is stable.
- Incremental write behavior for generated files.
  Write via temp files and replace only when content changes.
- Namespace-to-Python-module emission behavior.
- Emission ordering helpers that respect declaration order and dependency order.

## Parser / Project Configuration

- Revisit parser builder helper layering once the parse stage stabilizes.
  In particular, check whether the `build_*_cpp_facet()` helpers still buy
  enough readability over direct construction, and whether `clang_walk.py`
  can be shortened further without adding too much abstraction.
- Extend the existing parser configuration layer around libclang invocation.
  The current `ParserConfig` already covers include directories, defines,
  extra compiler arguments, language standard, resource directory, system
  include directories, and optional compiler-based toolchain autodetection.
  Remaining likely extensions are compilation database integration and a config
  parameter to decide what style of doc blocks to look for - doxygen styles,
  plain comments, etc, or auto (guessing or taking whatever is there).
- Project-level configuration for module naming, top-level namespace handling,
  selected template instances, activation-header workflow, and exception
  translation policy.
- Emitter/backend configuration for output layout, optional signature emission,
  and backend selection.

## Clang Integration Coverage

- Add one real libclang integration test for scope-relative named type
  spellings such as `types::OmenKind` and `Mortal::Vocation`.
- Add one real libclang integration test for raw comment extraction from
  Doxygen-style comment blocks.
- Add one real libclang integration test for alias-preserving type spellings,
  so declarations like `using Alias = Widget;` keep the written alias spelling
  while still linking to the resolved declaration where appropriate.
- Add one real libclang integration test for typedef-preserving type spellings,
  parallel to the alias case, to pin the intended separation between written
  spelling, declaration link, and canonical underlying type.

## Outputs Beyond Bindings

- Python stub generation.
- Binding test-stub generation.
- Better diagnostics and warnings tied to source locations.
  Especially for missing activation-header entries, unsupported declarations,
  skipped elements, and ambiguous user customizations.

## Nice To Revisit Later

- Box-type support similar in spirit to litgen, if it turns out to be useful.
- Broader coverage questions for standard-library types and other framework
  types once the basic parser/translate/emit pipeline is working well.
- Review `NotImplementedError` sites periodically to ensure the abstract
  methods that remain are still the right abstraction boundaries.
- In case of the user customization having an exception due to not finding a type,
  we could check if the git history of the to-be-bound repo contains a change
  that previously contained that type, and now changed, to aid the user in
  finding out why it broke. Maybe too fancy of an idea though...
