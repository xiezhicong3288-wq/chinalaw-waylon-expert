"""Disposable SQLite acceleration; Markdown and JSON remain authoritative.

Only standard-library modules are required. Content fingerprints invalidate
the cache even when a sync tool preserves timestamps and file sizes.
"""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile

SCHEMA_VERSION = 2
CORE_FILES = (
    "references/law-index.json", "references/law-catalog.json",
    "scripts/search_law.py", "scripts/law_search_cache.py",
)


def searchable(item: dict, body: str) -> str:
    return " ".join(str(value or "") for value in (
        item["law"], item["articleCn"], item.get("part"), item.get("chapter"),
        item.get("section"), item.get("topic"), body,
    )).casefold()


def source_stamp(root: Path, relative: str) -> list:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts or relative_path.drive:
        raise ValueError("Cache source path escapes the skill directory")
    path = root / relative_path
    stat = path.stat()
    return [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino,
            hashlib.sha256(path.read_bytes()).hexdigest()]


def is_current(connection: sqlite3.Connection, root: Path, check_sources=True) -> bool:
    row = connection.execute("SELECT value FROM metadata WHERE key = 'sources'").fetchone()
    if not row:
        return False
    state = json.loads(row[0])
    return state["schema"] == SCHEMA_VERSION and all(
        source_stamp(root, name) == stamp for name, stamp in state["files"].items()
        if check_sources or name in CORE_FILES
    )


def build_cache(root: Path, destination: Path, load_index, read_articles) -> None:
    # Snapshot metadata before reading content; do not publish a mixed revision.
    initial = {name: source_stamp(root, name) for name in CORE_FILES}
    index = load_index()
    sources = dict(initial)
    for item in index:
        if item["file"] not in sources:
            if not (root / item["file"]).resolve().is_relative_to(root.resolve()):
                raise ValueError("Cache source path escapes the skill directory")
            sources[item["file"]] = source_stamp(root, item["file"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="law-search-", suffix=".sqlite3", dir=destination.parent)
    os.close(fd)
    try:
        with sqlite3.connect(temporary) as connection:
            connection.executescript("""
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY, law_slug TEXT NOT NULL,
                    article INTEGER NOT NULL, suffix INTEGER,
                    payload TEXT NOT NULL, haystack TEXT NOT NULL
                );
                CREATE INDEX article_lookup ON articles(law_slug, article, suffix);
            """)
            # Scope the parser cache to this build, avoiding repeated reads even
            # for an index whose entries interleave more than 32 source files.
            parsed = {}
            for number, item in enumerate(index, 1):
                filename = item["file"]
                if filename not in parsed:
                    parsed[filename] = read_articles(filename)
                body = parsed[filename].get(item["articleCn"], "")
                if not body:
                    raise ValueError(f"索引对应的原文缺失：{filename} {item['articleCn']}")
                connection.execute("INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?)", (
                    number, item["lawSlug"], item["article"], item.get("articleSuffix"),
                    json.dumps(item, ensure_ascii=False), searchable(item, body),
                ))
            # Trigrams preserve Chinese substring searches of >=3 characters.
            # Short terms and Python builds without FTS5 use exact instr() scans.
            fts = False
            try:
                connection.execute("""CREATE VIRTUAL TABLE article_fts USING fts5(
                    haystack, content='articles', content_rowid='id',
                    tokenize='trigram case_sensitive 1')""")
                connection.execute("INSERT INTO article_fts(article_fts) VALUES ('rebuild')")
                fts = True
            except sqlite3.OperationalError:
                connection.execute("DROP TABLE IF EXISTS article_fts")
            if any(source_stamp(root, name) != stamp for name, stamp in sources.items()):
                raise OSError("知识库在构建缓存时发生变化，请重试")
            connection.executemany("INSERT INTO metadata VALUES (?, ?)", (
                ("sources", json.dumps({"schema": SCHEMA_VERSION, "files": sources})),
                ("fts", json.dumps(fts)),
            ))
        connection.close()
        # Atomic replacement means concurrent readers never see a partial build.
        os.replace(temporary, destination)
    finally:
        # sqlite3's context manager commits/rolls back but does not close.
        if "connection" in locals():
            connection.close()
        Path(temporary).unlink(missing_ok=True)


def open_cache(root: Path, load_index, read_articles, rebuild: bool = False,
               check_sources: bool = True) -> sqlite3.Connection:
    destination = root / ".cache" / "law-search.sqlite3"
    if destination.exists() and not rebuild:
        connection = None
        try:
            connection = sqlite3.connect(destination.as_uri() + "?mode=ro", uri=True, timeout=1)
            if is_current(connection, root, check_sources):
                return connection
        except (sqlite3.Error, OSError, ValueError, KeyError, TypeError):
            pass  # Missing, stale, or damaged caches are disposable.
        if connection is not None:
            connection.close()
    if hasattr(read_articles, "cache_clear"):
        read_articles.cache_clear()
    build_cache(root, destination, load_index, read_articles)
    return sqlite3.connect(destination.as_uri() + "?mode=ro", uri=True, timeout=1)


def candidates(connection: sqlite3.Connection, law_slugs: set[str], article=None,
               suffix=None, needles=(), all_laws=False) -> list[dict]:
    conditions, parameters = [], []
    if not all_laws:
        slugs = sorted(law_slugs)
        conditions.append("law_slug IN (" + ",".join("?" for _ in slugs) + ")")
        parameters.extend(slugs)
    if article is not None:
        conditions.extend(("article = ?", "suffix IS ?"))
        parameters.extend((article, suffix))
    if needles:
        fts = json.loads(connection.execute("SELECT value FROM metadata WHERE key = 'fts'").fetchone()[0])
        if fts and all(len(needle) >= 3 and "\0" not in needle for needle in needles):
            # Quote each literal so punctuation never becomes FTS query syntax.
            query = " OR ".join('"' + needle.replace('"', '""') + '"' for needle in needles)
            conditions.append("id IN (SELECT rowid FROM article_fts WHERE article_fts MATCH ?)")
            parameters.append(query)
        conditions.append("(" + " OR ".join("instr(haystack, ?) > 0" for _ in needles) + ")")
        parameters.extend(needles)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    # Preserve original index order and CLI result limits, not relevance ranking.
    return [json.loads(row[0]) for row in connection.execute(
        "SELECT payload FROM articles" + where + " ORDER BY id", parameters,
    )]
