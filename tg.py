#!/usr/bin/python3.3
import threading, telebot, schedule, time, random, yaml
from datetime import datetime
import os, sys
from telebot import types
from telegram.constants import ParseMode
import for_db as db
import re
import locale

config = yaml.safe_load(open("config.yaml"))
bot = telebot.TeleBot(
    config["api_token"],
    colorful_logs=True,
    disable_web_page_preview=True,
    parse_mode=ParseMode.HTML,
)

admin_id = config["admin_id"]
bot_username = config["bot_username"]

locale.setlocale(locale.LC_ALL, "ru_RU.UTF-8")


def is_admin(message):
    if (
        str(message.from_user.id) == admin_id
        and message.from_user.id == message.chat.id
    ):
        return True

    return False


@bot.message_handler(commands=["restart", "r"])
def restart_bot(message):
    if is_admin(message):
        send_admin_message("bye")
        os.execv(sys.executable, ["python3", "-u"] + sys.argv)


@bot.message_handler(commands=["start"])
def start(message):

    print(db.new_user(message))

    return


@bot.message_handler(commands=["help", "faq"])
def help(message):
    help_msg = "Мои команды:\
            \n/start - используй, чтобы сменить номер группы.\
            \n/list - список напоминаний.\
            \n/source - Страница бота на Github\
            \n\nИли же можно всегда написать напрямую: @Kr0sH_512"

    send_message(message.chat.id, help_msg)

    return


@bot.callback_query_handler(func=lambda call: "#return" in call.data)
def send_notes_callback(call):
    list_notes(call.message, call.data.split("#")[0])
    bot.delete_message(call.message.chat.id, call.message.message_id)

    return


@bot.callback_query_handler(func=lambda call: "#del#" in call.data)
def delete_notes_callback(call):
    note_ind = int(call.data.split("#")[2])
    prefix = call.data.split("#")[0]

    note = db.get_notes(call.message.chat.id, prefix)["notes"][note_ind]

    db.delete_note(call.message.chat.id, note_ind, prefix)

    bot.edit_message_text(
        f"❌ Удалено:\n\n{note['text']}",
        call.message.chat.id,
        call.message.message_id,
    )

    list_notes(call.message, prefix)

    return


@bot.callback_query_handler(func=lambda call: "#conf#" in call.data)
def edit_notes_callback(call):
    note_ind = int(call.data.split("#")[2])
    prefix = call.data.split("#")[0]
    notes = db.get_notes(call.message.chat.id, prefix)["notes"]

    note = notes[note_ind]

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "Удалить",
            callback_data=f"{prefix}#del#{note_ind}",
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "Назад",
            callback_data=f"{prefix}#return",
        )
    )

    text = f"📝 <b>Заметка {note_ind + 1}</b>"

    if note["time_notif"]:
        text += f" ⌚️ <b>{datetime.strptime(note['time_notif'], '%Y-%m-%d %H:%M:%S').strftime('%d %B %Y')}</b>"

    text += f"\n\n{note['text']}"

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )

    return


@bot.callback_query_handler(func=lambda call: "#select#" in call.data)
def choose_note_callback(call):
    page = int(call.data.split("#")[2])
    prefix = call.data.split("#")[0]
    markup = types.InlineKeyboardMarkup()
    num_on_page = 8  # Лимит телеграмма
    notes = db.get_notes(call.message.chat.id, prefix)["notes"]

    max_page = (len(notes) - 1) // num_on_page

    lst_button = []

    for i in range(num_on_page):
        # Calculate the index of the current program
        ind = i + page * num_on_page

        # Create an inline keyboard button for the program
        lst_button.append(
            types.InlineKeyboardButton(
                ind + 1,
                callback_data=f"{prefix}#conf#{ind}",
            )
        )

        if ind == len(notes) - 1:
            break

    # Create the inline keyboard markup from the list of buttons
    markup = types.InlineKeyboardMarkup([lst_button])

    if len(notes) > num_on_page:
        # Create the back button (only visible if we're not on the first page)
        back_btn = (
            types.InlineKeyboardButton(
                "Назад", callback_data=f"{prefix}#select#{page - 1}"
            )
            if page > 0
            else None
        )

        # Create the current page button
        now_btn = types.InlineKeyboardButton(
            f"{page + 1}/{max_page + 1}",
            callback_data=f"{prefix}#select#{0 if page > 0 else max_page}",
        )

        # Create the next button (only visible if we're not on the last page)
        next_btn = (
            types.InlineKeyboardButton(
                "Вперед", callback_data=f"{prefix}#select#{page + 1}"
            )
            if page < max_page
            else None
        )

        # Add the buttons to the inline keyboard markup
        markup.row(*[i for i in [back_btn, now_btn, next_btn] if i])

    markup.add(
        types.InlineKeyboardButton(
            "Назад",
            callback_data=f"{prefix}#return",
        )
    )

    bot.edit_message_text(
        call.message.text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )

    return


