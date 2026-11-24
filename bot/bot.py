"""Telegram-бот: отвечает на вопросы по данным 1С (долги, продажи, остатки) и по инструкциям.

Токен берётся из переменной RAG1C_TELEGRAM_TOKEN или из Диспетчера учётных данных Windows
(общие учётные данные, адрес RAG1C_TelegramBot). Заведите для этого отдельного бота у @BotFather.

Доступ: бот отвечает только тем, чьи Telegram ID записаны в allowed_users.txt (по одному в строке).
Свой ID можно узнать командой /myid. Остальным бот отвечает «нет доступа».

    python bot.py
"""
import sys
from pathlib import Path

import telebot

import data1c
from rag import answer, api_key, get_index, read_secret

sys.stdout.reconfigure(encoding="utf-8")

ALLOWED_FILE = Path(__file__).resolve().parent / "allowed_users.txt"

token = read_secret("RAG1C_TELEGRAM_TOKEN", "RAG1C_TelegramBot")
if not token:
    sys.exit("Нет токена бота: задайте RAG1C_TELEGRAM_TOKEN или учётные данные RAG1C_TelegramBot.")

# threaded=False: сообщения обрабатываются по очереди в одном потоке — COM-соединение с 1С
# нельзя использовать из разных потоков
bot = telebot.TeleBot(token, threaded=False)
index = get_index()

HELLO = ("Привет! Я помощник по 1С. Можно спрашивать:\n\n"
         "📊 По данным базы:\n"
         "• кто нам должен? / просроченные долги\n"
         "• сколько должен Ромашка?\n"
         "• долги на 1 ноября\n"
         "• продажи за октябрь / за прошлый месяц / за 2025 год\n"
         "• остаток фильтр масляный\n"
         "• залежавшиеся товары\n\n"
         "📘 По инструкциям:\n"
         "• где найти загрузку счетов из Excel?\n"
         "• почему не видно команды после установки?")


def allowed_ids() -> set[int]:
    if not ALLOWED_FILE.exists():
        return set()
    ids = set()
    for line in ALLOWED_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line.lstrip("-").isdigit():
            ids.add(int(line))
    return ids


def has_access(msg) -> bool:
    ok = msg.from_user.id in allowed_ids()
    if not ok:
        print(f"Нет доступа: {msg.from_user.id} (@{msg.from_user.username})", flush=True)
        bot.reply_to(msg, f"Нет доступа. Ваш Telegram ID: {msg.from_user.id}. "
                          "Попросите владельца бота добавить его в список.")
    return ok


def send(chat_id, text):
    for i in range(0, len(text), 4000):  # лимит Telegram — 4096 символов
        bot.send_message(chat_id, text[i:i + 4000])


@bot.message_handler(commands=["myid"])
def myid(msg):
    bot.reply_to(msg, f"Ваш Telegram ID: {msg.from_user.id}")


@bot.message_handler(commands=["start", "help"])
def start(msg):
    if has_access(msg):
        bot.reply_to(msg, HELLO)


@bot.message_handler(content_types=["text"])
def ask(msg):
    if not has_access(msg):
        return
    print(f"Вопрос: {msg.text}", flush=True)
    bot.send_chat_action(msg.chat.id, "typing")
    text = data1c.safe_route(msg.text)
    source = "1С"
    if text is None:
        text = answer(index, msg.text)
        source = "инструкции"
    print(f"Ответ ({source}): {text.splitlines()[0][:100]}", flush=True)
    send(msg.chat.id, text)


if __name__ == "__main__":
    n = len(allowed_ids())
    print(f"Бот запущен. Фрагментов инструкций: {len(index.chunks)}. Claude API: {'да' if api_key() else 'нет'}. "
          f"Разрешённых пользователей: {n}", flush=True)
    if not n:
        print("ВНИМАНИЕ: allowed_users.txt пуст — бот никому не будет отвечать. Узнайте свой ID командой /myid.", flush=True)
    bot.infinity_polling()
