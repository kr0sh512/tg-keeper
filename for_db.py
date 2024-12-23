import yaml, os
from datetime import datetime, timedelta
from telebot import types
from psycopg2 import pool
from sshtunnel import SSHTunnelForwarder

connection_pool: pool.SimpleConnectionPool = None

config = yaml.safe_load(open("config.yaml"))

server = SSHTunnelForwarder(
    (config["host"], 22),
    ssh_private_key="~/.ssh/id_rsa",
    ssh_username="krosh",
    remote_bind_address=("localhost", config["sql_port"]),
)

server.start()
connection_pool = pool.SimpleConnectionPool(
    1,
    5,
    database=config["sql_database"],
    user=config["sql_user"],
    password=config["sql_password"],
    host="localhost",
    port=server.local_bind_port,
)


def into_dict(curs) -> dict:
    cols = [desc[0] for desc in curs.description]
    data = curs.fetchone()

    return dict(zip(cols, data)) if data else None


def into_list(curs) -> list[dict]:
    cols = [desc[0] for desc in curs.description]
    data = curs.fetchall()

    return [dict(zip(cols, row)) for row in data] if data else None


def check_user(user_id: int) -> dict:
    con = connection_pool.getconn()
    curs = con.cursor()
    curs.execute("SELECT * FROM users WHERE id = %s", (user_id,))

    user = into_dict(curs)
    connection_pool.putconn(con)

    return user


def new_user(message: types.Message) -> bool:
    if check_user(message.chat.id):
        return False

    con = connection_pool.getconn()
    curs = con.cursor()
    curs.execute(
        """
        INSERT INTO users (id, username, firstname, lastname, chat)
        VALUES (%s, %s, %s, %s, %s)
    """,
        (
            message.chat.id,
            message.chat.username,
            message.chat.first_name,
            message.chat.last_name,
            message.chat.type,
        ),
    )
    con.commit()
    connection_pool.putconn(con)

    return


def add_note(
    id: int, text: str, remind_at: datetime = None, list: str = "Default"
) -> bool:
    if not check_user(id):
        return False

    con = connection_pool.getconn()
    curs = con.cursor()
    curs.execute(
        """
        SELECT id FROM lists WHERE name = %s AND user_id = %s
    """,
        (list, id),
    )

    data = curs.fetchone()

    if not data:
        curs.execute(
            """
            INSERT INTO lists (name, user_id)
            VALUES (%s, %s)
        """,
            (list, id),
        )
        con.commit()

    curs.execute(
        """
        INSERT INTO notes (user_id, list_id, content, remind_at)
        VALUES (%s, (SELECT id FROM lists WHERE name = %s AND user_id = %s), %s, %s)
    """,
        (id, list, id, text, remind_at),
    )
    con.commit()
    rowcnt = curs.rowcount

    connection_pool.putconn(con)

    return True if rowcnt else False


def get_notes(id: int, list="Default") -> list[dict]:
    if not check_user(id):
        return None

    con = connection_pool.getconn()
    curs = con.cursor()

    curs.execute(
        """
        SELECT * FROM notes
        WHERE user_id = %s AND list_id = (SELECT id FROM lists WHERE name = %s AND user_id = %s)
        ORDER BY remind_at IS NULL DESC, remind_at ASC, created_at DESC
        """,
        (id, list, id),
    )

    notes = into_list(curs)
    connection_pool.putconn(con)

    return notes


def delete_note(id, note_ind, list="Default") -> bool:
    if not check_user(id):
        return False

    con = connection_pool.getconn()
    curs = con.cursor()
    curs.execute(
        """
        DELETE FROM notes
        WHERE user_id = %s AND list_id = (SELECT id FROM lists WHERE name = %s AND user_id = %s)
        ORDER BY remind_at IS NULL DESC, remind_at ASC, created_at DESC
        LIMIT 1 OFFSET %s
    """,
        (id, list, id, note_ind),
    )

    con.commit()
    rowcnt = curs.rowcount
    connection_pool.putconn(con)

    return True if rowcnt else False


def new_message(message: types.Message) -> int:
    id = message.chat.id
    new_msg_id = message.message_id

    if not check_user(id):
        return None

    con = connection_pool.getconn()
    curs = con.cursor()
    curs.execute(
        """
        SELECT last_message FROM users WHERE id = %s
    """,
        (id,),
    )
    last_id = curs.fetchone()[0]

    curs.execute(
        """
        UPDATE users
        SET last_message = %s
        WHERE id = %s
    """,
        (new_msg_id, id),
    )
    con.commit()
    connection_pool.putconn(con)

    return last_id


def check_old_notes() -> list[int, str, int]:  # возвращает первую устаревшую заметку
    con = connection_pool.getconn()
    curs = con.cursor()
    curs.execute(
        """
        SELECT id FROM users
    """
    )
    users = curs.fetchall()

    for user_id in users:
        curs.execute(
            """
            SELECT * FROM notes
            WHERE id = %s
            ORDER BY remind_at IS NULL DESC, remind_at ASC, created_at DESC
        """,
            (user_id,),
        )
        notes = [dict(row) for row in curs.fetchall()]

        if not notes:
            continue

        timedt = timedelta(seconds=user_settings(user_id)["remind_delta"])

        for ind in range(len(notes)):
            if (
                notes[ind]["remind_at"]
                and datetime.strptime(notes[ind]["remind_at"], "%Y-%m-%d %H:%M:%S")
                - timedt
                < datetime.now()
            ):
                curs.execute(
                    """
                    SELECT name FROM lists
                    WHERE id = %s
                """,
                    (notes[ind]["list_id"],),
                )
                list_name = curs.fetchone()
                connection_pool.putconn(con)

                return (user_id, list_name, ind)

    connection_pool.putconn(con)

    return None, None, None


def update_user_settings(user_id: int, param: str, value: any) -> bool:
    con = connection_pool.getconn()
    curs = con.cursor()
    query = f"UPDATE users SET {param} = %s WHERE id = %s"
    curs.execute(query, (value, user_id))
    con.commit()
    rowcnt = curs.rowcount
    connection_pool.putconn(con)

    return True if rowcnt else False


def user_settings(user_id: int) -> dict:
    con = connection_pool.getconn()
    curs = con.cursor()
    curs.execute("SELECT * FROM users WHERE id = %s", (user_id,))

    user = into_dict(curs)
    connection_pool.putconn(con)

    return user