@bot.message_handler(commands=["list"])
def list_notes(message, list="Default"):

    notes = db.get_notes(message.chat.id, list)

    if not notes or not notes["notes"]:
        send_message(message.chat.id, "У вас нет напоминаний.")

        return

    list_notes = notes["notes"]

    for i in range(len(list_notes)):
        if list_notes[i]["time_notif"]:
            if (
                datetime.strptime(list_notes[i]["time_notif"], "%Y-%m-%d %H:%M:%S")
                - datetime.now()
            ).days < 0:
                send_message(
                    message.chat.id,
                    f"❌ {list_notes[i]['text']} (просрочено: {list_notes[i]['time_notif']})",
                )
                db.delete_note(message.chat.id, i)

    notes = db.get_notes(message.chat.id, list)

    if not notes:
        send_message(message.chat.id, "У вас нет напоминаний.")

        return

    list_notes = notes["notes"]

    notes_msg = "⚡️ <u>Ваши напоминания</u>:\n\n"
    for i in range(len(list_notes)):
        notes_msg += f"<b>{i + 1})</b> "
        if list_notes[i]["time_notif"]:
            notes_msg += f" ⌚️ <b>{datetime.strptime(list_notes[i]['time_notif'], '%Y-%m-%d %H:%M:%S').strftime('%d %B %Y')}:</b>\n"

        notes_msg += f"{list_notes[i]['text']}\n\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "Выбрать номер", callback_data=f"{'Default'}#select#0"
        )
    )

    send_message(message.chat.id, notes_msg, markup)

    return


@bot.message_handler(content_types=["text"])
def text_message(message):
    if message.chat.type == "supergroup" and bot_username not in message.text:
        # print(message.text)
        return  # ignore messages from supergroups

    if db.check_user(message.chat.id) is None:
        db.new_user(message)

    message.text = message.text.replace(f"{bot_username}", "").strip()
    if not message.text:
        if not message.reply_to_message:
            return
        message.text = message.reply_to_message.text

    date_patterns = [
        r"\b\d{1,2}\s(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\b",
        r"\b\d{1,2}\s(?:январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь)\b",
        r"\b\d{1,2}\.\d{1,2}\b",
        r"\b\d{1,2}ое\s(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\b",
    ]

    month_mapping = {
        "январь": "января",
        "февраль": "февраля",
        "март": "марта",
        "апрель": "апреля",
        "май": "мая",
        "июнь": "июня",
        "июль": "июля",
        "август": "августа",
        "сентябрь": "сентября",
        "октябрь": "октября",
        "ноябрь": "ноября",
        "декабрь": "декабря",
    }

    def translate_date_to_datetime(date_str):
        for ru_month, en_month in month_mapping.items():
            if ru_month in date_str:
                date_str = date_str.replace(ru_month, en_month)
                # break
        try:
            return datetime.strptime(date_str, "%d %B").replace(
                year=datetime.now().year
            )
        except ValueError:
            try:
                return datetime.strptime(date_str, "%dое %B").replace(
                    year=datetime.now().year
                )
            except ValueError:
                try:
                    return datetime.strptime(date_str, "%d.%m").replace(
                        year=datetime.now().year
                    )
                except ValueError:
                    return None

    date_found_dt = None

    for pattern in date_patterns:
        match = re.search(pattern, message.text, re.IGNORECASE)
        if match:
            # print(match.group())
            date_found_dt = translate_date_to_datetime(match.group())

            break

    if date_found_dt:
        if date_found_dt < datetime.now():
            date_found_dt = date_found_dt.replace(year=datetime.now().year + 1)

    db.add_note(
        message.chat.id,
        message.text,
        date_found_dt,
    )

    send_message(message.chat.id, "📝 Напоминание добавлено:")
    list_notes(message)

    return


def send_message(id, text, markup=None, thread_id="General"):
    if thread_id == "General":
        thread_id = None

    try:
        bot.send_message(
            chat_id=id,
            text=text,
            message_thread_id=thread_id,
            reply_markup=markup,
        )
    except Exception as e:
        time.sleep(5)
        try:
            bot.send_message(
                chat_id=id,
                text=text,
                message_thread_id=thread_id,
                reply_markup=markup,
            )
        except Exception as e:
            text_error = "Error from user: <code>{}</code>\n{}".format(id, str(e))
            # send_admin_message(text_error)
            print(f"--- {text_error} ---")

    return


def send_admin_message(text):
    send_message(admin_id, "🛑 " + text)

    return


if __name__ == "__main__":
    print("-------------------------")

    threading.Thread(
        target=bot.infinity_polling,
        name="bot_infinity_polling",
        daemon=True,
        # kwargs={"restart_on_change": True},
    ).start()

    while True:  # keep alive
        # добавить проверку живых напоминаний, удалять, если они не нужны
        print("I'm alive!")
        time.sleep(36000)  # 10 hours
