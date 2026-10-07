import time, os, sqlite3
from typing import List, Iterable, Optional, Union
from pathlib import Path
from dataclasses import dataclass


@dataclass
class FileState:
    file_path: str
    file_type: str        # e.g., 'bbclass', 'include', 'recipe'
    layer_name: str       # e.g., 'meta-base'
    recipe_name: str = "" # e.g., 'zlib'
    package_revision: str = "" # e.g., 'r0'
    version_name: str = ""     # e.g., '1.2.13'
    size: int = 0
    mtime_ns: int = 0
    last_checked: float = 0.0

    def __str__(self, verbose=False):
        result = f"{self.file_type}: '{self.recipe_name}' from '{self.layer_name}'"
        if verbose:
            result += f" ( version={self.version_name} )"
        return result

@staticmethod
def get_default_state_cache_path():
    return Path(os.environ["BB_TEMP_DIR"]) / 'filestate_cache.bb'

class SStateCache:
    def __init__(self, db_path: Union[str, Path] = get_default_state_cache_path()):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_state_cache (
                    file_path TEXT PRIMARY KEY,
                    file_type TEXT NOT NULL,
                    layer_name TEXT NOT NULL,
                    recipe_name TEXT,
                    package_revision TEXT,
                    version_name TEXT,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    last_checked REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_layer_type ON file_state_cache(layer_name, file_type);")
            conn.commit()

    @staticmethod
    def _normalize_path(file_path: Union[str, Path]) -> str:
        return str(Path(file_path).resolve())

    @staticmethod
    def _parse_metadata_from_path(file_path: Path) -> dict:
        """
        Implicitly derives file_type, layer_name, recipe_name, and version_name
        from standard directory layouts and naming conventions.
        """
        parts = file_path.parts
        layer_name = "unknown"
        for part in parts:
            if part.startswith("meta-") or part == "meta":
                layer_name = part
                break
        suffix = file_path.suffix.lower()

        # Determine file type
        file_type = "unknown"
        if suffix == ".bbclass":
            file_type = "bbclass"
        elif suffix in (".inc", ".h"):
            file_type = "include"
        elif suffix == ".bb":
            file_type = "recipe"

        recipe_name = ""
        version_name = ""
        package_revision = ""

        # If it's a recipe, extract name and version from filename (e.g., zlib_1.2.13.bb)
        if file_type == "recipe":
            stem = file_path.stem  # e.g., "zlib_1.2.13"
            if "_" in stem:
                recipe_name, version_name = stem.rsplit("_", 1)
            else:
                recipe_name = stem

        # Fallback recipe name from parent directory if naming convention differs
        if not recipe_name and len(parts) > 2 and parts[-2] != "recipes":
            recipe_name = parts[-2]

        return {
            "file_type": file_type,
            "layer_name": layer_name,
            "recipe_name": recipe_name,
            "version_name": version_name,
            "package_revision": package_revision
        }

    def clear_cache(self):
        """Wipes all cached file states, effectively flushing/resetting the cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM file_state_cache;")
            conn.commit()

    def batch_remove_files(self, file_paths: Iterable[Union[str, Path]]):
        """
        Removes multiple file records from the database cache in batch.
        """
        # Normalize all paths and format them as tuples for sqlite3
        norm_paths = [(self._normalize_path(fp),) for fp in file_paths]

        # Avoid executing if the list is empty
        if not norm_paths:
            return

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # executemany efficiently runs the DELETE statement for all items in the batch
            cursor.executemany("DELETE FROM file_state_cache WHERE file_path = ?", norm_paths)
            conn.commit()

    def batch_track_files(self, file_paths: List[Union[str, Path]]):
        """
        Bulk adds or updates a list of files using a single transaction.
        Metadata is implicitly derived for each file path.
        """
        now = time.time()
        rows = []

        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                continue

            norm_path = self._normalize_path(path)
            meta = self._parse_metadata_from_path(path)
            stat = path.stat()

            rows.append((
                norm_path,
                meta["file_type"],
                meta["layer_name"],
                meta["recipe_name"],
                meta["package_revision"],
                meta["version_name"],
                stat.st_size,
                stat.st_mtime_ns,
                now
            ))

        if not rows:
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT INTO file_state_cache (
                    file_path, file_type, layer_name, recipe_name,
                    package_revision, version_name, size, mtime_ns, last_checked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_type = excluded.file_type,
                    layer_name = excluded.layer_name,
                    recipe_name = excluded.recipe_name,
                    package_revision = excluded.package_revision,
                    version_name = excluded.version_name,
                    size = excluded.size,
                    mtime_ns = excluded.mtime_ns,
                    last_checked = excluded.last_checked
            """, rows)
            conn.commit()

    def find_files(
        self,
        layer_name: Optional[str] = None,
        file_type: Optional[str] = None,
        recipe_name: Optional[str] = None
    ) -> List[FileState]:
        """
        Finds multiple files or recipes matching optional criteria.
        If a parameter is None, it is ignored in the query.
        """
        query = "SELECT * FROM file_state_cache WHERE 1=1"
        params = []

        if layer_name is not None:
            query += " AND layer_name = ?"
            params.append(layer_name)

        if file_type is not None:
            query += " AND file_type = ?"
            params.append(file_type)

        if recipe_name is not None:
            # Supports exact match or wildcard matching depending on your needs
            query += " AND (file_path LIKE ? OR recipe_name = ?)"
            params.extend([f"%{recipe_name}%", recipe_name])

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Convert all fetched rows into FileState objects
            return [FileState(**dict(row)) for row in rows]

    def has_file_changed(self, file_path: Union[str, Path]) -> bool:
        path = Path(file_path)
        norm_path = self._normalize_path(path)

        if not path.exists() or not path.is_file():
            return True

        current_stat = path.stat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT size, mtime_ns FROM file_state_cache WHERE file_path = ?", (norm_path,))
            row = cursor.fetchone()

            if not row:
                return True

            cached_size, cached_mtime_ns = row
            return not (cached_size == current_stat.st_size and cached_mtime_ns == current_stat.st_mtime_ns)
