"""
SQLite 数据库操作层
"""
import sqlite3
import hashlib
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from app.config import Config
from app.models import compute_status


def get_db() -> sqlite3.Connection:
    """获取数据库连接（每次调用返回新连接，线程安全）"""
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    """初始化数据库表结构"""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS competitions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                type TEXT DEFAULT 'CTF',
                format TEXT DEFAULT '未知',
                mode TEXT DEFAULT '线上',
                reg_start TEXT,
                reg_end TEXT,
                comp_start TEXT NOT NULL,
                comp_end TEXT NOT NULL,
                link TEXT NOT NULL,
                organizer TEXT,
                status TEXT NOT NULL,
                detail TEXT,
                is_manual INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_status ON competitions(status);
            CREATE INDEX IF NOT EXISTS idx_comp_start ON competitions(comp_start);
            CREATE INDEX IF NOT EXISTS idx_source ON competitions(source);
            CREATE INDEX IF NOT EXISTS idx_manual ON competitions(is_manual);

            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)


def competition_id(name: str, source: str, comp_start: str) -> str:
    """生成唯一 ID"""
    raw = f"{name}|{source}|{comp_start}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def upsert_competition(data: dict) -> bool:
    """
    插入或更新一条比赛记录。
    返回 True 表示新增，False 表示更新。
    """
    data['id'] = competition_id(
        data.get('name', ''),
        data.get('source', 'manual'),
        data.get('comp_start', '')
    )
    data['status'] = compute_status(
        data.get('reg_start'),
        data.get('reg_end'),
        data.get('comp_start'),
        data.get('comp_end'),
    )
    data['updated_at'] = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id, is_manual FROM competitions WHERE id = ?",
            (data['id'],)
        ).fetchone()

        if existing:
            # 手动录入的记录优先，不被自动采集覆盖
            if existing['is_manual'] == 1 and data.get('is_manual', 0) == 0:
                return False
            conn.execute("""
                UPDATE competitions SET
                    name=?, source=?, type=?, format=?, mode=?,
                    reg_start=?, reg_end=?, comp_start=?, comp_end=?,
                    link=?, organizer=?, status=?, detail=?,
                    is_manual=?, updated_at=?
                WHERE id=?
            """, (
                data['name'], data['source'], data.get('type', 'CTF'),
                data.get('format', '未知'), data.get('mode', '线上'),
                data.get('reg_start'), data.get('reg_end'),
                data['comp_start'], data['comp_end'],
                data['link'], data.get('organizer'),
                data['status'], data.get('detail', ''),
                data.get('is_manual', 0), data['updated_at'],
                data['id']
            ))
            return False
        else:
            conn.execute("""
                INSERT INTO competitions
                    (id, name, source, type, format, mode,
                     reg_start, reg_end, comp_start, comp_end,
                     link, organizer, status, detail,
                     is_manual, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data['id'], data['name'], data['source'],
                data.get('type', 'CTF'), data.get('format', '未知'),
                data.get('mode', '线上'),
                data.get('reg_start'), data.get('reg_end'),
                data['comp_start'], data['comp_end'],
                data['link'], data.get('organizer'),
                data['status'], data.get('detail', ''),
                data.get('is_manual', 0), data['updated_at'],
            ))
            return True


def get_competitions(status=None, source=None, search=None,
                     type_filter=None, mode_filter=None,
                     offset=0, limit=200):
    with get_db() as conn:
        where = "WHERE 1=1"
        params = []

        if status:
            where += " AND status = ?"
            params.append(status)
        if source:
            where += " AND source = ?"
            params.append(source)
        if search:
            where += " AND name LIKE ?"
            params.append(f"%{search}%")
        if type_filter:
            where += " AND type = ?"
            params.append(type_filter)
        if mode_filter:
            where += " AND mode = ?"
            params.append(mode_filter)

        total = conn.execute(
            f"SELECT COUNT(*) FROM competitions {where}", params
        ).fetchone()[0]

        sql = f"SELECT * FROM competitions {where} ORDER BY CASE status WHEN 'registering' THEN 0 WHEN 'ongoing' THEN 1 WHEN 'upcoming' THEN 2 ELSE 3 END, comp_start ASC LIMIT ? OFFSET ?"
        rows = conn.execute(sql, params + [limit, offset]).fetchall()
        return [dict(r) for r in rows], total


def get_competition_by_id(cid: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM competitions WHERE id = ?", (cid,)
        ).fetchone()
        return dict(row) if row else None


def delete_competition(cid: str) -> bool:
    """删除比赛"""
    with get_db() as conn:
        cur = conn.execute("DELETE FROM competitions WHERE id = ?", (cid,))
        return cur.rowcount > 0


def get_stats() -> dict:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM competitions").fetchone()[0]
        by_status = {
            row['status']: row['cnt']
            for row in conn.execute(
                "SELECT status, COUNT(*) as cnt FROM competitions GROUP BY status"
            ).fetchall()
        }
        manual = conn.execute(
            "SELECT COUNT(*) FROM competitions WHERE is_manual = 1"
        ).fetchone()[0]
        last_update = conn.execute(
            "SELECT MAX(updated_at) FROM competitions"
        ).fetchone()[0]
        return {
            'total': total,
            'upcoming': by_status.get('upcoming', 0),
            'ongoing': by_status.get('ongoing', 0),
            'ended': by_status.get('finished', 0) + by_status.get('ended', 0),
            'registering': by_status.get('registering', 0),
            'manual': manual,
            'last_update': last_update,
        }


def get_stats_by_source() -> list[dict]:
    """Return count per source, ordered by count descending."""
    with get_db() as conn:
        return [
            dict(r) for r in conn.execute(
                "SELECT source, COUNT(*) as cnt FROM competitions GROUP BY source ORDER BY cnt DESC"
            ).fetchall()
        ]


def get_recent_competitions(limit: int = 10) -> list[dict]:
    """Return most recently updated competitions."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM competitions ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def create_admin_user(username: str, password: str) -> bool:
    pw_hash = generate_password_hash(password)
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
                (username, pw_hash)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def verify_admin(username: str, password: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM admin_users WHERE username = ?",
            (username,)
        ).fetchone()
        if row:
            return check_password_hash(row['password_hash'], password)
        return False


def update_admin_password(username: str, new_password: str) -> bool:
    pw_hash = generate_password_hash(new_password)
    with get_db() as conn:
        conn.execute(
            "UPDATE admin_users SET password_hash = ?, updated_at = datetime('now') WHERE username = ?",
            (pw_hash, username)
        )
        conn.commit()
        return conn.total_changes > 0


def get_admin_user(username: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, created_at, updated_at FROM admin_users WHERE username = ?",
            (username,)
        ).fetchone()
        return dict(row) if row else None


def admin_user_count() -> int:
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0]
