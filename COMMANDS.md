# Commands

Useful commands for developing and testing Oroboros.

## Set up the local clang environment

Create the micromamba environment from the checked-in conda file:

```bash
micromamba env create -f environment.yml
```

Activate it:

```bash
micromamba activate oroboros
```

Or run commands inside it without activation:

```bash
micromamba run -n oroboros python -V
```

If `micromamba` cannot write to its default cache directory, use a writable cache path explicitly:

```bash
XDG_CACHE_HOME=/tmp/micromamba-cache \
MAMBA_ROOT_PREFIX=/home/lucas/Software/micromamba-envs \
micromamba run -n oroboros python -V
```

Install the local repository in editable mode inside that environment:

```bash
python -m pip install -e .
```

Verify that the clang Python bindings are available:

```bash
python - <<'PY'
from clang import cindex
index = cindex.Index.create()
print("clang python bindings ok")
print(index)
PY
```

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

Run the parser tests inside the micromamba environment:

```bash
XDG_CACHE_HOME=/tmp/micromamba-cache \
MAMBA_ROOT_PREFIX=/home/lucas/Software/micromamba-envs \
micromamba run -n oroboros python -m unittest tests.test_parse
```

Run all unittest-based tests in the repository:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Run the full test suite inside the micromamba environment:

```bash
XDG_CACHE_HOME=/tmp/micromamba-cache \
MAMBA_ROOT_PREFIX=/home/lucas/Software/micromamba-envs \
micromamba run -n oroboros python -m unittest discover -s tests
```

## Example code

```bash
cd oroboros/example
cmake -B build/ && cmake --build build/
./build/cosmos_app
```
