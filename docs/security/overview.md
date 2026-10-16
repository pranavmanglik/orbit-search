# Orbit Search: security

This package validates and bounds search inputs and result documents. It does not authenticate
callers, authorize collections, apply tenant isolation, encrypt transport, or protect a provider
endpoint. Those controls belong to the application and the selected provider adapter.

## Application and provider responsibilities

- Derive tenant and authorization filters from trusted identity or server-side policy. Do not accept
  a client-supplied tenant filter as proof of access.
- Enforce collection-level authorization before calling `SearchStore.search`.
- Give provider credentials only the index and actions required by the application. Keep credentials
  in a secret manager and rotate them according to the provider's policy.
- Use TLS with certificate verification for remote providers and apply network restrictions where
  appropriate.
- Configure provider timeouts and concurrency bounds so slow queries cannot exhaust application
  resources.

## Data handling

Search text, filters, cursors, identifiers, scores, and document source may contain sensitive data.
Avoid logging full queries, opaque cursors, result documents, provider responses, or credentials.
Prefer request IDs and bounded error categories for operational logs. `SearchOperationError` accepts
only a bounded printable message; adapters must not pass raw SDK exception text into it.

The contract rejects provider DSL, control characters in query text and cursors, non-finite numeric
values, unsupported source values, and oversized or deeply nested documents. These are input and
resource bounds, not a defense against every provider-specific injection or authorization flaw.
Adapters must use provider APIs that bind or safely encode query values.

## Disclosure

Follow the repository [security policy](../../SECURITY.md) for vulnerability reporting. Do not post
unfixed vulnerability details in public issues.
