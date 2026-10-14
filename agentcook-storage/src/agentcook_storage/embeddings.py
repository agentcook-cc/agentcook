"""Embedders for :class:`~agentcook_storage.PgVectorMemoryStore`.

:class:`HashingEmbedder` is a dependency-free, deterministic lexical
embedder (feature hashing over word unigrams and CJK character bigrams).
It is *not* a semantic model — synonyms don't match — but it gives
pgvector recall a sensible keyword-overlap ranking with no API key, no
model download and zero cost, which is the right default for local dev,
CI and air-gapped deployments. Swap in a real embedding model (OpenAI
``text-embedding-3-small``, Qwen ``text-embedding-v3``, bge …) via
:class:`OpenAICompatibleEmbedder` when semantic recall matters.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence
from typing import Any

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_CJK_RUN = re.compile(r"[㐀-䶿一-鿿豈-﫿]+")
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have i in is it its of on or that the this to was "
    "were will with you your my me we our".split()
)


def _features(text: str) -> Counter[str]:
    lowered = text.lower()
    feats: Counter[str] = Counter(w for w in _WORD.findall(lowered) if w not in _STOPWORDS)
    for run in _CJK_RUN.findall(text):
        if len(run) == 1:
            feats[run] += 1
        for i in range(len(run) - 1):
            feats[run[i : i + 2]] += 1
    return feats


class HashingEmbedder:
    """Deterministic feature-hashing embedder (signed, log-TF, L2-normalized)."""

    def __init__(self, dim: int = 1536) -> None:
        if dim < 8:
            raise ValueError("dim must be >= 8")
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feature, count in _features(text).items():
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dim
            sign = 1.0 if (value >> 63) & 1 else -1.0
            vec[index] += sign * (1.0 + math.log(count))
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            return vec
        return [v / norm for v in vec]

    async def __call__(self, text: str) -> Sequence[float]:
        return self.embed(text)


class OpenAICompatibleEmbedder:
    """Embeddings via any OpenAI-compatible ``/embeddings`` endpoint.

    Args:
        client: An ``openai.AsyncOpenAI`` (or compatible) client.
        model: Embedding model name.
        dimensions: Requested output size (must match the pgvector column).
    """

    def __init__(self, client: Any, *, model: str, dimensions: int | None = 1536) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions

    async def __call__(self, text: str) -> Sequence[float]:
        kwargs: dict[str, Any] = {"model": self._model, "input": text}
        if self._dimensions:
            kwargs["dimensions"] = self._dimensions
        response = await self._client.embeddings.create(**kwargs)
        return list(response.data[0].embedding)


__all__ = ["HashingEmbedder", "OpenAICompatibleEmbedder"]
