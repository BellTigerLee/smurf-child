"""PyYAML node adapter isolated from incomplete third-party type stubs."""

from pathlib import Path
from typing import assert_never, override

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
from yaml.tokens import AliasToken, AnchorToken

from smurf_child.models import ContractErrorCategory, ContractValidationError

type JsonScalar = str | int | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

_SCALAR_TAGS = {
    "tag:yaml.org,2002:str",
    "tag:yaml.org,2002:int",
    "tag:yaml.org,2002:bool",
    "tag:yaml.org,2002:null",
}


class StrictLoader(yaml.SafeLoader):
    """Safe loader that refuses duplicate mapping keys."""

    @override
    def construct_mapping(
        self, node: MappingNode, deep: bool = False
    ) -> dict[str, JsonValue]:
        """Construct a mapping only after checking key type and uniqueness."""
        keys: set[str] = set()
        for key_node, _ in node.value:
            if (
                not isinstance(key_node, ScalarNode)
                or key_node.tag != "tag:yaml.org,2002:str"
            ):
                raise yaml.constructor.ConstructorError(
                    None, None, "non-string key", key_node.start_mark
                )
            if key_node.value in keys:
                raise yaml.constructor.ConstructorError(
                    None, None, "duplicate key", key_node.start_mark
                )
            keys.add(key_node.value)
        return super().construct_mapping(node, deep=deep)


def _validate_node(node: Node) -> None:
    match node:
        case ScalarNode(tag=tag, value=value):
            if tag not in _SCALAR_TAGS:
                raise yaml.constructor.ConstructorError(
                    None, None, f"forbidden scalar {tag}", node.start_mark
                )
            if tag == "tag:yaml.org,2002:int" and (
                value.startswith(("0x", "0o", "0b")) or "_" in value
            ):
                raise yaml.constructor.ConstructorError(
                    None, None, "non-JSON integer", node.start_mark
                )
            if tag == "tag:yaml.org,2002:bool" and value not in {"true", "false"}:
                raise yaml.constructor.ConstructorError(
                    None, None, "non-JSON boolean", node.start_mark
                )
        case SequenceNode(value=values):
            for child in values:
                _validate_node(child)
        case MappingNode(value=values):
            if node.tag != "tag:yaml.org,2002:map":
                raise yaml.constructor.ConstructorError(
                    None, None, "forbidden mapping", node.start_mark
                )
            for key, value in values:
                _validate_node(key)
                _validate_node(value)
        case _ as unreachable:
            assert_never(unreachable)
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"forbidden node {type(unreachable).__name__}",
                node.start_mark,
            )


def load_json_yaml(path: Path, category: ContractErrorCategory) -> JsonValue:
    """Load one alias-free document after validating every YAML node tag."""
    try:
        text = path.read_text(encoding="utf-8")
        if any(
            isinstance(token, (AliasToken, AnchorToken)) for token in yaml.scan(text)
        ):
            raise yaml.constructor.ConstructorError(
                None, None, "aliases forbidden", None
            )
        nodes = tuple(yaml.compose_all(text, Loader=StrictLoader))
        if len(nodes) != 1 or nodes[0] is None:
            raise yaml.constructor.ConstructorError(
                None, None, "exactly one document required", None
            )
        _validate_node(nodes[0])
        return yaml.load(
            text,
            Loader=StrictLoader,  # noqa: S506 - audited SafeLoader subclass
        )
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ContractValidationError(category, path) from error
