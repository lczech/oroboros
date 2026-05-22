# Model Navigation

The semantic model is the main working object graph of Oroboros. It is intended
to be pleasant to explore interactively in Python while still preserving C++
structure closely enough for customization and emission.

## Core shape

- `CppModule` owns top-level namespaces and declarations.
- `CppNamespace` owns nested namespaces, classes, functions, variables, enums,
  and template families.
- `CppClass` owns constructors, methods, instance variables, static member
  variables, nested enums, nested classes, and nested template families.
- Functions, methods, and constructors own `CppParameter` objects.
- Enums own `CppEnumerator` objects.

Most direct child collections are still stored as ordered lists so declaration
order is preserved:

- `module.namespaces`
- `namespace.classes`
- `class_.methods`
- `function.parameters`

## Direct-child navigation

For interactive use, scope-like nodes also support direct lookup by name:

```python
module["cosmos"]
module["cosmos"]["beings"]
module["cosmos"]["beings"]["Mortal"]
module["cosmos"]["beings"]["Mortal"]["size"]
```

`scope["name"]` searches only the direct children of that node.

Behavior:

- if exactly one direct child matches, return it
- if several direct children match and they are overloadable declarations such
  as functions, methods, or constructors, return a list
- otherwise raise `ModelLookupError`

This makes chained navigation natural without replacing the underlying ordered
list storage.

## Typed direct-child views

When you know which child kind you want, typed name-indexed views are often
clearer:

```python
module.namespace["cosmos"]
namespace.class_["Widget"]
namespace.function["make_widget"]
namespace.variable["global_count"]
class_.method["size"]
class_.variable["name_"]
class_.static_variable["instance_count"]
function.parameter["value"]
enum_.enumerator["primary"]
```

These views sit on top of the existing lists and do not change the underlying
storage model.

Behavior:

- unique-name collections return one element
- overloadable collections such as functions, methods, constructors, and
  function templates return a list
- missing or ambiguous unique-name lookups raise `ModelLookupError`

## Subtree lookup

For broader search instead of direct-child navigation, the model provides
subtree lookup helpers:

```python
module.find("cosmos::beings::Mortal")
module.find_all("size")
module.find_one_by_name("Widget")
module.find_one_by_qualified_name("cosmos::beings::Mortal")
```

Two convenience helpers are available:

- `find(query)` returns exactly one match
- `find_all(query)` returns all matches

If `query` contains `::`, Oroboros treats it as a qualified name. Otherwise it
is treated as an unqualified name.

## Discovery helpers

For quick inspection in interactive sessions, each scope-like node exposes:

```python
scope.element_names
```

This returns the unique names of all direct child declarations currently owned
by that scope. It is meant as a lightweight discovery aid while exploring a
module tree in a REPL or notebook.

## Type data is embedded, not a tree

`CppType` objects do not participate in the declaration ownership hierarchy.
They live inside `.cpp` facets as embedded value objects:

- function return types
- parameter types
- variable types
- class base types
- enum underlying types
- alias targets

So you navigate declarations through the semantic tree, and inspect type usage
through the `.cpp` data of those declarations.
