# Project: CPP to Python Binding Generator

This project develops a Python-based C++ to Python binding generator for C++ libraries.

## Goal

Generate nanobind and pybind11 bindings from C++ headers.

## Overall architecture

- Keep parser logic, policy logic, configuration, and emitter logic separate.
- Use libclang / clang.cindex as the semantic source of truth.
- Extract namespaces, classes, structs, enums, functions, constructors, methods, fields, base classes, and comments.
- Build a semantic C++ model before emitting bindings.
- Allow full customization in the model, such as return value policies, removal and addition of functions, etc.
- Respect the C++ header dependency order to ensure compilation will work.
- Preserve Doxygen-style comments from C++ declarations where possible.
- Emitter should target nanobind and pybind11.
- Implement nanobind first, but keep the emitter split clean so pybind11 can be added later without redesigning the pipeline.

## Specific design direction, to be worked on bit by bit

I want to use the final product as follows:

- In my C++ library (genesis, as an example, see the references), I will have a script `genesis/python/generate.py`, which will utilize this library here (Oroboros) to generate bindings code for genesis, targeting nanobind.
- When executed, the script will scan the library headers (in `genesis/lib`), and build the semantic model from that. Further, it will take a set of configurations and customizations (as python and c++ code, also in `genesis/python`), defining how to build the model, and customize it.
- Configuration should be Python-only. Users should not need to learn an ad-hoc configuration language, and the API should ideally be discoverable from interactive Python sessions.
- Configuration: Take an "all include" C++ header as one input, which defines the C++ headers and their dependency order.
- Separately, support an "activated headers" list that decides which headers are currently included in binding generation. This can be another C++ include header with commented and uncommented includes, or an equivalent Python-readable representation if that turns out cleaner.
- Only active headers shall be parsed for binding generation. If any include in the activation list is commented out, Oroboros shall ignore it and not generate bindings for code in that header.
- If any known library header is missing from the activation list entirely, a warning should be emitted.
- Instead of binding everything at once, allow incrementally adding headers from this list of activated headers. This allows to build the bindings step by step, instead of having to deal with many errors at once.
- Then, the `generate.py` script will build the semantic model for those active headers, amended by extra configuration, such as excluding certain functions, classes, and class members, return value policies, copy and other operators (translate to dunder methods where possible), converting iterations, and all the nice things that pybind and nanobind offer - fully configurable via the model for each class and function.
- This shall also allow to add new bindings, such as extra functions or class members. For now, these should preferably be expressed via explicit custom binding hooks that are emitted alongside the generated bindings, rather than by introducing synthetic declarations directly into the semantic model.
- Custom add-ons should preferably work as external C++ hook files, similar to the current Binder approach, while still allowing inline custom C++ hook fragments where useful.
- Also, things like which template instances to create for class and function templates will be decided via configuration per class and function.
- Finally, the script will call the generate() function of Oroboros, which will generate the bindings code into `genesis/python/bindings`. The files in there are auto-generated, and wil be scanned by the CMake setup, containing the main module for pybind/nanobind, and all bindings code needed.
- The file structure of the auto-generated bindings files shall follow the original header file names and paths, i.e., mirror them, and allow incremental builds. That is, when re-generating a bindings file, before writing it out, it needs to be written to a temp location, and only if content differs with the existing file, will it be overwritten, so that time stamps allow CMake to avoid recompilation.
- Everything should follow namespaces, and fully qualify names, or use the model to descend into namespaces etc when customizing the bindings.
- Python submodules should mirror the C++ namespaces, while still compiling into a single nanobind extension module.
- It should be configurable whether the top-level C++ namespace becomes the Python module root directly, or whether it is exposed as an explicit first submodule.
- Documentation of all C++ code (Doxygen-style) shall be preserved and added to the generated files (without the leading `*`, and with some Python-style equivalent of the `@` annotations of Doxygen).
- The model should preserve both the raw C++ comments and a normalized docstring-oriented representation, so documentation can also be customized before emission.
- Python stub files shall be generated in `genesis/python/stubs`, either as a single file or set of files. These should be usable for IDEs etc for code completion and documentation, i.e., contain the doc strings as well as the (nanobind-generated?) signatures.
- Generate test cases for the bindings, that hit every class and funtion, to show that the binding worked. This should also allow to use existing C++ test (e.g., gtest) as guidance, and replicate them in Python. But mostly, tests on the Python end should focus on the binding interface, to ensure that is working correctly. We can mostly assume that that internal functionality of the C++ side is already tested there. In other words, oroboros should create test stubs for every class and function with bindings, simply default constructing them and their arguments (or, if no default constuctor is available, recursively create the needed objects, until everything is constructed). Ideally, this will already serve as a testing framework - but likely will breat, as default constructed arguments will not always work. In these cases, the auto-generated tests will serve as a scaffold for the user of oroboros to more easily develop actual tests of the bindings.

