# Project: CPP to Python Binding Generator

This project develops a Python-based C++ to Python binding generator for C++ libraries.

## Goal

Generate nanobind and pybind11 bindings from C++ headers.

## Overall architecture

- Keep parser logic, policy logic, configuration, and emitter logic separate.
- Use libclang / clang.cindex as the semantic source of truth.
- Extract namespaces, classes, structs, enums, functions, constructors, methods, fields, base classes, and comments.
- Build an intermediate representation (IR) before emitting bindings.
- Allow full customization in the IR, such as return value policies, removal and addition of functions, etc.
- Respect the C++ header dependency order to ensure compilation will work.
- Preserve Doxygen-style comments from C++ declarations where possible.
- Emitter should target nanobind and pybind11.
- Implement nanobind first, but keep the emitter split clean so pybind11 can be added later without redesigning the pipeline.

## Specific design direction, to be worked on bit by bit

I want to use the final product as follows:

- In my C++ library (genesis, as an example, see the references), I will have a script `genesis/python/generate.py`, which will utilize this library here (Ouroboros) to generate bindings code for genesis, targeting nanobind.
- When executed, the script will scan the library headers (in `genesis/lib`), and build the IR from that. Further, it will take a set of configurations and customizations (as python and c++ code, also in `genesis/python`), defining how to build the IR, and customize it.
- Configuration should be Python-only. Users should not need to learn an ad-hoc configuration language, and the API should ideally be discoverable from interactive Python sessions.
- Configuration: Take an "all include" C++ header as one input, which defines the C++ headers and their dependency order.
- Separately, support an "activated headers" list that decides which headers are currently included in binding generation. This can be another C++ include header with commented and uncommented includes, or an equivalent Python-readable representation if that turns out cleaner.
- Only active headers shall be parsed for binding generation. If any include in the activation list is commented out, Ouroboros shall ignore it and not generate bindings for code in that header.
- If any known library header is missing from the activation list entirely, a warning should be emitted.
- Instead of binding everything at once, allow incrementally adding headers from this list of activated headers. This allows to build the bindings step by step, instead of having to deal with many errors at once.
- Then, the `generate.py` script will build the IR for those active headers, amended by extra configuration, such as excluding certain functions, classes, and class members, return value policies, copy and other operators (translate to dunder methods where possible), converting iterations, and all the nice things that pybind and nanobind offer - fully configurable via the IR for each class and function.
- This shall also allow to add new bindings, such as extra functions or class members. These should ideally be written as add-ons in CPP that will be compiled with the generated bindings, using the `def` function of pybind/nanobind to add function definitions to a to-be-bound class for instance. These customizations are provided in `genesis/python/custom` as needed.
- Custom add-ons should preferably work as external C++ hook files, similar to the current Binder approach, but IR-level customization should also allow providing custom code fragments from Python where useful.
- Also, things like which template instances to create for class and function templates will be decided via configuration per class and function.
- Finally, the script will call the generate() function of Ouroboros, which will generate the bindings code into `genesis/python/bindings`. The files in there are auto-generated, and wil be scanned by the CMake setup, containing the main module for pybind/nanobind, and all bindings code needed.
- The file structure of the auto-generated bindings files shall follow the original header file names and paths, i.e., mirror them, and allow incremental builds. That is, when re-generating a bindings file, before writing it out, it needs to be written to a temp location, and only if content differs with the existing file, will it be overwritten, so that time stamps allow CMake to avoid recompilation.
- Everything should follow namespaces, and fully qualify names, or use the IR to descend into namespaces etc when customizing the bindings.
- Python submodules should mirror the C++ namespaces, while still compiling into a single nanobind extension module.
- It should be configurable whether the top-level C++ namespace becomes the Python module root directly, or whether it is exposed as an explicit first submodule.
- Documentation of all C++ code (Doxygen-style) shall be preserved and added to the generated files (without the leading `*`, and with some Python-style equivalent of the `@` annotations of Doxygen).
- The IR should preserve both the raw C++ comments and a normalized docstring-oriented representation, so documentation can also be customized before emission.
- Python stub files shall be generated in `genesis/python/stubs`, either as a single file or set of files.
- Generate test cases for the bindings, that hit every class and funtion, to show that the binding worked. This should also allow to use existing C++ test (e.g., gtest) as guidance, and replicate them in Python. But mostly, tests on the Python end should focus on the binding interface, to ensure that is working correctly. We can mostly assume that that internal functionality of the C++ side is already tested there.

The goal of Ouroboros is to allow creating bindings this way. It thus needs to provide all the mentioned functionality, which will then be called and used from genesis. Note that genesis is only inteded to be used as the exemplary library that motivates the development of Ouroboros. Its name or paths or anything should never be mentioned in Ourobors itself, and everything should be configurable instead. Genesis itself will then use Ouroboros functionality to make its bindings. Ideally, genesis will only need to set up the configuration, call the function to parse the headers, then add its customization as needed on top, using the IR, and then call the function to write out the generated code. All the rest shall be handled by Ouroboros here. If any of the concepts or configurations are too specific for genesis alone, where it makes sense, it should be implemented in a more generic way as well, so that other libraries will be able to use this project as well.

As this is a lot of functionality, we will build the Ouroboros code incrementally, and test it in parallel in genesis.

## Coding style

- Python 3.12+.
- Use dataclasses or pydantic-style models for the IR.
- Keep functions small and testable.
- Add short comments for each function and class to state their purpose.
- Add short (one or two line) comments for code blocks, explaining their intend (e.g., what does the loop do?).
- Avoid hard-coding Genesis-specific behavior in the parser core; put policy in configuration instead.

## Current decisions

- Implement nanobind first.
- Keep the backend emitter split clean so pybind11 can be added later.
- Use Python-only configuration APIs.
- Keep header dependency order and header activation as separate inputs.
- Prefer external C++ add-on hooks for custom bindings, while still allowing Python-driven IR customization.
- Mirror C++ namespaces as Python submodules within a single compiled extension module.
- Make the handling of the top-level namespace configurable.
- Preserve both raw and normalized documentation in the IR.
- Defer stub generation and binding-test generation until after the basic parser, IR, and emitter pipeline works, but design the system so those later stages fit naturally.

## Exemplary C++ code

The C++20 code to be created in `example` should be a small self contained dummy library, showing all relevant functionality that can potentially receive bindings via pybind/nanobind: Namespaces, enums, functions, classes, inheritance, etc.

## Reference sources

The `reference/` directory contains local copies of relevant projects:

- `reference/genesis/`: exemplary target C++ library. Copy of the lczech/genesis repository.
- `reference/binder/`: existing Clang/LibTooling-based binding generator to learn from but not copy structurally.
- `reference/litgen/`: existing Python/srcmlcpp-based generator to study for comment handling and emitter design.
- `reference/litgen_template/`: existing template for litgen code generation, as an example.
- `reference/pybind11/`: binding backend reference.
- `reference/nanobind/`: preferred binding backend reference.
- `reference/*.pdf`: documentation of the existing tools.
