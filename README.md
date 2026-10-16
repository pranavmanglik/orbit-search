# Orbit Search

`orbit-search` defines a provider-neutral asynchronous search contract. It validates bounded text
queries, explicit field paths, scalar exact-match filters, opaque pagination cursors, finite result
scores, and size-limited JSON documents. It does not contain an Elasticsearch/OpenSearch client or
claim a provider integration.

Install the capability package:

```bash
python -m pip install orbit-search
```

Provider adapters implement `SearchStore` and own SDKs, credentials, configuration, transport,
resource lifecycle, and provider error mapping. They should translate the portable query fields
with parameterized provider APIs and document differences in ranking, consistency, and pagination.
No provider DSL, query syntax, automatic retry, or close method is imposed on the shared contract.

```python
from orbit_search import SearchQuery, SearchStore


async def find_articles(store: SearchStore):
    query = SearchQuery(
        text="async cancellation",
        fields=("title", "body"),
        filters={"visibility": "public"},
        page_size=25,
    )
    return await store.search("articles", query)
```

The input models reject provider query languages and bound page size to 100 and source documents to
1 MiB. Result payloads are detached and immutable; `model_dump()` returns JSON-compatible copies.
`SearchOperationError` provides a bounded public message and explicit retry hint. Adapters must not
place credentials, provider response bodies, or raw SDK exception text in those messages.

This package is in alpha and is not a published or stable release. It supports Python 3.11 through
3.14.

## Documentation

The package-specific guides cover [architecture](docs/architecture/overview.md), [operations and security](docs/operations/README.md), and [development](docs/development/README.md), with [security guidance](docs/security/overview.md). The [documentation index](docs/README.md) links to the full package overview and project policies.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
ruff check src tests
mypy
```

Licensed under Apache-2.0.

