"""Typed object-store boundary and boto3 S3 adapter."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Protocol, final

from boto3.session import Session
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from smurf_flow.errors import StorageError

if TYPE_CHECKING:
    from collections.abc import Callable

    from types_boto3_s3 import S3Client

    from smurf_flow.models import StorageSettings


@dataclass(frozen=True, slots=True)
class Created:
    """A conditional object creation succeeded."""

    def matches(self, expected: bytes) -> bool:
        """Accept any expected bytes because this call created them."""
        del expected
        return True


@dataclass(frozen=True, slots=True)
class Existing:
    """A conditional object key already exists."""

    payload: bytes

    def matches(self, expected: bytes) -> bool:
        """Report whether immutable existing bytes are idempotent."""
        return self.payload == expected


class CreateResult(Protocol):
    """Outcome capability for create-only object publication."""

    def matches(self, expected: bytes) -> bool:
        """Report whether the key now contains the expected bytes."""
        ...


class ObjectStore(Protocol):
    """Narrow immutable-object capability used by the flow."""

    def read(self, key: str) -> bytes | None:
        """Return exact object bytes, or None when absent."""
        ...

    def create(self, key: str, payload: bytes, content_type: str) -> CreateResult:
        """Conditionally create an object without overwriting it."""
        ...

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        """List keys beneath a prefix in deterministic order."""
        ...


class AwsErrorDetail(BaseModel):
    """Parsed botocore error detail."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    code: str = Field(alias="Code")


class AwsErrorResponse(BaseModel):
    """Parsed botocore error response boundary."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")

    error: AwsErrorDetail = Field(alias="Error")


@final
class BotoObjectStore:
    """S3 adapter with create-only writes and bounded conflict retries."""

    _RETRY_DELAYS: ClassVar[tuple[float, ...]] = (0.1, 0.2, 0.4)

    def __init__(
        self,
        client: S3Client,
        bucket: str,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        """Bind a typed client, bucket, and conflict sleeper."""
        self._client = client
        self._bucket = bucket
        self._sleep = sleeper

    @classmethod
    def from_settings(cls, settings: StorageSettings) -> BotoObjectStore:
        """Create a path-style, Signature-v4 client from non-secret settings."""
        session = Session()
        client: S3Client = session.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            region_name=settings.region,
            config=Config(
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 3, "mode": "standard"},
                s3={"addressing_style": "path"},
                signature_version="s3v4",
            ),
        )
        return cls(client=client, bucket=settings.bucket)

    def read(self, key: str) -> bytes | None:
        """Read exact bytes while translating expected SDK errors."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            with response["Body"] as body:
                return body.read()
        except ClientError as error:
            code = self._error_code(error)
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise StorageError(operation="read", key=key, code=code) from error
        except BotoCoreError as error:
            raise StorageError(
                operation="read",
                key=key,
                code=type(error).__name__,
            ) from error

    def create(self, key: str, payload: bytes, content_type: str) -> CreateResult:
        """Create with If-None-Match and retain it across conflict retries."""
        for delay in (*self._RETRY_DELAYS, None):
            try:
                _ = self._client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=payload,
                    ContentType=content_type,
                    IfNoneMatch="*",
                )
                return Created()
            except ClientError as error:
                code = self._error_code(error)
                if code in {"412", "PreconditionFailed"}:
                    existing = self.read(key)
                    if existing is None:
                        raise StorageError(
                            operation="create",
                            key=key,
                            code="precondition-without-object",
                        ) from error
                    return Existing(payload=existing)
                if code in {"409", "ConditionalRequestConflict"} and delay is not None:
                    self._sleep(delay)
                    continue
                raise StorageError(operation="create", key=key, code=code) from error
            except BotoCoreError as error:
                raise StorageError(
                    operation="create",
                    key=key,
                    code=type(error).__name__,
                ) from error
        raise StorageError(operation="create", key=key, code="retry-exhausted")

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        """List every page and normalize stale duplicate page entries."""
        keys: set[str] = set()
        token: str | None = None
        while True:
            try:
                if token is None:
                    response = self._client.list_objects_v2(
                        Bucket=self._bucket,
                        Prefix=prefix,
                    )
                else:
                    response = self._client.list_objects_v2(
                        Bucket=self._bucket,
                        Prefix=prefix,
                        ContinuationToken=token,
                    )
            except (BotoCoreError, ClientError) as error:
                raise StorageError(
                    operation="list",
                    key=prefix,
                    code=type(error).__name__,
                ) from error
            for summary in response.get("Contents", ()):
                key = summary.get("Key")
                if key is None:
                    raise StorageError(
                        operation="list",
                        key=prefix,
                        code="malformed-sdk-response",
                    )
                keys.add(key)
            if "NextContinuationToken" not in response:
                return tuple(sorted(keys))
            token = response["NextContinuationToken"]

    @staticmethod
    def _error_code(error: ClientError) -> str:
        try:
            return AwsErrorResponse.model_validate(error.response).error.code
        except ValidationError:
            return "malformed-sdk-error"
