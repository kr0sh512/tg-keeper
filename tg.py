#!/usr/bin/python3.3
import threading, telebot, schedule, time, yaml
from datetime import datetime
import os, sys, inspect, random
import re, locale
from telegram.constants import ParseMode
from telebot import types
import for_db as db

config = yaml.safe_load(open("config.yaml"))
lang = yaml.safe_load(open("lang.yaml", encoding="utf-8"))["ru"]
list_reactions = yaml.safe_load(open("lang.yaml", encoding="utf-8"))["list_reaction"]
bot = telebot.TeleBot(
    config["api_token"],
    colorful_logs=True,
    disable_web_page_preview=True,
    parse_mode=ParseMode.HTML,
)

admin_id = config["admin_id"]
bot_username = config["bot_username"]


locale.setlocale(locale.LC_ALL, "ru_RU.UTF-8")


def is_admin(message: types.Message):
    if (
        str(message.from_user.id) == str(admin_id)
        and message.from_user.id == message.chat.id
    ):
        return True

    return False


@bot.message_handler(commands=["restart", "r"])
def restart_bot(message: types.Message):
    if is_admin(message):
        send_admin_message("bye")
        os.execv(sys.executable, ["python3", "-u"] + sys.argv)


@bot.message_handler(commands=["start"])
def start(message: types.Message):

    send_message(message, lang["start_message"])

    if not db.check_user(message.chat.id):
        db.new_user(message)

    return


@bot.message_handler(commands=["help", "faq"])
def help(message: types.Message):
    help_msg = lang["help_message"].format(config["bot_username"])

    send_message(message, help_msg)

    if not db.check_user(message.chat.id):
        db.new_user(message)

    return


@bot.callback_query_handler(func=lambda call: "#return" in call.data)
def send_notes_callback(call):

    list_notes(call.message, call.data.split("#")[0], edit=True)

    return


@bot.callback_query_handler(func=lambda call: "#del#" in call.data)
def delete_notes_callback(call):
    note_ind = int(call.data.split("#")[2])
    prefix = call.data.split("#")[0]

    note = db.get_notes(call.message.chat.id, prefix)["notes"][note_ind]

    db.delete_note(call.message.chat.id, note_ind, prefix)

    list_notes(call.message, prefix, edit=True)

    bot.send_message(call.message.chat.id, f"❌ Удалено:\n\n{note['text']}")

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
    num_on_page = 6  # Лимит телеграмма - 8
    notes = db.get_notes(call.message.chat.id, prefix)["notes"]

    max_page = (len(notes) - 1) // num_on_page
    lst_button = []

    for i in range(num_on_page):
        ind = i + page * num_on_page

        lst_button.append(
            types.InlineKeyboardButton(
                str(ind + 1),
                callback_data=f"{prefix}#conf#{ind}",
            )
        )

        if ind == len(notes) - 1:
            break

    markup = types.InlineKeyboardMarkup([lst_button])

    if len(notes) > num_on_page:
        back_btn = (
            types.InlineKeyboardButton(
                "Назад", callback_data=f"{prefix}#select#{page - 1}"
            )
            if page > 0
            else None
        )

        now_btn = types.InlineKeyboardButton(
            f"{page + 1}/{max_page + 1}",
            callback_data=f"{prefix}#select#{0 if page > 0 else max_page}",
        )

        next_btn = (
            types.InlineKeyboardButton(
                "Вперед", callback_data=f"{prefix}#select#{page + 1}"
            )
            if page < max_page
            else None
        )

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


@bot.callback_query_handler(func=lambda call: "edit_time" in call.data)
def edit_time(call):
    list_time = {
        (24 - 8) * 3600: "8:00 в день до напоминания",
        (24 - 12) * 3600: "12:00 в день до напоминания",
        (24 - 18) * 3600: "18:00 в день до напоминания",
        0: "0:00 в день до напоминания",
        (-8) * 3600: "8:00 в день напоминания",
        (-12) * 3600: "12:00 в день напоминания",
        (-18) * 3600: "18:00 в день напоминания",
    }

    if call.data[-1] == "#":
        markup = types.InlineKeyboardMarkup()
        for delta in list_time.keys():
            markup.add(
                types.InlineKeyboardButton(
                    list_time[delta],
                    callback_data=f"edit_time^{delta}",
                )
            )

        bot.edit_message_text(
            "⏰ Выберите время для уведомлений:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
        )

        return

    delta = int(call.data.split("^")[1])

    db.update_user_settings(call.message.chat.id, "remind_delta", delta)

    bot.edit_message_text(
        f"Выбранное время: \n\n{list_time[delta]}",
        call.message.chat.id,
        call.message.message_id,
    )

    return


