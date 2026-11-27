# 완성된 일기를 로컬 Markdown 파일로 저장한다. 같은 날에도 덮어쓰지 않는다.

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import os
import re
from uuid import uuid4

KST = timezone(timedelta(hours=9))
DEFAULT_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "diary"
DIARY_FILENAME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{12}_[0-9a-f]{8}\.md")


class DiaryStore:
    def __init__(self, directory=DEFAULT_DIRECTORY):
        self.directory = Path(directory)

    def save(self, day: date, content: str) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(KST).strftime("%H%M%S%f")
        target = self.directory / f"{day.isoformat()}_{stamp}_{uuid4().hex[:8]}.md"
        temporary = target.with_suffix(".tmp")
        try:
            temporary.write_text(f"# {day.isoformat()}\n\n{content.strip()}\n", encoding="utf-8")
            # 기록이 완전히 쓰인 뒤 최종 이름으로 바꿔 미완성 일기가 조회되지 않게 한다.
            temporary.rename(target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def files(self) -> list[Path]:
        # 날짜와 시각이 앞에 붙은 완성 파일만 일기 순서로 조회한다.
        try:
            return sorted(path for path in self.directory.iterdir()
                          if DIARY_FILENAME.fullmatch(path.name) and not path.is_symlink() and path.is_file())
        except FileNotFoundError:
            return []

    def latest(self) -> str | None:
        files = self.files()
        return files[-1].read_text(encoding="utf-8") if files else None

    def update(self, path: Path, expected: str, revised: str) -> bool:
        # 두 프로그램이 같은 일기를 고쳐도 먼저 저장한 내용을 덮어쓰지 않는다.
        if path.parent != self.directory or not DIARY_FILENAME.fullmatch(path.name):
            raise ValueError("Invalid diary path")
        with (self.directory / ".edit.lock").open("a+b") as lock:
            lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if path.is_symlink() or path.read_text(encoding="utf-8") != expected:
                return False
            temporary = path.with_suffix(".edit.tmp")
            try:
                temporary.write_text(revised, encoding="utf-8")
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            return True

    def count(self) -> int:
        return len(self.files())
