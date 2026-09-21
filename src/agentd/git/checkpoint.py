"""Durable, create-only Git checkpoint capture for a trusted, quiesced workspace."""

import hashlib
import json
import logging
import os
import re
import stat
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from agentd.leases.model import ProtocolError, identifier
from agentd.protocol import validate

log = logging.getLogger(__name__)
MESSAGE_PREFIX = "ZHaiCode checkpoint v0.1\n\n"
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
DENIED_PARTS = {".git", ".runtime", ".venv", "__pycache__", ".ssh", ".aws", "node_modules"}
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"),
    re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
)


def canonical_remote(value: str, relative_to: Path) -> str:
    """Match SSH/HTTPS spellings of a repository without exposing credential material."""
    if value.startswith("-") or "\n" in value:
        raise ProtocolError("INVALID_REMOTE")
    if re.match(r"^[^/@:]+@[^/:]+:", value):
        host, path = value.split("@", 1)[1].split(":", 1)
        return f"{host.lower()}/{path.lstrip('/').removesuffix('.git')}"
    parsed = urlsplit(value)
    if parsed.scheme in {"ssh", "https", "http"}:
        if not parsed.hostname or parsed.query or parsed.fragment:
            raise ProtocolError("INVALID_REMOTE")
        port = parsed.port
        suffix = f":{port}" if port and port not in {22, 80, 443} else ""
        return f"{parsed.hostname.lower()}{suffix}/{parsed.path.lstrip('/').removesuffix('.git')}"
    if parsed.scheme == "file" and not parsed.netloc:
        return str(Path(unquote(parsed.path)).resolve())
    if parsed.scheme:
        raise ProtocolError("INVALID_REMOTE")
    return str((relative_to / value).resolve())


def scan_content(data: bytes) -> None:
    """Conservative known-secret detection, not a general secret-scanning guarantee."""
    if any(pattern.search(data) for pattern in SECRET_PATTERNS):
        raise ProtocolError("SECRET_DETECTED")


