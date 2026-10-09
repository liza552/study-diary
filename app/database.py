import sqlite3
import secrets
import datetime as dt

from app.security import hash_password

DB_FILE = "diary.db"


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def status_for(due: str) -> str:
    """Цвет задачи по сроку: late — срок истекает, soon — скоро, ok — есть время."""
    left = (dt.date.fromisoformat(due) - dt.date.today()).days
    return "late" if left <= 2 else "soon" if left <= 7 else "ok"


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT UNIQUE NOT NULL,
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT, full_name TEXT, city TEXT, college TEXT,
    years TEXT, grp TEXT, about TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    due TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'task',
    status TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    weekday INTEGER NOT NULL,
    time_from TEXT NOT NULL,
    time_to TEXT NOT NULL,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    color TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    date TEXT NOT NULL,
    grade TEXT
);
CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    subject TEXT NOT NULL
);
"""


def seed(conn):
    today = dt.date.today()
    day = lambda n: (today + dt.timedelta(days=n)).isoformat()

    salt = secrets.token_hex(8)
    conn.execute(
        "INSERT INTO users (login, salt, password_hash, name, full_name, city, college, years, grp, about)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "student", salt, hash_password("1234", salt),
            "Иванов Иван", "Иванов Иван Иванович", "Новосибирск",
            "Новосибирский авиационный технический колледж имени Б.С. Галущака",
            "2024-2026", "-",
            "Здесь может быть небольшой текст о вас, ваших целях и интересах",
        ),
    )

    # Задачи: сентябрь 2026 как в макете + несколько на ближайшие дни
    conn.executemany(
        "INSERT INTO tasks (user_id, title, due, kind, status, done) VALUES (1, ?, ?, 'task', ?, ?)",
        [
            ("Прочитать методичку", "2026-09-27", "ok", 1),
            ("Сдать лабораторную №4", "2026-09-27", "soon", 0),
            ("Оформить конспект в тетради", "2026-09-27", "ok", 0),
            ("Лаб №4", "2026-09-29", "late", 0),
            ("Сдать лабораторную №5", day(2), "late", 0),
            ("Подготовить доклад", day(6), "soon", 0),
            ("Курсовая: введение", day(15), "ok", 0),
        ],
    )
    conn.execute(
        "INSERT INTO notes (user_id, date, text) VALUES (1, '2026-09-27', ?)",
        ("Лекция по базам данных: нормальные формы, 1НФ-3НФ.",),
    )
    conn.execute("INSERT INTO files (user_id, date, name) VALUES (1, '2026-09-27', 'Требования_ЛР3.pdf')")

    # Расписание Пн-Пт
    lessons = [
        ("8:30", "10:20", "Базы данных", "Лекция", "ok"),
        ("10:20", "12:00", "Веб-разработка", "Практическая", "soon"),
        ("12:30", "14:00", "Философия", "Лекция", "late"),
        ("14:20", "16:00", "1С", "Практическая", "ok"),
    ]
    for weekday in range(5):
        for l in lessons:
            conn.execute(
                "INSERT INTO lessons (user_id, weekday, time_from, time_to, title, kind, color)"
                " VALUES (1, ?, ?, ?, ?, ?, ?)",
                (weekday, *l),
            )

    # Экзамены
    conn.executemany(
        "INSERT INTO exams (user_id, subject, date, grade) VALUES (1, ?, ?, ?)",
        [
            ("Базы данных", day(4), None),
            ("Высшая математика", day(9), None),
            ("Английский язык", day(21), None),
            ("Физика", "2026-09-25", "Отлично"),
            ("ОАП", "2026-09-29", "Хорошо"),
        ],
    )

    conn.executemany(
        "INSERT INTO teachers (name, subject) VALUES (?, ?)",
        [
            ("Громова Валентина Анатольевна", "Элементы высшей математики | программирование 1С"),
            ("Кузьмин Андрей Павлович", "Базы данных"),
            ("Орлова Виктория Сергеевна", "Иностранный язык"),
            ("Соколов Никита Дмитриевич", "Системное программирование"),
            ("Иванов Сергей Анатольевич", "Философия"),
        ],
    )


def init_db():
    conn = db()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        seed(conn)
    conn.commit()
    conn.close()