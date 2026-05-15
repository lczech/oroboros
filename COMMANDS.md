# Commands

Useful commands for developing and testing Oroboros.

## Run the CLI from the source tree

List all headers in a directory:

```bash
PYTHONPATH=src python3 -m oroboros find-headers --header-dir example/inc
```

List headers included from a root header in include order:

```bash
PYTHONPATH=src python3 -m oroboros find-headers --header-dir example/inc --header-file example/inc/cosmos/cosmos.hpp
```

```bash
PYTHONPATH=src python3 -m oroboros find-headers --header-dir ../genesis/lib/ --header-file ../genesis/lib/genesis/genesis.hpp
```

Run the bundled example script and update `example/python/active_headers.hpp`:

```bash
PYTHONPATH=src python3 example/python/generate.py
```

## Run the installed CLI

After installing the package, the project-wide command is:

```bash
oroboros find-headers --header-dir example/inc --header-file example/inc/cosmos/cosmos.hpp
```

## Run tests

Run the current header-discovery tests:

```bash
PYTHONPATH=src python3 -m unittest tests.test_find_headers tests.test_main
```

Run all unittest-based tests in the repository:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