class GitCheckpoint:
    """Raw-byte snapshots; no stash, checkout, merge, user-index writes or cleanup."""

    def __init__(self, repository: Path, remote: str = "origin"):
        self.repository = Path(repository).resolve()
        self.workspace = Path.cwd().resolve()
        if not self.repository.is_relative_to(self.workspace):
            raise ProtocolError("OUTSIDE_PROJECT")
        identifier(remote)
        self.remote = remote
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1")
        top = Path(self._git("rev-parse", "--show-toplevel").decode().strip()).resolve()
        if top != self.repository:
            raise ProtocolError("REPOSITORY_ROOT_REQUIRED")
        common = Path(self._git("rev-parse", "--git-common-dir").decode().strip())
        if not (self.repository / common).resolve().is_relative_to(self.workspace):
            raise ProtocolError("OUTSIDE_PROJECT")
        if self._git("rev-parse", "--is-shallow-repository").strip() != b"false":
            raise ProtocolError("SHALLOW_REPOSITORY_UNSUPPORTED")
        self.runtime = self.repository / ".runtime" / "checkpoints"
        self._inside(self.runtime)
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.hooks = self.runtime / "empty-hooks"
        self._inside(self.hooks)
        self.hooks.mkdir(exist_ok=True)
        if any(self.hooks.iterdir()):
            raise ProtocolError("HOOK_DIRECTORY_NOT_EMPTY")
        self.remote_url = self._git("remote", "get-url", "--push", "--all", remote).decode().strip()
        if not self.remote_url or "\n" in self.remote_url:
            raise ProtocolError("SINGLE_PUSH_REMOTE_REQUIRED")
        locator = canonical_remote(self.remote_url, self.repository)
        if locator.startswith("/") and not Path(locator).is_relative_to(self.workspace):
            raise ProtocolError("OUTSIDE_PROJECT")

    def _inside(self, path: Path):
        if not path.resolve().is_relative_to(self.repository):
            raise ProtocolError("OUTSIDE_PROJECT")
        for part in (path, *path.parents):
            if part == self.repository:
                break
            if part.is_symlink():
                raise ProtocolError("SYMLINK_UNSUPPORTED")

    def _git(self, *args: str, data: bytes | None = None, env: dict | None = None,
             allowed: tuple[int, ...] = (0,)) -> bytes:
        command = ["git", "-c", "gc.auto=0", "-c", "maintenance.auto=false"]
        if hasattr(self, "hooks"):
            command += ["-c", f"core.hooksPath={self.hooks}"]
        try:
            result = subprocess.run(command + list(args), cwd=self.repository,
                                    env={**self.env, **(env or {})}, input=data,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProtocolError("GIT_UNAVAILABLE") from exc
        if result.returncode not in allowed:
            #= Git stderr may contain credential-bearing URLs or captured filenames.
            log.warning("git operation failed operation=%s code=%s", args[0], result.returncode)
            raise ProtocolError("GIT_OPERATION_FAILED")
        return result.stdout

    @contextmanager
    def worktree_lock(self):
        """POSIX advisory lock shared by cooperating writers; caller stops other writers."""
        try:
            import fcntl
        except ImportError as exc:
            raise ProtocolError("USE_POSIX_OR_WSL") from exc
        path = self.runtime / "worktree.lock"
        self._inside(path)
        with path.open("a+b") as stream:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ProtocolError("WORKTREE_BUSY") from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _path(value: str):
        path = PurePosixPath(value)
        if (not value or path.is_absolute() or path.as_posix() != value
                or any(part in {".", ".."} for part in path.parts) or "\\" in value
                or any(ord(char) < 32 for char in value)):
            raise ProtocolError("INVALID_CAPTURE_PATH")
        if (any(part.lower() in DENIED_PARTS for part in path.parts)
                or path.name.lower().startswith(".env")
                or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
                or path.name.lower() in {"id_rsa", "id_ed25519", "credentials", ".netrc"}):
            raise ProtocolError("CAPTURE_PATH_DENIED")

    def _snapshot(self, included: tuple[str, ...]) -> tuple[str, bytes, dict]:
        base = self._git("rev-parse", "HEAD^{commit}").decode().strip()
        if self._git("config", "--bool", "core.sparseCheckout", allowed=(0, 1)).strip() == b"true":
            raise ProtocolError("SPARSE_CHECKOUT_UNSUPPORTED")
        names = set()
        for item in self._git("ls-tree", "-r", "-z", base).split(b"\0"):
            if item:
                metadata, name = item.split(b"\t", 1)
                if metadata.split()[0] not in {b"100644", b"100755"}:
                    raise ProtocolError("FILE_TYPE_UNSUPPORTED")
                names.add(name.decode("utf-8"))
        index = self._git("ls-files", "--stage", "-z")
        for item in index.split(b"\0"):
            if item:
                metadata, name = item.split(b"\t", 1)
                mode, _, stage = metadata.split()
                if stage != b"0":
                    raise ProtocolError("UNMERGED_INDEX")
                if mode not in {b"100644", b"100755"}:
                    raise ProtocolError("FILE_TYPE_UNSUPPORTED")
                names.add(name.decode("utf-8"))
        for name in included:
            self._path(name)
            if name not in names:
                ignored = self._git("check-ignore", "--no-index", "-z", "--stdin",
                                    data=name.encode() + b"\0", allowed=(0, 1))
                if ignored:
                    raise ProtocolError("IGNORED_FILE_DENIED")
        names.update(included)
        if len(names) > 10000:
            raise ProtocolError("TOO_MANY_FILES")
        snapshot = {}
        total = 0
        for name in sorted(names):
            self._path(name)
            path = self.repository / name
            self._inside(path)
            try:
                before = path.lstat()
            except FileNotFoundError:
                if name in included:
                    raise ProtocolError("INCLUDED_FILE_MISSING") from None
                continue
            if not stat.S_ISREG(before.st_mode):
                raise ProtocolError("FILE_TYPE_UNSUPPORTED")
            if before.st_size > MAX_FILE_BYTES:
                raise ProtocolError("FILE_TOO_LARGE")
            with path.open("rb") as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            after = path.lstat()
            if ((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_mode)
                    != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns,
                        after.st_mode)):
                raise ProtocolError("WORKTREE_CHANGED")
            total += len(data)
            if len(data) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                raise ProtocolError("CAPTURE_TOO_LARGE")
            scan_content(data)
            mode = "100755" if before.st_mode & 0o111 else "100644"
            snapshot[name] = (mode, data)
        #= Include exact index bytes in the stability check without refreshing the index.
        index_path = Path(self._git("rev-parse", "--git-path", "index").decode().strip())
        index_path = self.repository / index_path
        index_bytes = index_path.read_bytes() if index_path.exists() else b""
        return base, hashlib.sha256(index + index_bytes).digest(), snapshot

    def _existing(self, ref: str) -> str | None:
        result = self._git("rev-parse", "--verify", "--quiet", ref, allowed=(0, 1))
        return result.decode().strip() or None

    def read_manifest(self, commit: str) -> dict:
        if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
            raise ProtocolError("INVALID_COMMIT")
        message = self._git("show", "-s", "--format=%B", commit).decode()
        if not message.startswith(MESSAGE_PREFIX):
            raise ProtocolError("INVALID_CHECKPOINT_COMMIT")
        try:
            manifest = json.loads(message[len(MESSAGE_PREFIX):])
            validate("handoff", manifest["handoff"])
            validate("checkpoint", {**manifest["checkpoint"], "commit": commit,
                                    "durability": "REMOTE_VERIFIED"})
            if set(manifest) != {"checkpoint", "handoff", "included_untracked"}:
                raise ValueError("unexpected manifest fields")
        except (ValueError, TypeError, KeyError) as exc:
            raise ProtocolError("INVALID_CHECKPOINT_COMMIT") from exc
        return manifest

    def capture(self, checkpoint_id: str, handoff: dict, included_untracked=(), *,
                quiesced: bool = False) -> dict:
        """Create once or recover the exact immutable local operation for a retry."""
        if quiesced is not True:
            raise ProtocolError("QUIESCENCE_REQUIRED")
        identifier(checkpoint_id)
        validate("handoff", handoff)
        if isinstance(included_untracked, (str, bytes)):
            raise ProtocolError("INVALID_CAPTURE_PATH")
        included_untracked = tuple(included_untracked)
        if any(not isinstance(name, str) for name in included_untracked):
            raise ProtocolError("INVALID_CAPTURE_PATH")
        included = tuple(sorted(set(included_untracked)))
        for name in included:
            self._path(name)
        ref = (f"refs/agents/{handoff['task_id']}/checkpoints/"
               f"{handoff['generation']}/{checkpoint_id}")
        with self.worktree_lock():
            existing = self._existing(ref)
            if existing:
                manifest = self.read_manifest(existing)
                if (manifest["handoff"] != handoff
                        or manifest["included_untracked"] != list(included)
                        or manifest["checkpoint"]["checkpoint_id"] != checkpoint_id
                        or manifest["checkpoint"]["ref"] != ref):
                    raise ProtocolError("CHECKPOINT_CONFLICT")
                return {**manifest["checkpoint"], "commit": existing}
            before = self._snapshot(included)
            base, _, snapshot = before
            checkpoint = dict(schema_version="0.1", checkpoint_id=checkpoint_id,
                              task_id=handoff["task_id"], generation=handoff["generation"],
                              base_commit=base, ref=ref, handoff_id=handoff["handoff_id"],
                              created_at=datetime.now(timezone.utc).isoformat())
            manifest = {"checkpoint": checkpoint, "handoff": handoff,
                        "included_untracked": list(included)}
            message = (MESSAGE_PREFIX + json.dumps(manifest, sort_keys=True) + "\n").encode()
            if len(message) > 1024 * 1024:
                raise ProtocolError("HANDOFF_TOO_LARGE")
            scan_content(message)
            attempt = self.runtime / uuid4().hex
            attempt.mkdir()
            env = {"GIT_INDEX_FILE": str(attempt / "index")}
            #= Build from raw scanned bytes, avoiding filters, hooks and all user-index writes.
            self._git("read-tree", "--empty", env=env)
            records = []
            for name, (mode, data) in snapshot.items():
                oid = self._git("hash-object", "-w", "--stdin", "--no-filters", data=data).strip()
                records.append(mode.encode() + b" " + oid + b"\t" + name.encode() + b"\0")
            self._git("update-index", "-z", "--index-info", data=b"".join(records), env=env)
            tree = self._git("write-tree", env=env).decode().strip()
            if self._snapshot(included) != before:
                raise ProtocolError("WORKTREE_CHANGED")
            commit = self._git("commit-tree", tree, "-p", base, data=message,
                               env={"GIT_AUTHOR_NAME": "ZHaiCode checkpoint",
                                    "GIT_AUTHOR_EMAIL": "checkpoint@zhaicode.invalid",
                                    "GIT_COMMITTER_NAME": "ZHaiCode checkpoint",
                                    "GIT_COMMITTER_EMAIL": "checkpoint@zhaicode.invalid"}).decode().strip()
            self._git("update-ref", ref, commit, "0" * len(commit))
            log.info("checkpoint captured task=%s generation=%s checkpoint=%s",
                     handoff["task_id"], handoff["generation"], checkpoint_id)
            return {**checkpoint, "commit": commit}

    def remote_commit(self, ref: str) -> str | None:
        result = self._git("ls-remote", "--refs", "--exit-code", self.remote_url, ref, allowed=(0, 2))
        rows = [row.split() for row in result.decode().splitlines()]
        if not rows:
            return None
        if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != ref:
            raise ProtocolError("REMOTE_VERIFICATION_FAILED")
        return rows[0][0]

    def publish(self, checkpoint: dict) -> dict:
        """Compare-and-create the remote ref; an existing matching ref is a safe retry."""
        validate("checkpoint", {**checkpoint, "durability": "REMOTE_VERIFIED"})
        manifest = self.read_manifest(checkpoint["commit"])
        if {**manifest["checkpoint"], "commit": checkpoint["commit"]} != checkpoint:
            raise ProtocolError("CHECKPOINT_CONFLICT")
        ref = checkpoint["ref"]
        remote_commit = self.remote_commit(ref)
        if remote_commit is not None and remote_commit != checkpoint["commit"]:
            raise ProtocolError("REMOTE_REF_CONFLICT")
        if remote_commit is None:
            #= An empty expected old OID makes this create-only, even if another push races us.
            self._git("push", "--porcelain", "--no-follow-tags", "--recurse-submodules=no",
                      f"--force-with-lease={ref}:", self.remote_url, f"{checkpoint['commit']}:{ref}")
        if self.remote_commit(ref) != checkpoint["commit"]:
            raise ProtocolError("REMOTE_VERIFICATION_FAILED")
        log.info("checkpoint remote verified task=%s checkpoint=%s",
                 checkpoint["task_id"], checkpoint["checkpoint_id"])
        return {**checkpoint, "durability": "REMOTE_VERIFIED"}
