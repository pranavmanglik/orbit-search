# Orbit Search: development

This package declares Python `>=3.11,<3.15` support. A declared interpreter range is not evidence
that each version has passed hosted CI.

## Local checks

From this repository root:

```bash
python -m pip install -e '.[dev]'
pytest
ruff check src tests
ruff format --check src tests
mypy
```

The contract test suite is self-contained and does not require Core or a search service. Provider
adapter repositories should add integration tests against their own supported service versions and
keep credentials and service endpoints out of committed test configuration.

## Contract changes

Keep query values provider-neutral and bounded. Add validation tests for invalid types, boundary
values, nested payload limits, serialization, and safe error messages when changing public models.
Document changes to query semantics, cursor behavior, result immutability, dependency keys, or limits
in the README and the relevant architecture and operations guides. Avoid promising ranking,
consistency, retry, lifecycle, or security guarantees that the protocol does not define.

Run the repository documentation validator from the Orbit Core checkout when available. Report the
exact interpreter and tool versions used; local checks do not certify hosted CI or a release.
