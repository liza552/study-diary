import datetime as dt

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.database import db
from app.security import current_user_id

router = APIRouter(prefix="/api", tags=["data"])

GRADES = {"Отлично": 5, "Хорошо": 4, "Удовлетворительно": 3}
LESSON_COLORS = {"Лекция": "ok", "Практическая": "soon", "Лабораторная": "late"}


def uid(authorization: str | None = Header(default=None)) -> int:
    return current_user_id(authorization)


def rows(sql: str, args: tuple = ()):
    conn = db()
    result = [dict(r) for r in conn.execute(sql, args).fetchall()]
    conn.close()
    return result


def run(sql: str, args: tuple = ()):
    conn = db()
    conn.execute(sql, args)
    conn.commit()
    conn.close()
    return {"ok": True}


class LessonIn(BaseModel):
    weekday: int
    time_from: str
    time_to: str
    title: str
    kind: str = "Лекция"


class NoteIn(BaseModel):
    date: str
    text: str


class ProfileIn(BaseModel):
    name: str
    full_name: str
    city: str
    college: str
    years: str
    grp: str
    about: str


class ExamIn(BaseModel):
    subject: str
    date: str


class GradeIn(BaseModel):
    grade: str


class TeacherIn(BaseModel):
    name: str
    subject: str


# ---------- Расписание ----------
@router.get("/schedule")
def schedule(weekday: int, user_id: int = Depends(uid)):
    return rows(
        "SELECT id, time_from, time_to, title, kind, color FROM lessons WHERE user_id = ? AND weekday = ? ORDER BY id",
        (user_id, weekday),
    )


@router.post("/schedule")
def add_lesson(body: LessonIn, user_id: int = Depends(uid)):
    return run(
        "INSERT INTO lessons (user_id, weekday, time_from, time_to, title, kind, color) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, body.weekday, body.time_from, body.time_to, body.title.strip(), body.kind,
         LESSON_COLORS.get(body.kind, "ok")),
    )


@router.delete("/schedule/{lesson_id}")
def delete_lesson(lesson_id: int, user_id: int = Depends(uid)):
    return run("DELETE FROM lessons WHERE id = ? AND user_id = ?", (lesson_id, user_id))


# ---------- День ----------
@router.get("/day")
def day(date: str, user_id: int = Depends(uid)):
    note = rows("SELECT text FROM notes WHERE user_id = ? AND date = ?", (user_id, date))
    return {
        "note": note[0]["text"] if note else "",
        "tasks": rows("SELECT id, title, done, status FROM tasks WHERE user_id = ? AND due = ? ORDER BY id", (user_id, date)),
        "exams": rows("SELECT id, subject FROM exams WHERE user_id = ? AND date = ?", (user_id, date)),
        "files": rows("SELECT id, name FROM files WHERE user_id = ? AND date = ? ORDER BY id", (user_id, date)),
    }


@router.put("/day/note")
def save_note(body: NoteIn, user_id: int = Depends(uid)):
    conn = db()
    conn.execute("DELETE FROM notes WHERE user_id = ? AND date = ?", (user_id, body.date))
    if body.text.strip():
        conn.execute("INSERT INTO notes (user_id, date, text) VALUES (?, ?, ?)", (user_id, body.date, body.text.strip()))
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Профиль ----------
@router.get("/profile")
def profile(user_id: int = Depends(uid)):
    return rows("SELECT name, full_name, city, college, years, grp, about FROM users WHERE id = ?", (user_id,))[0]


@router.put("/profile")
def save_profile(body: ProfileIn, user_id: int = Depends(uid)):
    return run(
        "UPDATE users SET name=?, full_name=?, city=?, college=?, years=?, grp=?, about=? WHERE id=?",
        (body.name, body.full_name, body.city, body.college, body.years, body.grp, body.about, user_id),
    )


# ---------- Экзамены ----------
@router.get("/exams")
def exams(user_id: int = Depends(uid)):
    r = rows("SELECT id, subject, date, grade FROM exams WHERE user_id = ? ORDER BY date", (user_id,))
    return {"upcoming": [x for x in r if not x["grade"]], "passed": [x for x in r if x["grade"]]}


@router.post("/exams")
def add_exam(body: ExamIn, user_id: int = Depends(uid)):
    try:
        dt.date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(422, "Неверная дата")
    return run("INSERT INTO exams (user_id, subject, date) VALUES (?, ?, ?)", (user_id, body.subject.strip(), body.date))


@router.post("/exams/{exam_id}/grade")
def grade_exam(exam_id: int, body: GradeIn, user_id: int = Depends(uid)):
    if body.grade not in GRADES:
        raise HTTPException(422, "Неверная оценка")
    return run("UPDATE exams SET grade = ? WHERE id = ? AND user_id = ?", (body.grade, exam_id, user_id))


@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: int, user_id: int = Depends(uid)):
    return run("DELETE FROM exams WHERE id = ? AND user_id = ?", (exam_id, user_id))


# ---------- Преподаватели ----------
@router.get("/teachers")
def teachers(user_id: int = Depends(uid)):
    return rows("SELECT id, name, subject FROM teachers ORDER BY id")


@router.post("/teachers")
def add_teacher(body: TeacherIn, user_id: int = Depends(uid)):
    return run("INSERT INTO teachers (name, subject) VALUES (?, ?)", (body.name.strip(), body.subject.strip()))


@router.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, user_id: int = Depends(uid)):
    return run("DELETE FROM teachers WHERE id = ?", (teacher_id,))


# ---------- Статистика ----------
@router.get("/stats")
def stats(user_id: int = Depends(uid)):
    conn = db()
    total = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ?", (user_id,)).fetchone()[0]
    done = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND done = 1", (user_id,)).fetchone()[0]
    grades = [r["grade"] for r in conn.execute("SELECT grade FROM exams WHERE user_id = ? AND grade IS NOT NULL", (user_id,))]
    upcoming = conn.execute("SELECT COUNT(*) FROM exams WHERE user_id = ? AND grade IS NULL", (user_id,)).fetchone()[0]
    conn.close()
    scores = [GRADES[g] for g in grades if g in GRADES]
    return {
        "tasks_total": total,
        "tasks_done": done,
        "exams_passed": len(grades),
        "exams_upcoming": upcoming,
        "avg_grade": round(sum(scores) / len(scores), 2) if scores else None,
    }