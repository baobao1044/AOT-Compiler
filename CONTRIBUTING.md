# Contributing to AOTC

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pre-commit install
```

## Local checks

```bash
pytest -q
python -m aotc.cli build examples/array_sum.py --emit ll --opt O3 --passes cf,dce,inline
python -m aotc.cli bench --loop-count 100000 --repeats 1 --threads 4 --opt O3
```

## Code style
- Keep changes focused and tested.
- Prefer explicit IR semantics over magic lowering steps.
- Add tests for parser/control-flow/optimizer behavior changes.

## Pull requests
- Include problem statement and behavior changes.
- Include benchmark delta when touching optimizer or codegen.
- Ensure CI is green on Linux, macOS, and Windows matrix.
