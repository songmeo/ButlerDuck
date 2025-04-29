import asyncio
import json
from typing import Any
import os
import openai
from openai import OpenAI
from openai.types.chat import ChatCompletion

from tool_function import evaluate, set_reminder
import logging

logger = logging.getLogger(__name__)

# todo: make this a class

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = "gpt-4o"

TOOL_DEF = json.load(open("tools.json"))

client = OpenAI(api_key=OPENAI_API_KEY)


async def ask_ai(messages: list[Any]) -> str:
    loop = asyncio.get_running_loop()  # gain access to the scheduler

    def runs_in_background_thread() -> ChatCompletion:
        try:
            # noinspection PyShadowingNames
            completion = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                tools=TOOL_DEF,
            )
        except openai.BadRequestError as e:
            logger.error(f"OpenAI API error: {e}")
            raise ValueError("Missing corresponding tool_call responses for tool_call_ids.") from e
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise Exception("An unexpected error occurred while processing the tool call.") from e
        return completion

    completion = await loop.run_in_executor(None, runs_in_background_thread)
    message = completion.choices[0].message

    while message.tool_calls:
        tool_call = message.tool_calls[0]
        logger.info(f"tool call {tool_call}")
        function = tool_call.function.name
        answer = "no function is called."
        if function == "set_reminder":
            arguments = json.loads(tool_call.function.arguments)
            chat_id, action, duration, deadline = (
                arguments["chat_id"],
                arguments["action"],
                arguments.get("duration", None),
                arguments.get("deadline", None),
            )
            answer = set_reminder(chat_id, action, deadline, duration)
        elif function == "evaluate":
            arguments = json.loads(tool_call.function.arguments)
            expression = arguments["expression"]
            answer = evaluate(expression)
        logger.info(f"Tool call message: {message}")
        function_call_result_message = {
            "role": "tool",
            "content": json.dumps({"result": answer}),
            "tool_call_id": tool_call.id,
        }
        messages = [message, function_call_result_message]
        try:
            completion = await loop.run_in_executor(None, runs_in_background_thread)
            message = completion.choices[0].message
        except ValueError as ve:
            logger.error(f"Tool call validation error: {ve}")
            return f"There is problem with our calculation tool! Please try again later."
        except Exception as e:
            logger.error(f"Unexpected error during tool call: {e}")
            return f"Unexpected error occurred. Please try again later."

        logger.info("tool_call and call_result messages: %s", messages)

    logger.info("bot replied: %s", completion.choices)

    if message.content is None:
        raise ValueError("Unexpected None content from OpenAI response.")

    return message.content