The goal of Oroboros is to allow creating bindings this way. It thus needs to provide all the mentioned functionality, which will then be called and used from genesis. Note that genesis is only inteded to be used as the exemplary library that motivates the development of Oroboros. Its name or paths or anything should never be mentioned in Orobors itself, and everything should be configurable instead. Genesis itself will then use Oroboros functionality to make its bindings. Ideally, genesis will only need to set up the configuration, call the function to parse the headers, then add its customization as needed on top, using the model, and then call the function to write out the generated code. All the rest shall be handled by Oroboros here. If any of the concepts or configurations are too specific for genesis alone, where it makes sense, it should be implemented in a more generic way as well, so that other libraries will be able to use this project as well.

As this is a lot of functionality, we will build the Oroboros code incrementally, and test it in parallel in genesis.

## Coding style

- Python 3.12+.
- Use dataclasses or pydantic-style models for the semantic model.
- Keep functions small and testable.
- Add short comments for each function and class to state their purpose.
- Add short (one or two line) comments for code blocks, explaining their intend (e.g., what does the loop do?).
- Avoid hard-coding Genesis-specific behavior in the parser core; put policy in configuration instead.

## Development environment

- The checked-in `environment.yml` currently defines the micromamba environment `oroboros`.
- When running commands non-interactively, prefer `micromamba run -n oroboros ...` instead of relying on shell activation.
- In sandboxed environments, `micromamba` may fail if it cannot write to the default cache directory under `~/.cache`.
  In that case, prefix commands with:
  `XDG_CACHE_HOME=/tmp/micromamba-cache MAMBA_ROOT_PREFIX=/home/lucas/Software/micromamba-envs`
- A known-good test command pattern is:
  `XDG_CACHE_HOME=/tmp/micromamba-cache MAMBA_ROOT_PREFIX=/home/lucas/Software/micromamba-envs micromamba run -n oroboros python -m unittest discover -s tests`
- The `oroboros` environment contains the required clang Python bindings, but may not contain `pytest`.
  Prefer the repository's `unittest` commands unless `pytest` has been installed explicitly.

## Current decisions

- Implement nanobind first.
- Keep the backend emitter split clean so pybind11 can be added later.
- Use Python-only configuration APIs.
- Keep header dependency order and header activation as separate inputs.
- The parse stage should take one ordered list of active headers to build right now.
  The broader "all known headers" inventory and activation-header workflow live one layer above parsing.
- Parsing should build one synthetic translation unit that includes those active headers in the configured order.
  Clang will still see transitive includes normally, but Oroboros should only materialize declarations whose source file belongs to the active project-header set.
- Use one semantic tree of C++ declaration objects rather than a flat list or a raw AST.
- Split each declaration object into facets: `.cpp` for parsed C++ facts, `.bind` for binding-generation settings, `.py` for Python-facing exposure choices, and `.defaults` for inherited descendant defaults.
- Keep the parsed `.cpp` facet read-mostly, and express user customization mainly through `.bind`, `.py`, and `.defaults`.
- The intended high-level stages are `parse`, `translate`, and `emit`.
  Parsing creates the semantic tree with `.cpp` filled and both `.bind` and `.py` default-constructed.
  Translation derives or fills `.py` from `.cpp` and `.bind`.
  By default, translation should populate only missing Python-facing values and preserve user edits, unless an explicit overwrite mode is requested.
  Emission generates the final backend code from the translated model.
- Use typed descendant defaults rather than putting every possible binding setting on every node.
  For example, namespaces may expose `.defaults.class_`, `.defaults.function`, and `.defaults.enum`, while classes may expose `.defaults.method`, `.defaults.constructor`, `.defaults.field`, and `.defaults.enum`.
- Store direct binding settings on the element itself via `.bind`, and store inherited child defaults in `.defaults`.
- Resolve optional binding settings by inheritance through the declaration tree, walking upward through scopes until an explicit override is found.
- Support activation and deactivation inside the model as part of the binding customization layer, so whole namespaces, classes, or individual members can be disabled incrementally before Python-facing translation.
- Model template families, generic template declarations, and template instances separately.
  A `CppClassTemplate` or `CppFunctionTemplate` groups one generic parsed declaration in `.declaration`, any selected concrete `.instances`, and `.defaults` that apply to those instances and their descendants.
  Template instances shall be first-class customizable objects with their own `.cpp`, `.bind`, `.py`, and `.defaults`.
- Prefer external C++ add-on hooks for custom bindings, while still allowing Python-driven model customization.
- Mirror C++ namespaces as Python submodules within a single compiled extension module.
- Make the handling of the top-level namespace configurable.
- Preserve both raw and normalized documentation in the model.
- During parsing, keep one semantic node per semantic entity rather than creating duplicate tree nodes for forward declarations and collapsing them later.
  Repeated declarations, forward declarations, and later definitions should enrich the same semantic node.
- The parser may use backend-specific identity helpers internally, such as clang USRs stored in a parser-local symbol table, but those identifiers should not be stored in the semantic model unless a later concrete need arises.
- Organize the semantic model in multiple files under a `model/` package, split by concern and declaration kind, similar in spirit to litgen's split but simpler and more binding-oriented.
- Defer stub generation and binding-test generation until after the basic parser, model, and emitter pipeline works, but design the system so those later stages fit naturally.

