import yaml
from datetime import datetime
from telebot import types
import errno, os

users_path = "database/users.yaml"
user_path = "database/users/{}.yaml"


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

    user = {
        "id": message.chat.id,
        "type": message.chat.type,
        "username": message.chat.username,
        "first_name": message.chat.first_name,
        "last_name": message.chat.last_name,
        "time_created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    users = yaml.safe_load(open(users_path, "r"))

    if not users:
        users = {}

    users[user["id"]] = user

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


def add_note(id: int, text: str, time_notif: datetime = None, list: str = "Default"):
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


def get_notes(id, list="Default"):
    if not check_user(id):
        return None

    if not os.path.exists(user_path.format(id)):
        return None

    notes = yaml.safe_load(open(user_path.format(id), "r", encoding="utf-8"))

    return notes[list] if list in notes else None


def delete_note(id, note_ind, list="Default"):
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
