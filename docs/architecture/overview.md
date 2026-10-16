# Orbit Search: architecture

## Package boundary

`orbit-search` owns the portable Python contract and immutable query/result values. Provider
integrations are separate packages that implement `SearchStore`; each integration owns its provider
SDK, credentials, connection configuration, lifecycle, and provider-specific error translation.
Applications depend on this capability contract and select the provider adapter separately.

```text
application service
       │ SearchStore
       ▼
 orbit-search ───── provider adapter ───── provider SDK/service
```

The capability has no required Core dependency. `SEARCH_STORE_DEPENDENCY_KEY` is available for Core
applications that choose to register an implementation in dependency injection; ordinary code can
pass a `SearchStore` directly. The capability package does not register routes, create a database
client, or manage application lifecycle.

## Portable query model

`SearchQuery` represents full-text input, explicit dotted field paths, exact-match scalar filters,
page size, and an optional opaque cursor. It deliberately excludes provider query languages and
does not standardize relevance, stemming, fuzzy matching, sort order, or consistency. Adapters
translate these values through safe provider APIs and document any provider-specific behavior.

`SearchHit` holds a provider-neutral ID, finite provider-defined score, and JSON source object.
`SearchPage` groups results and the continuation cursor. These Pydantic models are frozen; nested
filters and source values are copied into immutable containers, and `model_dump()` returns detached
JSON-compatible data.

## Failure and lifecycle contract

`SearchOperationError` bounds its public message and carries an explicit `retryable` hint.
`SearchIndexNotFound` identifies a missing collection. Adapters should normalize expected provider
failures without including raw SDK messages, response bodies, or credentials. Unexpected programming
errors should not be mislabeled as transient failures.

`SearchStore` defines only `search`. It has no implicit retry, timeout, client lifecycle, or close
semantics. Those choices vary by provider and remain in the adapter contract and its documentation.
Cancellation should propagate to the provider request.

## Implemented modules

- `src/orbit_search/contracts.py`: dependency key, collection-name validation, bounded Pydantic
  values, normalized errors, and the asynchronous protocol.
- `src/orbit_search/__init__.py`: public exports.

The capability tests verify value validation, immutable data, serialization, and protocol shape
without connecting to a search service. Provider integration and production topology checks belong
to adapter repositories.