## Semantic model design

The semantic model is intended to be the central working object graph of Oroboros. It should be rich enough to preserve C++ structure and comments, but still simpler and more binding-oriented than a source-faithful AST. The parser should fill this model from libclang, and later stages should customize and emit from it.

### High-level shape

- Use one semantic tree of declaration objects.
- Avoid a completely flat list of declarations, because ownership and scope matter.
- Avoid a raw AST mirror, because syntax-level details that are irrelevant for binding generation would add complexity without enough value.
- Treat the model as a semantic declaration tree: namespaces own declarations, classes own members, and template family nodes group one generic declaration with its chosen instances.

This means:

- the module owns top-level namespaces and top-level declarations
- a namespace owns nested namespaces, classes, enums, and free functions
- a class or struct owns constructors, methods, fields, nested enums, and nested classes
- template family nodes group explicit template instances to be bound

Every node should know:

- its owning scope
- its children, in typed lists
- its identity and qualified name
- its source location and comments
- whether it is active directly or effectively

This structure should make it natural to:

- descend into namespaces and classes while customizing
- deactivate a whole class or namespace
- compute inherited defaults by walking upward
- emit code in scope-respecting order

For interactive Python usage, the model should also remain easy to navigate
without forcing users to remember many specialized helper names. In addition
to typed child lists such as `.namespaces`, `.classes`, `.functions`, and
`.methods`, scope-like nodes may expose lightweight name-indexed navigation and
discovery helpers on top of those lists.

The intended interaction style is:

- direct-child navigation via `scope["name"]`, returning one direct child when
  unique and a list for overloadable direct-child groups such as functions,
  methods, and constructors
- typed direct-child views such as `module.namespace["demo"]`,
  `namespace.class_["Widget"]`, or `class_.method["size"]`
- subtree search via generic helpers such as `find()` and `find_all()`, in
  addition to the more explicit `find_one_by_name()` and
  `find_one_by_qualified_name()` variants
- direct-child discoverability via `scope.element_names` for quick interactive
  inspection of available names at the current level

These helpers should stay as a user-facing layer on top of the existing list
storage. The underlying model should still preserve declaration order in typed
lists rather than replacing those collections with dictionaries.

### Parsing approach

The parser should stay narrow in responsibility:

- build the semantic declaration tree
- fill `.cpp`
- default-construct `.bind`, `.py`, and `.defaults`
- preserve source facts and provenance
- avoid binding-policy and backend-emission decisions

The intended parse workflow is:

- accept one ordered list of active project headers
- build one synthetic header or equivalent translation-unit input that includes those headers in order
- let clang follow transitive includes normally
- materialize only declarations whose source file belongs to the active project-header set

The `parse` package itself may depend directly on `clang.cindex`. If clang is
not available, parsing should fail clearly when the parse layer is imported or
used. It is still acceptable for the top-level package to expose parse-related
APIs lazily so that model-only utilities remain importable in environments that
do not have libclang installed.

This means:

- declarations from external libraries and inactive project headers may still appear indirectly in types
- those referenced types should remain type information, not automatically become bound declaration nodes
- if an active declaration references another known project declaration from an inactive header, Oroboros should warn instead of silently auto-activating or auto-binding that header

Namespace reopening should be handled parser-side via get-or-add behavior keyed by owner plus namespace name, so reopened namespaces enrich one semantic namespace node.

Other declarations should not be merged by plain names, because overloads and templates make names insufficiently unique. The parser should instead use a backend-specific internal identity registry, such as a clang-USR-to-node map, to enrich one semantic node as redeclarations and definitions are encountered.

That parser-local identity registry should live in the model-building stage, not
in clang driver setup. Its intended jobs are:

- merge repeated declarations and forward declarations into one semantic node
- support later linking of `NamedCppType.declaration` back to parsed
  declarations by semantic identity rather than guessed name matching
- support alias parsing and similar declaration-to-declaration relationships
- provide a stable backbone for provenance and redeclaration diagnostics

The semantic model itself should remain backend-neutral. Parser identities such as clang USRs are useful internally during parsing, but should not be persisted in the user-facing model unless a concrete later need arises, such as incremental reparsing.

The current implemented parser slice already materializes:

- namespaces
- classes and structs
- enums and enumerators
- aliases and typedefs
- free functions
- methods
- constructors
- fields
- parameters
- class base relationships
- source locations and provenance containers
- visibility where libclang exposes it
- basic callable flags such as `const`, `virtual`, and `noexcept`
- structured recursive types for builtins, named types, pointers, references,
  arrays, function types, and simple template-instantiation spellings

The current parser internals are also intentionally split into:

- `clang_driver.py` for libclang invocation and translation-unit creation
- `build_model.py` for the public semantic-model build entrypoint and shared
  parser-local build state such as the active-header set and USR map
- `clang_walk.py` for cursor traversal, dispatch, namespace reopening, skipped
  kind tracking, and USR-based node reuse
- `build_facets.py` for cursor-to-`.cpp` facet extraction and lower-level
  cursor data helpers

