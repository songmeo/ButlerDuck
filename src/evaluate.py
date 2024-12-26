def evaluate(expression: str) -> str:
    # todo: catch wrong expression
    return str(eval(expression))


def test_evaluate() -> None:
    # TODO: add PyTest config to the project
    assert evaluate("123 + 456") == str(123 + 456)
