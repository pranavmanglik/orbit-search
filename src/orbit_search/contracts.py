# Copyright 2026-present Orbit Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Bounded search values and the provider-neutral asynchronous search contract."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_serializer,
    field_validator,
)

# Stable Core container key used by applications that register a SearchStore capability.
SEARCH_STORE_DEPENDENCY_KEY = "orbit.search"
_MAX_QUERY_TEXT = 2_048
_MAX_FIELDS = 64
_MAX_FILTERS = 64
_MAX_PAGE_SIZE = 100
_MAX_CURSOR_LENGTH = 4_096
_MAX_DOCUMENT_BYTES = 1_048_576
_MAX_DOCUMENT_DEPTH = 16
_MAX_DOCUMENT_NODES = 10_000
_MAX_OBJECT_FIELDS = 1_000
_MAX_TEXT_VALUE = 65_536
_FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*)*$")
_COLLECTION_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$")
_FilterValue = str | int | float | bool | None


def validate_collection_name(value: str) -> str:
    """Validate a portable collection/index alias without accepting provider query syntax."""
    if not isinstance(value, str) or _COLLECTION_NAME.fullmatch(value) is None:
        raise ValueError("Collection names must be 1–255 portable identifier characters.")
    if value in {".", ".."}:
        raise ValueError("Collection names cannot be relative path markers.")
    return value


def _contains_control(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _copy_document(value: object, *, depth: int, nodes: list[int]) -> object:
    """Copy and freeze a bounded JSON value while rejecting custom objects and cycles."""
    nodes[0] += 1
    if nodes[0] > _MAX_DOCUMENT_NODES:
        raise ValueError("Search documents exceed the maximum value count.")
    if depth > _MAX_DOCUMENT_DEPTH:
        raise ValueError("Search documents exceed the maximum nesting depth.")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        if len(value) > _MAX_TEXT_VALUE:
            raise ValueError("Search document text values exceed the maximum length.")
        return value
    if isinstance(value, int):
        if not -(2**63) <= value < 2**63:
            raise ValueError("Search document integers must fit a signed 64-bit value.")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Search document numbers must be finite.")
        return value
    if isinstance(value, Mapping):
        if len(value) > _MAX_OBJECT_FIELDS:
            raise ValueError("Search document objects exceed the maximum field count.")
        copied: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 256 or _contains_control(key):
                raise ValueError("Search document keys must be bounded printable strings.")
            copied[key] = _copy_document(item, depth=depth + 1, nodes=nodes)
        return MappingProxyType(copied)
    if isinstance(value, (list, tuple)):
        if len(value) > _MAX_DOCUMENT_NODES:
            raise ValueError("Search document arrays exceed the maximum value count.")
        return tuple(_copy_document(item, depth=depth + 1, nodes=nodes) for item in value)
    raise ValueError("Search documents may contain only JSON-compatible values.")


def _thaw_document(value: object) -> object:
    """Convert immutable document values to ordinary JSON containers for serialization."""
    if isinstance(value, Mapping):
        return {key: _thaw_document(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_document(item) for item in value]
    return value


class SearchQuery(BaseModel):
    """Bounded full-text query with exact-match scalar filters and opaque pagination cursor.

    The contract deliberately excludes provider-specific query DSL. Adapters must translate the
    text, selected fields, exact filters, and cursor using parameterized provider APIs. The caller
    chooses the fields to search and return; the contract does not define ranking, tenant isolation,
    stemming, fuzzy matching, or provider-side defaults. Cursors are opaque and only meaningful to
    the adapter that produced them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, hide_input_in_errors=True)

    text: StrictStr = Field(min_length=1, max_length=_MAX_QUERY_TEXT)
    fields: tuple[StrictStr, ...] = Field(min_length=1, max_length=_MAX_FIELDS)
    filters: Mapping[StrictStr, _FilterValue] = Field(default_factory=dict)
    page_size: StrictInt = Field(default=20, ge=1, le=_MAX_PAGE_SIZE)
    cursor: StrictStr | None = Field(default=None, max_length=_MAX_CURSOR_LENGTH)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject blank/control-only queries while preserving user query whitespace."""
        if not value.strip() or _contains_control(value):
            raise ValueError("Search text must be nonblank and contain no control characters.")
        return value

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Require explicit, unique portable field paths and bound their total text size."""
        if len(values) != len(set(values)):
            raise ValueError("Search fields must be unique.")
        if sum(len(value) for value in values) > _MAX_QUERY_TEXT:
            raise ValueError("Search field paths exceed the maximum aggregate length.")
        if any(_FIELD_NAME.fullmatch(value) is None for value in values):
            raise ValueError("Search fields must be portable dotted identifiers.")
        return values

    @field_validator("filters", mode="before")
    @classmethod
    def validate_filters(cls, value: object) -> Mapping[str, _FilterValue]:
        """Copy and freeze a bounded set of scalar exact-match predicates."""
        if not isinstance(value, Mapping) or len(value) > _MAX_FILTERS:
            raise ValueError("Search filters must be a mapping with at most 64 entries.")
        copied: dict[str, _FilterValue] = {}
        for key, item in value.items():
            if not isinstance(key, str) or _FIELD_NAME.fullmatch(key) is None:
                raise ValueError("Search filter names must be portable dotted identifiers.")
            if isinstance(item, str):
                if len(item) > _MAX_TEXT_VALUE:
                    raise ValueError("Search filter text exceeds the maximum length.")
            elif isinstance(item, float) and not math.isfinite(item):
                raise ValueError("Search filter numbers must be finite.")
            elif item is not None and not isinstance(item, (bool, int, float)):
                raise ValueError("Search filters support only scalar JSON values.")
            if (
                isinstance(item, int)
                and not isinstance(item, bool)
                and not -(2**63) <= item < 2**63
            ):
                raise ValueError("Search filter integers must fit a signed 64-bit value.")
            copied[key] = item
        return MappingProxyType(copied)

    @field_validator("cursor")
    @classmethod
    def validate_cursor(cls, value: str | None) -> str | None:
        """Treat cursors as bounded opaque tokens and reject header/log injection controls."""
        if value is not None and _contains_control(value):
            raise ValueError("Search cursors cannot contain control characters.")
        return value

    def model_post_init(self, __context: object) -> None:
        """Freeze validated filters after Pydantic has normalized the mapping field."""
        object.__setattr__(self, "filters", MappingProxyType(dict(self.filters)))

    @field_serializer("filters")
    def serialize_filters(self, value: Mapping[str, _FilterValue]) -> dict[str, _FilterValue]:
        """Serialize a detached ordinary mapping rather than exposing the read-only proxy."""
        return dict(value)


class SearchHit(BaseModel):
    """One immutable result with provider-neutral identifier, finite score, and JSON source.

    ``score`` is provider-defined and should only be compared within results from the same backend
    and query. ``source`` is a detached, recursively immutable JSON object; use ``model_dump()`` to
    obtain ordinary JSON-compatible containers.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, hide_input_in_errors=True)

    id: StrictStr = Field(min_length=1, max_length=512)
    score: StrictFloat
    source: Mapping[StrictStr, object]

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Reject blank or control-bearing backend identifiers before application use."""
        if not value.strip() or _contains_control(value):
            raise ValueError("Search hit IDs must be nonblank printable text.")
        return value

    @field_validator("score")
    @classmethod
    def validate_score(cls, value: float) -> float:
        """Reject non-finite scores that cannot be reliably ordered or serialized."""
        if not math.isfinite(value):
            raise ValueError("Search hit scores must be finite numbers.")
        return value

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, value: object) -> Mapping[str, object]:
        """Detach, size-limit, and recursively freeze the provider document payload."""
        if not isinstance(value, Mapping):
            raise ValueError("Search hit sources must be JSON objects.")
        copied = _copy_document(value, depth=0, nodes=[0])
        assert isinstance(copied, Mapping)
        encoded = json.dumps(_thaw_document(copied), ensure_ascii=False, allow_nan=False).encode(
            "utf-8"
        )
        if len(encoded) > _MAX_DOCUMENT_BYTES:
            raise ValueError("Search hit sources exceed the 1 MiB safety limit.")
        return copied

    def model_post_init(self, __context: object) -> None:
        """Freeze normalized Pydantic output to protect nested search result data."""
        frozen = _copy_document(self.source, depth=0, nodes=[0])
        assert isinstance(frozen, Mapping)
        object.__setattr__(self, "source", frozen)

    @field_serializer("source")
    def serialize_source(self, value: Mapping[str, object]) -> object:
        """Return detached JSON-compatible data for model serialization."""
        return _thaw_document(value)


class SearchPage(BaseModel):
    """One bounded page of results and its opaque continuation cursor, if any.

    Adapters return at most the requested page size and provide ``next_cursor`` only when another
    page is available. ``took_ms`` is the provider-reported elapsed duration for this operation; it
    excludes application-side processing and transport time unless the adapter documents otherwise.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, hide_input_in_errors=True)

    hits: tuple[SearchHit, ...] = Field(max_length=_MAX_PAGE_SIZE)
    next_cursor: StrictStr | None = Field(default=None, max_length=_MAX_CURSOR_LENGTH)
    took_ms: StrictInt = Field(ge=0)

    @field_validator("next_cursor")
    @classmethod
    def validate_next_cursor(cls, value: str | None) -> str | None:
        """Reject provider pagination tokens with control characters."""
        if value is not None and _contains_control(value):
            raise ValueError("Search cursors cannot contain control characters.")
        return value