Comments/docs, templates, operators, destructor/conversion functions, and
fuller parser-side redeclaration enrichment are still follow-up work.

The next parser work should focus first on:

- redeclaration enrichment beyond simple node reuse, so later declarations can
  add missing facts such as definitions, declaration locations, and richer
  metadata to already-created nodes
- linking `NamedCppType.declaration` back to parsed declaration nodes via the
  parser-local USR registry where libclang provides enough identity
- parsing `using` and `typedef` aliases, using the same identity and linking
  infrastructure rather than string-based matching

### Naming

Prefer `model/` over `ir/` or `elements/` for the package name, and prefer explicit `Cpp...` class names for parsed declaration nodes.

Examples:

- `CppModule`
- `CppNamespace`
- `CppClass`
- `CppStruct`
- `CppEnum`
- `CppEnumerator`
- `CppFunction`
- `CppMethod`
- `CppConstructor`
- `CppField`
- `CppClassTemplate`
- `CppClassTemplateDecl`
- `CppClassTemplateInstance`
- `CppFunctionTemplate`
- `CppFunctionTemplateDecl`
- `CppFunctionTemplateInstance`

The intention is:

- `Cpp...` names mean parsed or semantically derived C++ entities
- the element object itself is the user-facing object to customize
- internal helper classes can have more technical names where needed

### One object, multiple facets

Each semantic element should expose multiple facets instead of splitting parsed data and customization into separate trees.

The main facets are:

- `.cpp`
- `.bind`
- `.py`
- `.defaults`

This gives users one object graph to work with, while still keeping concerns separated inside each object.

#### `.cpp`

This facet stores parsed C++ facts and should be treated as read-mostly by convention.

Typical contents:

- original C++ name
- semantic qualified name exposed on the element itself via the ownership chain, rather than duplicated redundantly inside `.cpp`
- scope path
- kind information such as class/struct/enum/function/method
- source location
- raw comment
- normalized comment
- alias target type for alias declarations
- parameters
- return type
- bases
- template parameters
- enum values
- overload and signature information
- overload group membership and overload order
- structured type information for declarations and parameters

Examples:

- for a class: class kind, base classes, nested declarations
- for a function: parameter list, return type, noexcept, constness, staticness
- for an enum: enum kind, enumerators, underlying type if needed later

Types should not remain plain strings for long. The model should preserve spelled C++ text, but also introduce a structured type model early. At minimum, that type model should distinguish:

- named types
- builtin types
- pointers
- lvalue references
- rvalue references
- arrays
- function types
- const qualification
- pointee or referred type
- template instantiations

The recursive wrapper pattern should be preserved in the type model:

- `NamedCppType` stores the original spelled name, an optional declaration target, and an optional canonical underlying type for reasoning
- `BuiltinCppType` stores true language fundamental types such as `int`, `bool`, and `std::nullptr_t`
- pointer, reference, and array types wrap inner `CppType` objects
- function pointers should be represented structurally as a pointer or reference that wraps a `FunctionCppType`

More specialized type forms such as member pointers, optional-like types, and variant-like types can be added later as needed.

`CppType` objects should be treated as embedded value data, not as semantic tree nodes. This means:

- `CppType` objects do not participate in the owner/child declaration hierarchy
- they live inside `.cpp` facets where declarations need to describe a type, such as parameter types, return types, field types, base-class types, alias targets, and template argument or parameter types
- the same semantic type may appear multiple times as separate `CppType` values at different use sites, which is acceptable and expected
- where a named type refers to a declaration that is present in the semantic tree, the `NamedCppType` should link back to that declaration node via its optional declaration reference

For example:

- one `CppClass` node represents the declaration of `Widget`
- multiple functions may each contain their own `NamedCppType(name="Widget")` or `NamedCppType(name="Widget", declaration=that_class)` in parameter or return types
- those per-use type objects describe how the declaration is referenced at each use site, while the declaration node itself remains the canonical place to customize binding behavior for the class

Users should generally not mutate `.cpp` except for advanced internal transforms.

Standard-library and other well-known framework types should not be modeled as special declaration nodes in the semantic tree. Instead:

- preserve the original spelled type text for later emission
- preserve a canonical or normalized underlying type for semantic reasoning
- recognize standard-library families such as `std::vector`, `std::map`, `std::optional`, `std::variant`, and `std::function` from the canonical structural type, not from the raw source spelling
- allow the parser to refer to those families through `CppType` objects rather than by creating semantic declaration nodes for standard-library declarations

This is important because the source may use:

- unqualified spellings enabled by `using namespace std`
- aliases such as `using IntVec = std::vector<int>`
- implementation-specific or ABI-decorated spellings that appear in diagnostics

The intended rule is:

- emit the original source spelling by default, so generated bindings remain portable and follow the library headers closely
- use the canonical type only to detect semantic families and apply binding policy

This should make it possible to generate portable binding code such as `uint64_t` or `std::vector<int>` without rewriting those types into platform-dependent underlying spellings such as `unsigned long`.

Binding policy for recognized library types should be configured outside the declaration tree, at project or generation configuration level. That policy should support both:

