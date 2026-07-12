"""Typed strict-YAML trust boundary."""

from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from smurf_child.models import ContractErrorCategory, ContractValidationError
from smurf_child.yaml_adapter import load_json_yaml

type JsonScalar = str | int | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

_JSON_VALUE: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


def load_yaml(path: Path, category: ContractErrorCategory) -> JsonValue:
    """Parse exactly one strict YAML document into a typed JSON value."""
    try:
        return _JSON_VALUE.validate_python(load_json_yaml(path, category), strict=True)
    except ValidationError as error:
        raise ContractValidationError(category, path) from error
