def evaluate(expression: str) -> str:
    try:
        ans = eval(expression)
    except Exception as error:
        return str(type(error).__name__)
    return str(ans)


def test_evaluate() -> None:
    # TODO: add PyTest config to the project
    assert evaluate("123 + 456") == str(123 + 456)


def test_evaluate_name_error() -> None:
    # TODO: add PyTest config to the project
    assert evaluate("455 +_/ 342") == "NameError"


def test_evaluate_syntax_error() -> None:
    # TODO: add PyTest config to the project
    assert evaluate("455 +_( 342") == "SyntaxError"