- family defaults, for example all `std::vector<...>` use cast mode by default
- exact-instance overrides, for example `std::vector<int>` uses binding mode while `std::vector<Widget>` still uses cast mode

This two-level policy is intended to support backend choices such as nanobind type casters versus explicit helper bindings for the same template family.

#### Parameters

Function and method parameters should be first-class model objects, but they do not need to be full peers of declaration nodes.

Recommended shape:

- parameters are owned by functions, methods, and constructors
- parameters should not have `.defaults`
- parameters should not act as scopes
- parameters should not have general-purpose hooks initially

However, parameters still need more than a plain name and type. They should preserve enough information for binding behavior and documentation.

At minimum, a parameter should carry:

- C++ name
- structured C++ type
- default value information
- source location when available
- parameter documentation derived from C++ comments

Parameters should also support lighter-weight Python and binding customization. A practical design is:

- `param.cpp`
- `param.py`
- `param.bind`

without a `param.defaults` facet.

Typical parameter-side Python or binding details include:

- Python argument name override
- `None` acceptance
- `noconvert` behavior
- keyword-only or positional-only behavior if needed later
- Python-facing default-signature override via `param.py.sig` when needed for nanobind-style signature customization

This keeps parameters first-class and customizable without over-promoting them into full declaration containers.

#### `.py`

This facet stores Python-facing exposure choices. It answers: “how should this element appear in Python?”

This facet should be default-constructed during the initial parse phase, but translation should later fill it from `.cpp` and `.bind`.
By default, translation should only fill fields that are still unset, so users may customize `.py` early without losing those edits.

Rule of thumb:

- if a setting changes binding mechanics, lifetime rules, backend calls, or whether something is bound at all, it belongs in `.bind`
- if a setting changes what Python users see, call, import, or read, it belongs in `.py`
- for gray areas, keep the policy or decision in `.bind`, and keep the final exposed Python name, docstring, or rendered signature in `.py`

Typical contents:

- Python name override
- docstring override
- Python submodule override
- `sig` override for callable, constructor, or parameter nanobind-style signature customization
- later: rendered Python signatures, naming policy exceptions, and other Python-surface presentation details

Examples:

- `func.py.name = "to_string"`
- `ns.py.submodule = "placement"`

Users may customize `.bind` and `.py` incrementally from the start, but the usual workflow is still to decide binding behavior in `.bind` first and then refine Python-facing polish in `.py` after translation has filled default values.

#### `.bind`

This facet stores binding-generation settings for the element itself. It answers: “how should this element be bound?”

Rule of thumb:

- `.bind` is primarily the input policy for translation and emission
- `.py` is primarily the translated Python-facing surface that later stages such as stub generation and documentation emission should consume

Typical contents differ by element kind.

For functions and methods:

- active / inactive state
- return value policy
- keep_alive rules
- call guards
- argument policy overrides
- backend-neutral ownership semantics where possible
- operator translation mode
- custom binding hooks

For classes:

- active / inactive state
- holder type
- trampoline settings
- custom init policy
- copy/move exposure policy
- backend-specific extras only when truly needed later

For fields:

- active / inactive state
- readonly / readwrite policy
- getter/setter customization

For enums:

- active / inactive state
- export style
- scoped/unscoped exposure choices

This should contain only direct settings for the element itself, not inherited descendant defaults.

Operator translation should primarily live in `.bind`.

Recommended default behavior:

- operators that have a sensible Python mapping should be translated automatically to the corresponding dunder method
- the `.cpp` facet should preserve which C++ operator declaration was parsed
- a structured `CppOperator` object should be stored inside the `.cpp` facet of free functions and methods when the declaration is an operator
- the `.py` and `.bind` facets should control how that operator is exposed

The operator-specific binding choices should live in a small structured object inside `.bind`, separate from the parsed `CppOperator` facts stored in `.cpp`.

If a user disables dunder-style exposure and instead binds an operator as a normal function, the Python-facing name should be validated, because names such as `operator++` are not valid Python function names.

If named operator exposure is selected and no explicit Python-facing name override is provided, the emitter should generate a valid fallback name automatically, for example `operator_plus`, `operator_brackets`, or similar readable forms derived from the C++ operator.

Custom binding extensions should also live in `.bind`, via an explicit `.bind.hooks` collection rather than via a single opaque code string.

Recommended properties of `.bind.hooks`:

- it should support multiple hooks, not just one
- hook order should be preserved
- hooks should be modeled explicitly, not as untyped strings

Useful hook forms include:

- a C++ hook function name that the emitter will call with the bound nanobind object
- inline C++ binding code snippets for smaller customizations
- later, if needed, Python-side generation callbacks

Hooks should be attachable to the element kinds where extra binding statements are naturally meaningful, especially:

- module-level bindings
- namespaces
- classes

The emitted hook call should receive the bound nanobind scope object appropriate for that element, for example:

- module hook receives the module object
- namespace hook receives the namespace or submodule binding object
- class hook receives the `nb::class_` binding object

This should make it possible to add extra free functions to a namespace or extra methods and properties to a class without requiring Oroboros to model synthetic declarations yet.

