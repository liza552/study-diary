import os
import time
import secrets
import datetime as dt

import psycopg
from dotenv import load_dotenv

from app.security import hash_password

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _py(v):
    """Приводим значения Postgres к простым типам (так их ждет фронтенд)."""
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
        self.cols = [d.name for d in cur.description] if cur.description else []

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
        # prepare_threshold=None отключает подготовленные запросы: так работает и пулер Supabase в режиме Transaction
        self.c = psycopg.connect(DATABASE_URL, prepare_threshold=None)

    def execute(self, sql, args=()):
        cur = self.c.cursor()
        # в запросах проекта параметры записаны как ?, а psycopg ждет %s
        cur.execute(sql.replace("?", "%s"), args)
        return Cursor(cur)

    def executemany(self, sql, rows):
        cur = self.c.cursor()
        for r in rows:
            cur.execute(sql.replace("?", "%s"), r)

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
    uid = conn.execute(
        "INSERT INTO users (login, salt, password_hash, name, full_name, city, college, years, grp, about)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (
            "student", salt, hash_password("1234", salt),
            "Иванов Иван", "Иванов Иван Иванович", "Новосибирск",
            "Новосибирский авиационный технический колледж имени Б.С. Галущака",
            "2024-2026", "-",
            "Здесь может быть небольшой текст о вас, ваших целях и интересах",
        ),
    ).fetchone()[0]

    conn.executemany(
        "INSERT INTO tasks (user_id, title, due, kind, status, done) VALUES (?, ?, ?, 'task', ?, ?)",
        [
            (uid, "Прочитать методичку", "2026-09-27", "ok", True),
            (uid, "Сдать лабораторную №4", "2026-09-27", "soon", False),
            (uid, "Оформить конспект в тетради", "2026-09-27", "ok", False),
            (uid, "Лаб №4", "2026-09-29", "late", False),
            (uid, "Сдать лабораторную №5", day(2), "late", False),
            (uid, "Подготовить доклад", day(6), "soon", False),
            (uid, "Курсовая: введение", day(15), "ok", False),
        ],
    )
    conn.execute(
        "INSERT INTO notes (user_id, note_date, text) VALUES (?, '2026-09-27', ?)",
        (uid, "Лекция по базам данных: нормальные формы, 1НФ-3НФ."),
    )
    conn.execute(
        "INSERT INTO files (user_id, file_date, name) VALUES (?, '2026-09-27', ?)",
        (uid, "Требования_ЛР3.pdf"),
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
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uid, weekday, *l),
            )

    conn.executemany(
        "INSERT INTO exams (user_id, subject, exam_date, grade) VALUES (?, ?, ?, ?)",
        [
            (uid, "Базы данных", day(4), None),
            (uid, "Высшая математика", day(9), None),
            (uid, "Английский язык", day(21), None),
            (uid, "Физика", "2026-09-25", "Отлично"),
            (uid, "ОАП", "2026-09-29", "Хорошо"),
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
    conn = None
    for attempt in range(15):
        try:
            conn = db()
            break
        except psycopg.OperationalError as e:
            print(f"База данных недоступна ({attempt + 1}/15): {e}")
            time.sleep(4)
    if conn is None:
        raise RuntimeError("Не удалось подключиться к базе данных")

    # таблицы созданы в Supabase вручную; если пользователей нет, добавляем демо-данные
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        seed(conn)
    conn.commit()
    conn.close()
