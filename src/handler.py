import base64
import os
import uuid
from datetime import datetime
from typing import Any
from pathlib import Path
import psycopg2
from telegram import Update, Message, PhotoSize
from telegram.ext import ExtBot, CallbackContext
from llm import ask_ai
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
    If you need today date to set reminder, it is {datetime.now().isoformat()}.
    """
DB_BLOB_DIR = Path(os.environ["DB_BLOB_DIR"])
DB_BLOB_DIR.mkdir(parents=True, exist_ok=True)


async def store_message(message: Message, bot: ExtBot, con: psycopg2.connect) -> None:
    if message.from_user is None:
        logger.warning("Message has no sender. Skipping...")
        return

    logger.info(
        "Mew message from chat %s, user %s",
        message.chat_id,
        message.from_user.id,
    )
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

    text = message.text
    photo = message.photo
    if text:
        cur.execute(
            """
            INSERT INTO user_message (chat_id, user_id, message_id, message)
            VALUES (%s, %s, %s, %s)
            """,
            (chat_id, user_id, message_id, text),
        )

    if photo:
        user_image_id = await store_photo(photo[0], bot, con)
        cur.execute(
            """
            INSERT INTO user_message (chat_id, user_id, message_id, user_image_id)
            VALUES (%s, %s, %s, %s)
            """,
            (chat_id, user_id, message_id, user_image_id),
        )

    con.commit()


async def generate_response(chat_id: int, con: psycopg2.connect) -> str:
    cur = con.cursor()
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    cur.execute(
        """
        SELECT 
            user_message.user_id,
            tg_user.name AS username,
            user_message.message,
            user_image.image_path AS image_path
        FROM 
            user_message
        JOIN
            tg_user
        ON 
            user_message.user_id = tg_user.tg_id
        LEFT JOIN 
            user_image
        ON
            user_message.user_image_id = user_image.id
        WHERE 
            user_message.chat_id = %s
        ORDER BY 
            user_message.id ASC
        LIMIT 1000;
        """,
        (chat_id,),
    )
    all_messages = cur.fetchall()
    for user_id, user_name, message, image_path in all_messages:
        if image_path:
            try:
                base64_image = base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                            },
                        ],
                    }
                )
            except FileNotFoundError:
                logger.error(f"File not found: {image_path}")
        if message:
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


def _make_unique_blob_path_relative(object_kind: str) -> Path:
    uu = uuid.uuid4()
    return Path(object_kind) / uu.hex[:5] / str(uu)


async def store_photo(photo: PhotoSize, bot: ExtBot, con: psycopg2.connect) -> int:
    try:
        tg_file_id = photo.file_id
        tg_file_info = await bot.get_file(tg_file_id)
        local_file_path = _make_unique_blob_path_relative("image")
        local_full_path = DB_BLOB_DIR / local_file_path
        local_full_path.parent.mkdir(parents=True, exist_ok=True)

        await tg_file_info.download_to_drive(str(local_full_path))

        logger.info(f"Photo saved as {local_full_path}")

        cur = con.cursor()
        cur.execute("INSERT INTO user_image (image_path) VALUES (%s) RETURNING id", (str(local_full_path),))
        image_id: int = cur.fetchone()[0]
        con.commit()

        return image_id

    except Exception as e:
        raise Exception(f"An unexpected error {e}")


async def help_command(update: Update, context: CallbackContext) -> None:
    _ = context

    if update.message is None:
        return

    help_text = (
        "🤖 *ButlerBot Behavior:*\n"
        f"ButlerBot observes conversations but does not normally interfere.\n"
        f"It only responds when explicitly called by name (e.g., 'bot', '{BOT_NAME}').\n"
        f"If the bot has nothing to say, it will respond with: `{no_reply_token}`.\n\n"
        "📌 *Available Commands:*\n"
        "/help - Show this help message\n"
        "/todo - Manage your to-do list (upcoming) \n"
        "/remind - Set reminders (upcoming) \n"
        "\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")
