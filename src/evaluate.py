def evaluate(expression: str) -> str:
    try:
        ans = eval(expression)
    except Exception as error:
        return str(type(error).__name__)
    return str(ans)


def test_evaluate() -> None:
    assert evaluate("123 + 456") == str(123 + 456)
    assert evaluate("455 +_/ 342") == "NameError"
    assert evaluate("455 +_( 342") == "SyntaxError"
    assert evaluate("455 / 0") == "ZeroDivisionError"
