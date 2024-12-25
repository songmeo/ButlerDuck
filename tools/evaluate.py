import operator


def evaluate(num1: float, num2: float, operation: str) -> float:
    operations = {
        "+": operator.add,
        "-": operator.sub,
        "*": operator.mul,
        "/": operator.truediv,
    }
    return operations[operation](num1, num2)