The first implementation should focus on C++ hook functions and optionally inline C++ code, because those already allow users to:

- add extra free functions to a namespace
- add custom methods or properties to a class
- replace or supplement generated bindings without requiring Oroboros to model synthetic declarations yet

This hook mechanism should be treated as a deliberate escape hatch for advanced customization, while the main semantic model continues to describe parsed declarations only.

#### `.defaults`

This facet stores inherited defaults for descendants. It answers: “what settings should child elements use if they do not override them directly?”

Use typed descendant-default buckets rather than putting every possible setting on every node.

Examples:

- for a namespace:
  - `.defaults.namespace`
  - `.defaults.class_`
  - `.defaults.function`
  - `.defaults.enum`
- for a class:
  - `.defaults.class_`
  - `.defaults.method`
  - `.defaults.constructor`
  - `.defaults.field`
  - `.defaults.enum`

These buckets should contain the same typed binding objects that direct elements use in `.bind`.

Examples:

- a function node has `.bind: FunctionBind`
- a method node has `.bind: MethodBind`
- a constructor node has `.bind: ConstructorBind`
- a class node has `.bind: ClassBind`
- a class node also has `.defaults.method: MethodBind`
- a class node also has `.defaults.constructor: ConstructorBind`
- a namespace node may have `.defaults.function: FunctionBind`

This keeps inheritance expressive without giving namespaces a giant flat set of function-only fields.

### Direct settings versus inherited settings

The distinction should be strict:

- `.bind` applies to the element itself
- `.defaults.*` applies to descendants

Examples:

- `function.bind.return_value_policy` affects only that function
- `class.defaults.method.return_value_policy` affects methods of the class that do not override it
- `namespace.defaults.class_.holder_type` affects enclosed classes unless they override it

This is the main mechanism for scope-aware customization.

### Inheritance strategy

Binding settings should typically default to `None`. `None` means “not set here, inherit or fall back.”

Resolution should walk upward through scopes until it finds an explicit value.

For example, a method’s effective return value policy should be resolved in roughly this order:

1. `method.bind.return_value_policy`
2. enclosing class `defaults.method.return_value_policy`
3. outer namespace `defaults.function.return_value_policy`
4. module-level defaults
5. backend or generator default

The same general mechanism should apply to:

- active/inactive state
- Python naming defaults
- holder types
- field exposure choices
- enum export choices
- operator translation defaults

The important rule is that inheritance should be explicit in the resolver, not simulated by physically copying values into every node.

Exception handling needs two levels of design:

- exception types that exist in the parsed C++ model
- exception translation policy that maps thrown C++ exceptions to Python exceptions

Exception types themselves should be modeled like other classes when they are part of the parsed API.

Exception translation policy should live primarily in global or project-level generation configuration rather than in per-element semantic model state.

This means exception translation should not be treated as purely per-class configuration in the semantic tree, even though exception classes themselves are ordinary model elements.

### Configuration layers

The semantic model is not the right place for every decision. Oroboros should also maintain explicit configuration layers outside the declaration tree.

These configuration layers should remain separate from per-element model state:

- parser configuration
- project or generation configuration
- emitter or backend configuration

#### Parser configuration

This should cover things needed to invoke clang correctly, for example:

- include directories
- preprocessor defines
- extra compiler arguments
- language standard
- later, possibly compilation database or equivalent integration

#### Project or generation configuration

This should cover project-wide policies that are not naturally owned by a single declaration node, for example:

- module name
- top-level namespace handling
- exception translation policy
- chosen template instances to bind
- which custom hooks are enabled at a broad scope
- activation-header paths and related workflow settings

#### Emitter or backend configuration

This should cover output-formatting and backend-specific choices, for example:

- whether to target nanobind or pybind11
- optional inclusion of C++ signatures in Python docstrings
- output file layout and incremental write behavior
- later, backend-specific policy defaults where necessary

The rough rule is:

- if a setting describes one declaration or a subtree of declarations, it likely belongs in the semantic model
- if a setting describes how the whole project is parsed or emitted, it likely belongs in configuration instead

### Activation and deactivation

Activation should be part of the binding customization layer, because it controls what bindings are generated before Python-facing translation occurs.

Recommended behavior:

- every bindable element can be active, inactive, or inherit
- a parent set inactive should effectively deactivate descendants unless they explicitly override it
- the selected-header mechanism controls which headers enter the model in the first place
- the per-element active flag then allows narrower pruning inside the model

Examples:

- disable a whole namespace for now
- disable one class that causes binding trouble
- disable one overloaded function or one problematic field

This allows incremental binding development without having to remove declarations from the parsed model.

Parameter objects should not support this activation flag. Hiding or reshaping parameters is a later wrapper or adaptor concern, not ordinary activation/deactivation of parsed declarations.

### Comments and source locations

Documentation should be preserved in a structured way across the C++ and Python facets.

On the C++ side, each documented element should expose:

- `cpp.comment`: the raw original comment text as found in the source file
- `cpp.doc`: a parsed and normalized `CppDoc` object

