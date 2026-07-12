class ConstructorError(Exception):
    def __init__(
        self,
        context: str | None,
        context_mark: str | None,
        problem: str,
        problem_mark: str | None,
    ) -> None: ...
