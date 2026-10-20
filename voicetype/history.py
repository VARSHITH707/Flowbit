"""Transcript history in a local SQLite file. Raw audio is never stored."""
import csv
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .config import data_dir


@dataclass
class Entry:
    id: int
    ts: float
    text: str
    language: str
    duration: float
    model: str
    raw: str = ""


class History:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "history.db"
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("PRAGMA secure_delete = ON")  # overwrite deleted rows so removed text is not left in the file
        self.db.execute("CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY, ts REAL NOT NULL, "
                        "text TEXT NOT NULL, language TEXT, duration REAL, model TEXT)")
        if "raw" not in {r[1] for r in self.db.execute("PRAGMA table_info(entries)")}:
            self.db.execute("ALTER TABLE entries ADD COLUMN raw TEXT DEFAULT ''")  # older history files
        self.db.commit()

    def add(self, text: str, language: str = "", duration: float = 0.0, model: str = "", raw: str = "") -> int:
        cur = self.db.execute("INSERT INTO entries (ts, text, language, duration, model, raw) VALUES (?,?,?,?,?,?)",
                              (time.time(), text, language, duration, model, raw))
        self.db.commit()
        return cur.lastrowid

    def list(self, query: str = "", limit: int = 500) -> list[Entry]:
        like = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        rows = self.db.execute("SELECT id, ts, text, language, duration, model, COALESCE(raw, '') FROM entries "
                               "WHERE text LIKE ? ESCAPE '\\' ORDER BY ts DESC, id DESC LIMIT ?", (like, limit)).fetchall()
        return [Entry(*r) for r in rows]

    def delete(self, entry_id: int) -> None:
        self.db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self.db.commit()

    def clear(self) -> None:
        self.db.execute("DELETE FROM entries")
        self.db.commit()
        self.db.execute("VACUUM")  # actually remove the deleted text from the file

    def prune(self, days: int) -> int:
        if days <= 0:
            return 0
        cur = self.db.execute("DELETE FROM entries WHERE ts < ?", (time.time() - days * 86400,))
        self.db.commit()
        return cur.rowcount

    def export(self, dest: Path, fmt: str = "json") -> Path:
        """Write to a new/overwritten file chosen by the user. fmt: json | csv | txt."""
        dest = Path(dest)
        if dest.is_dir():
            raise ValueError("Export path is a directory")
        entries = self.list(limit=10**9)
        if fmt == "json":
            dest.write_text(json.dumps([e.__dict__ for e in entries], indent=2, ensure_ascii=False), encoding="utf-8")
        elif fmt == "csv":
            with dest.open("w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["id", "timestamp", "language", "duration_s", "model", "text"])
                w.writerows([e.id, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e.ts)), e.language, e.duration, e.model, e.text] for e in entries)
        elif fmt == "txt":
            dest.write_text("\n\n".join(f"[{time.strftime('%Y-%m-%d %H:%M', time.localtime(e.ts))}] {e.text}" for e in entries), encoding="utf-8")
        else:
            raise ValueError(f"Unknown format {fmt!r}")
        return dest

    def close(self) -> None:
        self.db.close()
