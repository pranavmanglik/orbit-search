# Orbit Search: operations

`orbit-search` contains contracts and bounded data models only. It does not open network connections,
manage a client pool, or provide an Elasticsearch, OpenSearch, or other search backend. Install a
provider adapter separately and follow that adapter's connection, timeout, credential, and shutdown
instructions.

## Query behavior

Every `SearchQuery` has nonblank text, at least one explicit field, optional exact-match scalar
filters, a page size from 1 through 100, and an optional opaque cursor. Provider adapters translate
these values into their provider's parameterized query API. Provider query DSL is intentionally not
accepted by the shared contract.

`SearchPage` contains at most 100 `SearchHit` values, a nonnegative `took_ms`, and an optional
continuation cursor. Cursors are provider-specific opaque tokens: pass them back only to the same
adapter and compatible query, and do not parse, construct, or assume they remain valid after provider
configuration or index changes. Provider ranking and score scales are not normalized by Orbit.

The contract does not impose retries or expose a close method. Configure connection and request
timeouts, safe retry rules, concurrency limits, and client shutdown using the selected provider
adapter. Cancellation should reach the provider request. `SearchOperationError.retryable` is an
adapter's explicit hint; it is not a promise that retrying is safe or will succeed.

## Resource and payload bounds

Queries limit text to 2,048 characters, fields and filters to 64 entries each, cursor text to 4,096
characters, and page size to 100. A source document is limited to 1 MiB, 16 nesting levels, 10,000
values, and 1,000 object keys at each level. Search result payloads are copied and frozen before they
are returned; `model_dump()` produces detached JSON-compatible values.

Collection names are portable identifiers of at most 255 characters. Field paths are explicit dotted
identifiers. These checks prevent provider syntax from being smuggled through this contract; they do
not replace provider authorization or application validation.

## Deployment checks

Before release, verify the chosen provider's supported version, TLS configuration, least-privilege
permissions, client lifecycle, request timeouts, cancellation behavior, query translation, paging
consistency, and behavior during provider outages. Exercise realistic document size and result volume.
Test backup, restore, and index lifecycle through the provider-specific tooling where required.

This package's local contract tests use no search service. Passing them does not validate a live
provider, a production topology, or hosted CI.
