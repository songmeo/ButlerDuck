from db import con
from datetime import datetime, timezone
import isodate


def set_reminder(chat_id: int, action: str, deadline: str, duration: str) -> str:
    today = datetime.now(timezone.utc)
    if deadline:
        if (datetime.fromisoformat(deadline) - today).seconds < -60:
            return "Sorry deadline is past."
    elif duration:
        td = isodate.parse_duration(duration)
        deadline = today + td
    else:
        return "You must define deadline or duration."
    cur = con.cursor()

    cur.execute(
        "INSERT INTO user_reminder (chat_id, action, deadline) VALUES (%s, %s, %s)", (chat_id, action, deadline)
    )
    con.commit()

    return f"A reminder for '{action}' is set on {deadline}."


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
