from typing import Literal

from botocore.config import Config
from types_boto3_s3 import S3Client

class Session:
    def __init__(self) -> None: ...
    def client(
        self,
        service_name: Literal["s3"],
        region_name: str | None = ...,
        endpoint_url: str | None = ...,
        config: Config | None = ...,
    ) -> S3Client: ...
