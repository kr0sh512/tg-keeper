import yaml, os
from datetime import datetime, timedelta
from telebot import types

config = yaml.safe_load(open("config.yaml"))
users_path = config["users_path"]
user_path = config["user_path"]


def check_user(user_id: int) -> dict:
    users = yaml.safe_load(open(users_path, "r", encoding="utf-8"))

    if not users:
        users = {}

    if user_id in users:
        return users[user_id]

    return None


def new_user(message: types.Message) -> bool:
    if check_user(message.chat.id):
        return False

    update_user_settings(message.chat.id, "id", message.chat.id)
    update_user_settings(message.chat.id, "type", message.chat.type)
    update_user_settings(message.chat.id, "username", message.chat.username)
    update_user_settings(message.chat.id, "first_name", message.chat.first_name)
    update_user_settings(message.chat.id, "last_name", message.chat.last_name)
    update_user_settings(
        message.chat.id, "time_created", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    update_user_settings(message.chat.id, "last_message", None)
    update_user_settings(
        message.chat.id, "remind_delta", 12 * 60 * 60
    )  # 12 часов по умолчанию

    return


def add_note(
    id: int, text: str, time_notif: datetime = None, list: str = "Default"
) -> bool:
    if not check_user(id):
        return False

    notes = (
        yaml.safe_load(open(user_path.format(id), "r", encoding="utf-8"))
        if os.path.exists(user_path.format(id))
        else {}
    )

    if list not in notes:
        notes[list] = {"name": list, "description": "Стандартный список", "notes": []}

    notes[list]["notes"].append(
        {
            "text": text,
            "time_notif": str(time_notif) if time_notif else None,
            "time_created": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        }
    )

    if True:  # TODO: edit sorting
        import functools

        def comp(x, y):
            if not x["time_notif"] and not y["time_notif"]:
                return 0
            elif not x["time_notif"]:
                return -1
            elif not y["time_notif"]:
                return 1
            else:
                x_time = datetime.strptime(
                    x["time_notif"],
                    "%Y-%m-%d %H:%M:%S",
                )
                y_time = datetime.strptime(
                    y["time_notif"],
                    "%Y-%m-%d %H:%M:%S",
                )
                if x_time > y_time:
                    return 1
                elif x_time < y_time:
                    return -1
            return 0

        notes[list]["notes"].sort(
            key=lambda x: datetime.strptime(
                x["time_created"],
                "%Y-%m-%d %H:%M:%S",
            ),
            reverse=True,
        )

        notes[list]["notes"].sort(
            key=functools.cmp_to_key(comp),
        )

    yaml_data = yaml.dump(
        notes,
        default_flow_style=False,
        encoding="utf-8",
        allow_unicode=True,
        width=float("inf"),
        sort_keys=False,
    )

    with open(user_path.format(id), "wb") as file:
        file.write(yaml_data)

    return True


def get_notes(id: int, list="Default") -> dict:
    if not check_user(id):
        return None

    if not os.path.exists(user_path.format(id)):
        return None

    notes = yaml.safe_load(open(user_path.format(id), "r", encoding="utf-8"))

    return notes[list] if list in notes else None


def delete_note(id, note_ind, list="Default") -> bool:
    if not check_user(id):
        return False

    if not os.path.exists(user_path.format(id)):
        return False

    notes = yaml.safe_load(open(user_path.format(id), "r", encoding="utf-8"))

    if list not in notes:
        return False

    if note_ind >= len(notes[list]["notes"]):
        return False

    notes[list]["notes"].pop(note_ind)

    yaml_data = yaml.dump(
        notes,
        default_flow_style=False,
        encoding="utf-8",
        allow_unicode=True,
        width=float("inf"),
        sort_keys=False,
    )

    with open(user_path.format(id), "wb") as file:
        file.write(yaml_data)

    return True


def new_message(message: types.Message) -> int:
    id = message.chat.id
    new_msg_id = message.message_id

    if not check_user(id):
        return None

    users = yaml.safe_load(open(users_path, "r", encoding="utf-8"))

    user = users[id]

    if "last_message" not in user:
        user["last_message"] = None

    last_id = user["last_message"]
    user["last_message"] = new_msg_id

    users[id] = user

    yaml_data = yaml.dump(
        users,
        default_flow_style=False,
        encoding="utf-8",
        allow_unicode=True,
        width=float("inf"),
        sort_keys=False,
    )

    with open(users_path, "wb") as file:
        file.write(yaml_data)

    return last_id


def check_old_notes() -> list[int, str, int]:  # возвращает первую устаревшую заметку
    users = yaml.safe_load(open(users_path, "r", encoding="utf-8"))

    for user_id in users.keys():
        notes = yaml.safe_load(open(user_path.format(user_id), "r", encoding="utf-8"))

        if "remind_delta" not in users[user_id]:
            users[user_id]["remind_delta"] = 12 * 60 * 60  # не сохранится!

        timedt = timedelta(seconds=users[user_id]["remind_delta"])

        for list in notes.keys():
            for ind in range(len(notes[list]["notes"])):
                if (
                    notes[list]["notes"][ind]["time_notif"]
                    and datetime.strptime(
                        notes[list]["notes"][ind]["time_notif"], "%Y-%m-%d %H:%M:%S"
                    )
                    - timedt
                    < datetime.now()
                ):
                    return user_id, list, ind

    return None, None, None


def update_user_settings(user_id: int, param: str, value: any) -> bool:
    users = yaml.safe_load(open(users_path, "r", encoding="utf-8"))

    if not users:
        users = {}

    if user_id not in users:
        users[user_id] = {}

    users[user_id][param] = value

    yaml_data = yaml.dump(
        users,
        default_flow_style=False,
        encoding="utf-8",
        allow_unicode=True,
        width=float("inf"),
        sort_keys=False,
    )

    with open(users_path, "wb") as file:
        file.write(yaml_data)

    return True


def user_settings(user_id: int) -> dict:
    if not check_user(user_id):
        return None

    users = yaml.safe_load(open(users_path, "r", encoding="utf-8"))

    return users[user_id]