class SearchOperationError(Exception):
    """Safe provider-neutral operation failure with a bounded retry hint."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        """Create an actionable public message; adapters must not pass raw vendor exceptions."""
        if (
            not isinstance(message, str)
            or not message
            or len(message) > 256
            or _contains_control(message)
        ):
            raise ValueError("Search errors require bounded printable public messages.")
        if not isinstance(retryable, bool):
            raise TypeError("Search retryable flags must be bool.")
        self.retryable = retryable
        super().__init__(message)


class SearchIndexNotFound(SearchOperationError):
    """Raised when a requested search collection is absent."""


class SearchStore(Protocol):
    """Provider-neutral asynchronous search contract implemented by optional adapters.

    Each adapter owns its client, credentials, transport timeouts, connection lifecycle, and
    provider error mapping. Implementations must validate collection names with
    :func:`validate_collection_name`, preserve the caller's explicit filters, and avoid silently
    widening the query. Cancellation must propagate to the underlying request; adapters must not
    retry automatically unless the provider operation is known to be safe. This protocol has no
    lifecycle method, so applications close provider clients through the adapter's documented API.
    """

    async def search(self, collection: str, query: SearchQuery) -> SearchPage:
        """Search one collection with explicit fields, filters, page size, and optional cursor.

        Raise :class:`SearchIndexNotFound` when the collection is absent and
        :class:`SearchOperationError` for other normalized failures. Do not expose credentials,
        document contents, or raw provider exception text through public errors.
        """
