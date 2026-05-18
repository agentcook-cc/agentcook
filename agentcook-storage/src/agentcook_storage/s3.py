"""S3-compatible object store implementing :class:`ObjectStoreProtocol`.

Backed by ``aioboto3``. Works against AWS S3, MinIO, Cloudflare R2,
LocalStack — anything speaking the S3 wire format. The ``endpoint_url``
keyword is the swap point for MinIO / LocalStack.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import aioboto3


class S3ObjectStore:
    """Async object store satisfying :class:`ObjectStoreProtocol`."""

    def __init__(
        self,
        *,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        session: aioboto3.Session | None = None,
    ) -> None:
        try:
            import aioboto3
        except ImportError as exc:
            raise ImportError(
                "Install agentcook-storage[s3] to use S3ObjectStore."
            ) from exc
        self._session = session or aioboto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
        self._client_kwargs: dict[str, Any] = {}
        if endpoint_url is not None:
            self._client_kwargs["endpoint_url"] = endpoint_url

    def _client(self):
        return self._session.client("s3", **self._client_kwargs)

    async def put_object(self, bucket: str, key: str, body: bytes) -> None:
        async with self._client() as s3:
            await s3.put_object(Bucket=bucket, Key=key, Body=body)

    async def get_object(self, bucket: str, key: str) -> bytes:
        async with self._client() as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            async with response["Body"] as stream:
                return await stream.read()

    async def delete_object(self, bucket: str, key: str) -> None:
        async with self._client() as s3:
            await s3.delete_object(Bucket=bucket, Key=key)

    async def list_objects(self, bucket: str, prefix: str = "") -> AsyncIterator[str]:
        async with self._client() as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for item in page.get("Contents", []):
                    yield item["Key"]

    async def presigned_url(self, bucket: str, key: str, *, expires_in: int = 3600) -> str:
        async with self._client() as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )


__all__ = ["S3ObjectStore"]
