import string
from db import con
from datetime import datetime


def set_reminder(chat_id: int, action: str, deadline: str) -> str:
    today = datetime.now()
    if datetime.fromisoformat(deadline) < today:
        return "the deadline is in the past."
    cur = con.cursor()
    cur.execute(
        "INSERT INTO user_reminder (chat_id, action, deadline) VALUES (%s, %s, %s)", (chat_id, action, deadline)
    )
    con.commit()
    return f"A reminder for {action} is set on {deadline}."


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