The intention is:

- `cpp.comment` preserves the source-of-truth text exactly as it was written
- `cpp.doc` stores a structured Doxygen-oriented interpretation of that text

`CppDoc` should be designed around Doxygen-style concepts, for example:

- brief summary
- longer description
- parameter documentation
- return documentation
- notes
- warnings
- see-also references
- any additional parsed tags that are useful later

On the Python side, each bindable element should expose:

- `py.doc`: a `PyDoc` object

The intention is:

- `py.doc` is the final Python-facing documentation model
- it should be initialized automatically from `cpp.doc`
- users may then modify `py.doc` directly without touching the original C++ documentation data

The first implementation should use one Python-oriented documentation style only, close to Doxygen in spirit, rather than supporting multiple formatting styles immediately.

This means:

- keep structure such as parameters and returns
- keep notes and warnings where possible
- adapt the output to be comfortable as a Python docstring
- postpone support for alternative styles such as Google-style or NumPy-style docstrings until later

The intended flow is:

1. parse the raw source comment into `cpp.comment`
2. derive a structured `CppDoc` into `cpp.doc`
3. translate `cpp.doc` into a default `PyDoc`
4. store that result in `py.doc`, unless the user already provided a custom value and overwrite was not requested
5. allow users to customize `py.doc` before emission

This separation keeps all three useful representations:

- exact original comment text
- structured C++-side interpretation
- final Python-facing documentation

Function and method signatures should be treated as optional rendered documentation extras rather than as part of the core stored doc text.

This means:

- the model should know enough to render C++ signatures from the `cpp` facet
- later stages may also know enough to render the final Python signature after adaptation
- emitter or generation configuration should optionally allow adding the C++ signature to the emitted Python documentation
- this should remain optional, because some users will want it and others will prefer cleaner docstrings

Source locations should at least contain:

- file path
- line
- column

For declarations that may be seen multiple times across headers, one plain location is not enough. The model should therefore preserve source provenance in a small container, for example `CppLocationInfo`, with explicit fields such as:

- `primary`: the parser-chosen main location for the semantic element
- `declarations`: all declaration locations seen in active headers
- `definition`: the definition location, if one was seen in headers

The important rule is that source provenance should be explicit. The parser should not encode semantic meaning by saying "the first location in a list is canonical". Instead, it should record one primary location deliberately by policy, such as definition-first when available, and preserve the other declaration sites separately.

This provenance separation is important because parse facts and emission layout policy are related but not identical. Later emitter configuration may choose to group generated bindings by a resolved header anchor, but that grouping decision should not be hidden inside raw source-location ordering.

This supports:

- documentation emission
- diagnostics
- user-facing warnings
- later tooling such as jumping back to the original source

### Typed element set

The initial node set should cover the declarations that matter most for binding generation:

- module
- namespace
- class / struct
- enum / enumerator
- function
- method
- constructor
- field
- template declarations
- template instances

It is acceptable to postpone more specialized node kinds until needed, but the structure should be ready for them.

Overloaded functions and methods should preserve declaration order. This matters because downstream binding backends such as nanobind resolve overloads in registration order, so the model should not treat overload groups as unordered sets.

Examples of later additions:

- first-class alias declarations if they become necessary for binding policy
- template aliases
- operators as special function forms
- properties synthesized from getter/setter pairs
- friend declarations if they become relevant

### Templates

Template families, template declarations, and template instances should be modeled separately.

This is important because binding decisions may differ greatly between instances of the same template.

For example:

- `Vector<T>` is one class template declaration
- `Vector<int>` is one chosen bound instance
- `Vector<bool>` is another chosen bound instance

The instance may need:

- a different Python name
- different return value policy defaults
- different exposure choices
- custom hooks or special-case logic

Therefore:

- each template family should be represented by a wrapper node such as `CppClassTemplate` or `CppFunctionTemplate`
- the wrapper should expose `.declaration`, `.instances`, and `.defaults`
- `.declaration` should hold the generic parsed template declaration only
- parser-discovered instantiations should be recorded on the declaration side via `declaration.cpp.observed_instances`
- template instances should be first-class nodes in the model
- instances should have their own `.cpp`, `.bind`, `.py`, and `.defaults`
- template-family `.defaults.instance` should apply to the selected instances themselves, while the other default buckets should apply to descendants inside those instances
- the template-family wrapper should own both the generic declaration and the selected instance nodes in the model tree, while remaining transparent for C++ qualified-name purposes

The same principle should apply to function templates.

The template selection workflow should distinguish between:

- observed instances found during parsing
- chosen instances that will actually be bound

Observed instances should remain parser facts on the declaration side via `declaration.cpp.observed_instances`.
Here, "observed" means concrete instantiations seen somewhere in the parsed C++ codebase, not instances inferred from binding configuration alone.
Chosen instances should be materialized later as real `CppClassTemplateInstance` or `CppFunctionTemplateInstance` nodes attached to the template-family wrapper.

A helper such as `add_observed_template_instances(...)` should support materializing those parser-observed C++ instances recursively within a chosen subtree, for example a whole module, one namespace, one class, or one specific template family.

