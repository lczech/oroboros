# Customization Workflow

Oroboros is meant to build a semantic C++ model first and customize that model
before backend code emission happens.

The long-term high-level stages are:

- `parse`
- `translate`
- `emit`

Only the parse stage is implemented meaningfully so far, but the model is
already shaped to support the later stages.

## Intended lifecycle

The intended user workflow is:

1. choose the active header list
2. parse those headers into a semantic model
3. customize the model
4. translate missing Python-facing values
5. emit nanobind or pybind11 code

In code, that should eventually feel roughly like:

```python
result = parse_headers(active_headers, config)
module = result.module

# Customize the semantic model.
module["cosmos"]["beings"]["Mortal"].bind.active = True
module["cosmos"]["beings"]["Mortal"].method["name"][0].py.name = "name"

# Later:
# translate(module)
# emit(module, emitter_config)
```

## Facets and their roles

Each semantic declaration object is split into facets:

- `.cpp`
  Parsed C++ facts, treated as read-mostly by convention
- `.bind`
  Binding policy and generation settings for this element itself
- `.py`
  Python-facing exposure choices
- `.defaults`
  Inherited descendant defaults for child declarations

This lets users customize one object graph without mixing parser facts and
binding policy into one flat namespace.

## Where changes should go

Rule of thumb:

- if a setting changes binding mechanics, lifetime rules, ownership, or
  whether something is emitted at all, it belongs in `.bind`
- if it changes what Python users see, import, call, or read, it belongs in
  `.py`
- if it is parsed source information, it belongs in `.cpp`
- if it should apply to descendants unless overridden, it belongs in
  `.defaults`

Examples:

- `func.bind.return_value_policy`
- `method.bind.active`
- `class_.py.name`
- `namespace.defaults.function.active`

## Scope-aware customization

The model is intentionally hierarchical so customization can follow scope:

```python
module.namespace["cosmos"].bind.hooks.append("customize_cosmos")
module.namespace["cosmos"].namespace["beings"].class_["Mortal"].bind.active = True
```

Or with the generic direct-child API:

```python
module["cosmos"]["beings"]["Mortal"].bind.active = True
```

## Discovery in interactive sessions

The model is meant to be explorable in a REPL or notebook:

- use `scope.element_names` to see direct child names
- use `scope["name"]` to walk direct children
- use typed views like `scope.class_["Widget"]`
- use `scope.find(...)` when you want subtree search instead

Examples:

```python
module.element_names
module["cosmos"].element_names
module.find("cosmos::beings::Mortal")
module.find_all("size")
```

## Important current limitation

The current parser fills `.cpp` and default-constructs the other facets, but
the real translation and emission layers are not implemented yet. So today the
model is already the right customization target, but the later stages still
need to catch up to that design.
