import datetime as dt

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.database import db, status_for
from app.security import current_user_id

router = APIRouter(prefix="/api", tags=["tasks"])


def uid(authorization: str | None = Header(default=None)) -> int:
    return current_user_id(authorization)


class TaskIn(BaseModel):
    title: str
    due: str


@router.get("/tasks")
def calendar(year: int, month: int, user_id: int = Depends(uid)):
    like = f"{year}-{month:02d}-%"
    conn = db()
    tasks = conn.execute(
        "SELECT id, title, due, kind, status, done FROM tasks WHERE user_id = ? AND due LIKE ? ORDER BY due, id",
        (user_id, like),
    ).fetchall()
    exams = conn.execute(
        "SELECT id, subject, date FROM exams WHERE user_id = ? AND date LIKE ? ORDER BY date",
        (user_id, like),
    ).fetchall()
    conn.close()
    out = [
        {"id": r["id"], "title": r["title"], "date": r["due"], "kind": r["kind"],
         "status": "ok" if r["done"] else r["status"], "done": r["done"]}
        for r in tasks
    ]
    out += [
        {"id": f"e{r['id']}", "title": r["subject"], "date": r["date"], "kind": "exam", "status": "late", "done": 0}
        for r in exams
    ]
    return out


@router.get("/tasks/all")
def all_tasks(user_id: int = Depends(uid)):
    conn = db()
    rows = conn.execute(
        "SELECT id, title, due, status, done FROM tasks WHERE user_id = ? ORDER BY done, due, id", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/tasks")
def add_task(body: TaskIn, user_id: int = Depends(uid)):
    try:
        dt.date.fromisoformat(body.due)
    except ValueError:
        raise HTTPException(422, "Неверная дата")
    conn = db()
    conn.execute(
        "INSERT INTO tasks (user_id, title, due, kind, status, done) VALUES (?, ?, ?, 'task', ?, 0)",
        (user_id, body.title.strip(), body.due, status_for(body.due)),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/tasks/{task_id}/toggle")
def toggle(task_id: int, user_id: int = Depends(uid)):
    conn = db()
    conn.execute("UPDATE tasks SET done = 1 - done WHERE id = ? AND user_id = ?", (task_id, user_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, user_id: int = Depends(uid)):
    conn = db()
    conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    conn.commit()
    conn.close()
    return {"ok": True}