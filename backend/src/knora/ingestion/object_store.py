from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    workspace_id: str
    object_key: str
    sha256: str
    byte_size: int
    media_type: str


class ObjectStore(Protocol):
    def put_stream(
        self,
        *,
        workspace_id: str,
        stream: BinaryIO,
        media_type: str,
    ) -> ObjectMetadata: ...

    def open_read(self, *, workspace_id: str, object_key: str) -> BinaryIO: ...

    def head(self, *, workspace_id: str, object_key: str) -> ObjectMetadata: ...

    def delete(self, *, workspace_id: str, object_key: str) -> None: ...