@bot.message_handler(commands=["settings", "setting", "edit"])
def display_settings(message: types.Message):
    if not db.check_user(message.chat.id):
        db.new_user(message)

    settings_msg = "Изменить время отправки напоминания"
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "Изменить время",
            callback_data="edit_time#",
        )
    )

    send_message(message, settings_msg, markup)

    return

    settings = db.user_settings(message.chat.id)
    # if not settings:
    #     send_message(message, lang["not_registered"])

    #     return

    settings_msg = "⚙️ <u>Настройки</u>:\
        \n\nВремя до отправки уведомления: <b>{}</b>"

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "Изменить время",
            callback_data="edit_time#",
        )
    )

    return


@bot.message_handler(commands=["list", "lists", "l"])
def list_notes(message: types.Message, list: str = "Default", edit: bool = False):
    notes = db.get_notes(message.chat.id, list)

    if not notes:
        send_message(message, lang["no_reminders"])

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

    if edit:
        bot.edit_message_text(
            notes_msg, message.chat.id, message.message_id, reply_markup=markup
        )

        return

    msg = send_message(message, notes_msg, markup)

    reaction = types.ReactionTypeEmoji(random.choice(list_reactions))
    bot.set_message_reaction(
        message.chat.id, message.message_id, [reaction], is_big=True
    )

    old_msg_id = db.new_message(msg)

    if old_msg_id:
        bot.delete_message(message.chat.id, old_msg_id)

    return


@bot.message_handler(content_types=["text"])
def text_message(message: types.Message):
    if message.chat.type == "supergroup" and bot_username not in message.text:

        return  # ignore messages from supergroups

    if not db.check_user(message.chat.id):
        db.new_user(message)

    if not message.text:
        return

    mes_text = message.text
    mes_entities = message.entities

    if not message.text.replace(f"{bot_username}", "").strip():
        if not message.reply_to_message:
            return
        mes_text = message.reply_to_message.text
        mes_entities = message.reply_to_message.entities

    text = mes_text
    html_parts = []
    last_idx = 0
    for ent in mes_entities:
        if ent.type == "text_link":
            html_parts.append(text[last_idx : ent.offset])
            link_text = text[ent.offset : ent.offset + ent.length]
            html_parts.append(f'<a href="{ent.url}">{link_text}</a>')
            last_idx = ent.offset + ent.length

    html_parts.append(text[last_idx:])
    msg_text = "".join(html_parts)

    msg_text = msg_text.replace(f"{bot_username}", "").strip()

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
        for month_from, month_to in month_mapping.items():
            if month_from in date_str:
                date_str = date_str.replace(month_from, month_to)
                break
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
        match = re.search(pattern, msg_text, re.IGNORECASE)
        if match:
            date_found_dt = translate_date_to_datetime(match.group())

            break

    if date_found_dt:
        if date_found_dt < datetime.now():
            date_found_dt = date_found_dt.replace(year=datetime.now().year + 1)

    db.add_note(
        message.chat.id,
        msg_text,
        date_found_dt,
    )

    reaction = types.ReactionTypeEmoji(random.choice(list_reactions))

    bot.set_message_reaction(
        message.chat.id, message.message_id, [reaction], is_big=True
    )
    send_message(message, "📝 Напоминание добавлено:")
    list_notes(message)

    return


def send_message(
    message: types.Message, text, markup=None, thread_id=None
) -> types.Message:
    id = message.chat.id

    if not thread_id:
        thread_id = message.message_thread_id

    msg = None

    try:
        msg = bot.send_message(
            chat_id=id,
            text=text,
            message_thread_id=thread_id,
            reply_markup=markup,
        )
    except Exception as e:
        time.sleep(5)
        try:
            msg = bot.send_message(
                chat_id=id,
                text=text,
                message_thread_id=thread_id,
                reply_markup=markup,
            )
        except Exception as e:
            text_error = "\tError from user {}: \n{}\n\t---\n".format(id, str(e))
            print(f"--- {text_error} ---")

    return msg


def send_admin_message(text):
    text += f"\n\ncalled by:{inspect.stack()[1][3]}"
    bot.send_message(admin_id, f"🛑 {text}")

    return


if __name__ == "__main__":
    print("-------------------------")

    threading.Thread(
        target=bot.infinity_polling,
        name="bot_infinity_polling",
        daemon=True,
    ).start()

    while True:  # keep alive
        chat_id, list, ind_note = db.check_old_notes()

        if chat_id:
            note = db.get_notes(chat_id, list)["notes"][ind_note]

            db.delete_note(chat_id, ind_note, list)

            msg = bot.send_message(
                chat_id,
                f"❌ {note['text']} \n(Уведомление: {datetime.strptime(note['time_notif'], '%Y-%m-%d %H:%M:%S').strftime('%d %B %Y')})",
                timeout=1,
            )

            list_notes(msg, list)

        time.sleep(15)
