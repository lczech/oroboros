# Project: C++ To Python Binding Generator

Oroboros builds nanobind first, and later pybind11, from C++ headers.

## Goal

Generate bindings from C++ headers through a staged pipeline:

1. `parse`: build a semantic C++ model from libclang into `.cpp` facets
2. `modify`: the user can modify and customize the model as needed
3. `emit`: generate backend-specific binding code, using `.bind` and `.py` facets

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

## Run tests

Always run the tests after code changes:

```
micromamba activate oroboros
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Current Architectural Decisions

- Keep the backend split clean so pybind11 can be added later
- Clang sees transitive includes normally, but Oroboros only materializes declarations from active project headers
- Keep one semantic node per semantic entity; repeated declarations enrich it

## Semantic Model

### Facets

Most semantic elements expose:

- `.cpp`: parsed C++ facts, read-mostly
- `.bind`: binding-generation policy for that element
- `.py`: Python-facing exposure choices
- `.defaults`: inherited defaults for descendants

## Binding Model Guidelines

For external, STL, and framework-provided types, Oroboros should support a
layered policy system with both type-specificity and declaration-scope
precedence.

This should allow one stable default for a type family, more specific defaults
for particular instantiations, and explicit local overrides where a particular
API wants a different Python-facing representation.

Activation/deactivation belongs to the binding layer:

- headers decide what enters the model at all
- `.bind.active` decides what remains bindable within that model

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
