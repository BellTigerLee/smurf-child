from collections.abc import Iterator

from yaml.nodes import MappingNode, ScalarNode, SequenceNode
from yaml.tokens import Token

from . import constructor as constructor

type JsonScalar = str | int | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

class YAMLError(Exception): ...

class SafeLoader:
    def construct_mapping(
        self, node: MappingNode, deep: bool = False
    ) -> dict[str, JsonValue]: ...

def scan(stream: str) -> Iterator[Token]: ...
def compose_all(
    stream: str, Loader: type[SafeLoader]
) -> Iterator[ScalarNode | SequenceNode | MappingNode | None]: ...
def load(stream: str, Loader: type[SafeLoader]) -> JsonValue: ...
