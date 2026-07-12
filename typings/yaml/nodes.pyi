class Node:
    tag: str
    start_mark: str

class ScalarNode(Node):
    value: str
    style: str | None

class SequenceNode(Node):
    value: list[ScalarNode | SequenceNode | MappingNode]

class MappingNode(Node):
    value: list[
        tuple[
            ScalarNode | SequenceNode | MappingNode,
            ScalarNode | SequenceNode | MappingNode,
        ]
    ]
