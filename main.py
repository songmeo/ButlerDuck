import logging
import re
import sqlite3
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

XAI_API_KEY = os.environ['XAI_API_KEY']
TOKEN = os.environ['TOKEN']
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

USERS: dict[int, str] = {129626155: "chubby", 787018746: "songmeo"}
client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")


def ask_ai(question: str, messages: list) -> str:
    completion = client.chat.completions.create(
        model="grok-beta",
        messages=messages
    )
    answer = completion.choices[0].message.content
    return answer


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE, con: sqlite3.Connection) -> None:
    """Echo the user message."""
    text = update.message.text
    cur = con.cursor()
    if re.match("bot g+r+", text):
        cur.execute("""
            REPLACE INTO status VALUES   
            (True)
        """)
        con.commit()
    elif text == "bot ple":
        cur.execute("""
            REPLACE INTO status VALUES
            (False)
        """)
        con.commit()
    else:
        enabled = bool(cur.execute("SELECT enabled FROM status").fetchall()[-1][0])
        if enabled:
            chat_id = update.message.chat_id
            cur.execute("INSERT INTO user_message VALUES (NULL,?,False,?)", (chat_id, text))

            messages = []
            all_messages = cur.execute(
                "select is_bot, message from user_message where chat_id=? order by id limit 1000",
                (chat_id,)).fetchall()
            for is_bot, message in all_messages:
                messages.append({"role": "system" if is_bot else "user", "content": message})
            answer = ask_ai(text, messages)
            cur.execute("INSERT INTO user_message VALUES (NULL,?,True,?)", (chat_id, answer))
            con.commit()

            await update.message.reply_text(answer)


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    con = sqlite3.connect("telegrambot.db")

    async def echo_proxy(update, context):
        await echo(update, context, con)

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, echo_proxy))

    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS status(enabled UNIQUE)")
    cur.execute("""
        REPLACE INTO status VALUES
        (False)
    """)

    cur.execute("CREATE TABLE IF NOT EXISTS user(username UNIQUE, message_count)")
    cur.execute("""
        REPLACE INTO user VALUES
        ('songmeo', 0),
        ('chubby', 0)
    """)

    cur.execute("CREATE TABLE IF NOT EXISTS user_message("
                "id INTEGER PRIMARY KEY, chat_id INTEGER, is_bot BOOLEAN,message TEXT)")
    con.commit()

    async def echo_proxy(update, context):
        await echo(update, context, con)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
