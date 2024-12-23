CREATE type chat_type AS ENUM ('private', 'group', 'supergroup', 'channel');

CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    username TEXT,
    firstname TEXT,
    lastname TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_message BIGINT NOT NULL DEFAULT 0,
    remind_delta BIGINT NOT NULL DEFAULT 21600,
    chat chat_type NOT NULL
);

CREATE Table lists (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id),
    name TEXT NOT NULL,
    discription TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE notes (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id),
    list_id BIGINT NOT NULL REFERENCES lists (id),
    content TEXT NOT NULL,
    remind_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