This means the binding pipeline answers two separate questions:

- what templates exist in C++?
- which concrete instances do we actually bind?

### Example customization style

The intended Python API should read naturally from one object graph.

Examples:

```python
ns.defaults.function.return_value_policy = "reference_internal"
cls.bind.active = False
cls.defaults.method.keep_alive = (1, 0)
func.py.name = "to_string"
vector_bool.py.name = "BoolVector"
vector_bool.bind.holder_type = "std::shared_ptr<VectorBool>"
```

Users should not need to jump between a parsed tree and a disconnected binding overlay tree for ordinary customization.

Typical customization order should be:

1. customize `.bind`
2. optionally customize `.py` early
3. run translation to fill missing `.py` values
4. customize `.py` further if needed

### Suggested package layout

The semantic model should live in a `model/` package and be split by concern rather than in one large file.

Possible first layout:

- `model/element.py`
- `model/location.py`
- `model/comment.py`
- `model/alias.py`
- `model/type.py`
- `model/operator_.py`
- `model/module.py`
- `model/namespace.py`
- `model/class_.py`
- `model/function.py`
- `model/class_template.py`
- `model/function_template.py`
- `model/member.py`
- `model/enum.py`
- `model/template_.py`

The exact split can evolve, but the main idea is:

- shared infrastructure in a few base files
- declaration kinds in their own files
- bind, Python, and defaults facets colocated with the declaration kinds they belong to

### Recommended pipeline

The intended long-term pipeline is:

1. discover project headers
2. select active headers
3. parse active headers with clang
4. build the semantic declaration tree with `.cpp` filled and `.bind` plus `.py` default-constructed
5. let users customize `.bind`, `.py`, and `.defaults`
6. translate the model to fill missing `.py` values from `.cpp` and `.bind`, unless overwrite is requested
7. let users further customize `.py` if desired
8. resolve effective settings by inheritance
9. emit nanobind or pybind11 code

The semantic model is the main handoff object between parsing, customization, and emission.

### What not to do

Avoid these extremes:

- a completely flat list of declarations without ownership and scope
- a raw syntax tree that mirrors every source construct
- a design where every node carries every possible binding field directly
- a design where users must constantly hop between disconnected parsed and binding trees

The desired middle ground is:

- one semantic declaration tree
- multiple clear facets per node
- typed inherited defaults
- separate template instances
- a Python-discoverable customization surface

## Exemplary C++ code

The C++20 code in `example` should be a small self-contained dummy library named `cosmos`. The name is intentional: it should gradually grow into the "universe" of declarations and binding situations that Oroboros can handle.

The framing may stay playful and mythology-themed, as long as the technical purpose of each declaration remains clear. This means:

- file and type names may use a Greek-mythology-inspired theme such as deities, mortals, oracles, relics, pantheons, omens, and constellations
- the example should still remain technically readable and obviously organized by binding feature
- comments should continue to explain which C++ or binding capability a given header is meant to exercise

In practice, this can look like:

- `Mortal`, `Deity`, `Oracle`, and `Demigod` as class examples
- `Realm` and `OmenKind` as enum examples
- `Demigod : Mortal, Deity` as a multiple-inheritance example
- themed headers such as `deities.hpp`, `omens.hpp`, `artifacts.hpp`, or later `callbacks.hpp` and `operators.hpp`

The example library should grow in layers rather than trying to cover everything at once:

- `basics`: declarations that match the current parser and core model, such as namespaces, enums, free functions, classes, constructors, methods, fields, and parameters
- `advanced`: richer C++ shapes such as aliases, comments, templates, and more subtle declaration relationships
- `nanobind` or backend-focused fixtures: later examples adapted from relevant backend features, such as operators, callbacks, ownership/lifetime, STL handling, and other binding-specific patterns

The current parser-first example should therefore stay intentionally modest and align with what Oroboros can already materialize into the semantic model. As parser and emitter support expands, `cosmos` can be extended with more themed declarations in parallel.

The project notes and fixtures should be kept in sync with the actual implementation. In practice, this means periodically checking and updating together:

- `AGENTS.md`
- `TODO.md`
- the lightweight docs in `docs/`
- the unit tests
- the `example/` library and its parser/generator flow

This should be treated as a regular maintenance checkpoint rather than something to re-scan mechanically after every tiny change. When a feature, API, parser capability, or workflow meaningfully changes, take a moment to confirm that these companion files and fixtures still describe and exercise the current reality.

## Reference sources

The `reference/` directory contains local copies of relevant projects:

- `reference/genesis/`: exemplary target C++ library. Copy of the lczech/genesis repository.
- `reference/binder/`: existing Clang/LibTooling-based binding generator to learn from but not copy structurally.
- `reference/litgen/`: existing Python/srcmlcpp-based generator to study for comment handling and emitter design.
- `reference/litgen_template/`: existing template for litgen code generation, as an example.
- `reference/pybind11/`: binding backend reference.
- `reference/nanobind/`: preferred binding backend reference.
- `reference/*.pdf`: documentation of the existing tools.
