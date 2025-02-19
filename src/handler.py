import asyncio
import uuid
import urllib.request
import psycopg2
import os

from telegram import Update, Message
from telegram.ext import (
    CallbackContext,
)
from llm import ask_ai, analyze_photo
from logger import logger

BOT_NAME = "ButlerBot"
BOT_USER_ID = 0
BOT_MESSAGE_ID = 0
no_reply_token = "-"
SYSTEM_PROMPT = f"""
    Each message in the conversation below is prefixed with the username and their unique 
    identifier, like this: "username (123456789): MESSAGE...". '
    You play the role of the user called {BOT_NAME}, or simply Bot;
    your username and unique identifier are {BOT_NAME} and 0. 
    You are observing the users' conversation and normally you do not interfere 
    unless you are explicitly called by name (e.g., 'bot,' '{BOT_NAME},' etc.). 
    Explicit mentions include cases where your name or identifier appears anywhere in the message. 
    If you are not explicitly addressed, always respond with {no_reply_token}.
    When answering, don't use LaTeX.
    """


async def store_message(message: Message, con: psycopg2.connect) -> None:
    if message.from_user is None:
        logger.warning("Message has no sender. Skipping...")
        return

    logger.info(
        "Mew message from chat %s, user %s",
        message.chat_id,
        message.from_user.id,
    )
    text = message.text
    cur = con.cursor()
    chat_id, user_id, message_id, username = (
        message.chat_id,
        message.from_user.id,
        message.message_id,
        message.from_user.username,
    )
    cur.execute(
        """
        INSERT INTO tg_user (tg_id, name)
        VALUES (%s, %s)
        ON CONFLICT (tg_id) DO NOTHING
        """,
        (user_id, username),
    )
    cur.execute(
        """
        INSERT INTO user_message (chat_id, user_id, message_id, message)
        VALUES (%s, %s, %s, %s)
        """,
        (chat_id, user_id, message_id, text),
    )
    con.commit()


async def generate_response(chat_id: int, con: psycopg2.connect) -> str:
    cur = con.cursor()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    cur.execute(
        """
        SELECT 
            user_message.user_id,
            tg_user.name AS username,
            user_message.message
        FROM 
            user_message
        JOIN
            tg_user
        ON 
            user_message.user_id = tg_user.tg_id
        WHERE 
            user_message.chat_id = %s
        ORDER BY 
            user_message.id ASC
        LIMIT 1000;
        """,
        (chat_id,),
    )
    all_messages = cur.fetchall()
    for user_id, user_name, message in all_messages:
        messages.append(
            {
                "role": "assistant" if user_id == 0 else "user",
                "content": f"{user_name} ({user_id}): {message}",
            }
        )
    logger.info("all messages: %s", messages)
    response = await ask_ai(messages)
    response = response.removeprefix(f"{BOT_NAME} ({BOT_USER_ID}): ")
    cur.execute(
        """
        INSERT INTO user_message (chat_id, user_id, message)
        VALUES (%s, 0, %s)
        """,
        (chat_id, response),
    )
    con.commit()
    return response


async def photo_handler(update: Update, context: CallbackContext) -> None:
    try:
        if update.message is None:
            logger.warning("No image to analyze. Skipping...")
            return

        file_id = update.message.photo[-1].file_id
        file_info = await context.bot.get_file(file_id)
        file_path = file_info.file_path

        file_name = f"{uuid.uuid4()}.jpg"

        loop = asyncio.get_running_loop()

        def runs_in_background_thread() -> None:
            try:
                with urllib.request.urlopen(file_path) as response:
                    if response.status == 200:
                        with open(file_name, "wb") as f:
                            f.write(response.read())
                        logger.info(f"File downloaded successfully: {file_name}")
                    else:
                        logger.error(f"Failed to download the file. Status code: {response.status}")
            except Exception as e:
                logger.error(f"Unexpected error while downloading the file: {e}")

        try:
            await loop.run_in_executor(None, runs_in_background_thread)
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return

        response = await analyze_photo(update, file_name)

        if os.path.exists(file_name):
            os.remove(file_name)

        await update.message.reply_text(response)

    except Exception as e:
        raise Exception(f"An unexpected error {e}")
