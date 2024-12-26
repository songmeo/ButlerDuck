tools = [
    {
        "type": "function",
        "function": {
            "name": "evaluate",
            "description": "calculate an arithmetic expression",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "the expression in string form",
                    }
                },
            },
            "required": ["expression"],
            "additionalProperties": False,
        },
    }
]
