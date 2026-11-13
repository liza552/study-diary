import os
import time
import secrets
import datetime as dt

import pyodbc
from dotenv import load_dotenv

from app.security import hash_password

load_dotenv()
CONN_STR = os.environ.get("DB_CONNECTION", "")


def _py(v):
    """Приводим значения SQL Server к простым типам."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, dt.time):
        return v.strftime("%H:%M")
    return v


class Row(dict):
    def __init__(self, cols, values):
        super().__init__(zip(cols, values))
        self._v = list(values)

    def __getitem__(self, key):
        return self._v[key] if isinstance(key, int) else super().__getitem__(key)


class Cursor:
    def __init__(self, cur):
        self.cur = cur
        self.cols = [d[0] for d in cur.description] if cur.description else []

    def _row(self, r):
        return Row(self.cols, [_py(x) for x in r])

    def fetchall(self):
        return [self._row(r) for r in self.cur.fetchall()]

    def fetchone(self):
        r = self.cur.fetchone()
        return None if r is None else self._row(r)

    def __iter__(self):
        return iter(self.fetchall())


class Conn:
    def __init__(self):
        self.c = pyodbc.connect(CONN_STR)

    def execute(self, sql, args=()):
        cur = self.c.cursor()
        cur.execute(sql, args)
        return Cursor(cur)

    def executemany(self, sql, rows):
        cur = self.c.cursor()
        for r in rows:
            cur.execute(sql, r)

    def commit(self):
        self.c.commit()

    def close(self):
        self.c.close()


def db():
    return Conn()


def status_for(due: str) -> str:
    """Цвет задачи по сроку: late — срок истекает, soon — скоро, ok — есть время."""
    left = (dt.date.fromisoformat(due) - dt.date.today()).days
    return "late" if left <= 2 else "soon" if left <= 7 else "ok"


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
    conn.execute(
        "INSERT INTO files (user_id, date, name) VALUES (1, '2026-09-27', ?)",
        ("Требования_ЛР3.pdf",),
    )

    lessons = [
        ("08:30", "10:20", "Базы данных", "Лекция", "ok"),
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


SCHEMA_SQL = [
    """IF OBJECT_ID('users','U') IS NULL CREATE TABLE users (
        id INT IDENTITY(1,1) PRIMARY KEY, login NVARCHAR(50) NOT NULL UNIQUE,
        salt NVARCHAR(50) NOT NULL, password_hash NVARCHAR(200) NOT NULL,
        name NVARCHAR(100), full_name NVARCHAR(150), city NVARCHAR(100),
        college NVARCHAR(200), years NVARCHAR(20), grp NVARCHAR(20), about NVARCHAR(500))""",
    """IF OBJECT_ID('tasks','U') IS NULL CREATE TABLE tasks (
        id INT IDENTITY(1,1) PRIMARY KEY, user_id INT NOT NULL, title NVARCHAR(200) NOT NULL,
        due DATE NOT NULL, kind NVARCHAR(20) NOT NULL DEFAULT 'task', status NVARCHAR(20) NOT NULL,
        done BIT NOT NULL DEFAULT 0,
        CONSTRAINT FK_tasks_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)""",
    """IF OBJECT_ID('notes','U') IS NULL CREATE TABLE notes (
        id INT IDENTITY(1,1) PRIMARY KEY, user_id INT NOT NULL, [date] DATE NOT NULL,
        [text] NVARCHAR(MAX) NOT NULL,
        CONSTRAINT FK_notes_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)""",
    """IF OBJECT_ID('files','U') IS NULL CREATE TABLE files (
        id INT IDENTITY(1,1) PRIMARY KEY, user_id INT NOT NULL, [date] DATE NOT NULL,
        name NVARCHAR(255) NOT NULL,
        CONSTRAINT FK_files_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)""",
    """IF OBJECT_ID('lessons','U') IS NULL CREATE TABLE lessons (
        id INT IDENTITY(1,1) PRIMARY KEY, user_id INT NOT NULL,
        weekday TINYINT NOT NULL CHECK (weekday BETWEEN 0 AND 6),
        time_from TIME NOT NULL, time_to TIME NOT NULL, title NVARCHAR(150) NOT NULL,
        kind NVARCHAR(30) NOT NULL, color NVARCHAR(10) NOT NULL,
        CONSTRAINT FK_lessons_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)""",
    """IF OBJECT_ID('exams','U') IS NULL CREATE TABLE exams (
        id INT IDENTITY(1,1) PRIMARY KEY, user_id INT NOT NULL, subject NVARCHAR(150) NOT NULL,
        [date] DATE NOT NULL, grade NVARCHAR(30) NULL,
        CONSTRAINT FK_exams_users FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)""",
    """IF OBJECT_ID('teachers','U') IS NULL CREATE TABLE teachers (
        id INT IDENTITY(1,1) PRIMARY KEY, name NVARCHAR(150) NOT NULL, subject NVARCHAR(200) NOT NULL)""",
]


def ensure_database():
    master = CONN_STR.replace("DATABASE=StudyDiary", "DATABASE=master")
    c = pyodbc.connect(master, autocommit=True)
    c.execute("IF DB_ID('StudyDiary') IS NULL CREATE DATABASE StudyDiary")
    c.close()


def init_db():
    for attempt in range(15):
        try:
            ensure_database()
            break
        except pyodbc.Error as e:
            print(f"База данных ещё не готова ({attempt + 1}/15): {e}")
            time.sleep(4)
    else:
        raise RuntimeError("Не удалось подключиться к базе данных")

    conn = db()
    for sql in SCHEMA_SQL:
        conn.execute(sql)
    conn.commit()
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        seed(conn)
    conn.commit()
    conn.close()