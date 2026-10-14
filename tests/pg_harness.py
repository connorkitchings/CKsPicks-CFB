"""Disposable, socket-only PostgreSQL cluster for database-backed tests.

The cluster is created with ``initdb --auth=trust --no-sync`` inside a pytest
temporary directory and started with ``listen_addresses=''`` so it never binds a
TCP port: clients reach it only through a Unix socket in a private directory.
``stop()`` always shuts the server down and removes every directory it created.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

import psycopg

_PG_BIN_CANDIDATES = (
    "/opt/homebrew/opt/postgresql@14/bin",
    "/opt/homebrew/bin",
    "/usr/local/opt/postgresql@14/bin",
    "/usr/lib/postgresql/14/bin",
)
_PORT = 5432  # Only names the socket file; the socket directory is private.
# macOS limits a socket path to 103 bytes; leave room for "/.s.PGSQL.5432".
_MAX_SOCKET_DIR_LEN = 80


def find_pg_bin() -> Path | None:
    """Return a directory holding ``initdb``, ``pg_ctl`` and ``postgres``."""
    found = shutil.which("initdb")
    candidates = [str(Path(found).parent)] if found else []
    for directory in (*candidates, *_PG_BIN_CANDIDATES):
        path = Path(directory)
        if all((path / tool).is_file() for tool in ("initdb", "pg_ctl", "postgres")):
            return path
    return None


def _socket_dir() -> Path:
    for base in (tempfile.gettempdir(), "/tmp"):
        candidate = Path(tempfile.mkdtemp(prefix="cks-pg-", dir=base))
        if len(str(candidate)) <= _MAX_SOCKET_DIR_LEN:
            return candidate
        candidate.rmdir()
    raise RuntimeError("no temporary directory is short enough for a socket path")


class PgCluster:
    """One throwaway cluster; use ``conninfo``/``connect`` to reach a database."""

    def __init__(self, bin_dir: Path, root: Path) -> None:
        self.bin_dir = bin_dir
        self.root = root
        self.data_dir = root / "data"
        self.log_file = root / "postgres.log"
        self.socket_dir: Path | None = None
        self.superuser = "postgres"

    def start(self) -> None:
        self.socket_dir = _socket_dir()
        self._run(
            "initdb",
            "-D",
            str(self.data_dir),
            "-U",
            self.superuser,
            "--auth=trust",
            "--no-sync",
            "--encoding=UTF8",
            "--locale=C",
        )
        options = (
            "-c listen_addresses='' "
            f"-c unix_socket_directories='{self.socket_dir}' "
            f"-p {_PORT} -c fsync=off -c max_connections=60"
        )
        self._run(
            "pg_ctl",
            "-D",
            str(self.data_dir),
            "-l",
            str(self.log_file),
            "-o",
            options,
            "-w",
            "-t",
            "60",
            "start",
        )

    def stop(self) -> None:
        """Stop the server (forcefully if needed) and delete all of its files."""
        try:
            if (self.data_dir / "postmaster.pid").exists():
                result = subprocess.run(
                    [
                        str(self.bin_dir / "pg_ctl"),
                        "-D",
                        str(self.data_dir),
                        "-m",
                        "immediate",
                        "-w",
                        "-t",
                        "30",
                        "stop",
                    ],
                    capture_output=True,
                    check=False,
                )
                if result.returncode != 0:
                    self._kill_postmaster()
        finally:
            shutil.rmtree(self.root, ignore_errors=True)
            if self.socket_dir is not None:
                shutil.rmtree(self.socket_dir, ignore_errors=True)

    def _kill_postmaster(self) -> None:
        pid_file = self.data_dir / "postmaster.pid"
        try:
            pid = int(pid_file.read_text().splitlines()[0])
        except (OSError, ValueError, IndexError):
            return
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def _run(self, tool: str, *args: str) -> None:
        result = subprocess.run(
            [str(self.bin_dir / tool), *args], capture_output=True, text=True
        )
        if result.returncode != 0:
            log = self.log_file.read_text() if self.log_file.exists() else ""
            raise RuntimeError(
                f"{tool} failed ({result.returncode}): {result.stderr}\n{log}"
            )

    def conninfo(self, dbname: str = "postgres", user: str | None = None) -> str:
        return psycopg.conninfo.make_conninfo(
            host=str(self.socket_dir),
            port=_PORT,
            dbname=dbname,
            user=user or self.superuser,
        )

    def connect(
        self, dbname: str = "postgres", user: str | None = None, **kwargs
    ) -> psycopg.Connection:
        return psycopg.connect(self.conninfo(dbname, user), **kwargs)
