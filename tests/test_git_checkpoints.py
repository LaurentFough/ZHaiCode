"""Real Git repositories, local remotes and retained recovery artifacts."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from agentd.checkpoints.service import create_checkpoint
from agentd.git.checkpoint import GitCheckpoint, canonical_remote
from agentd.leases.model import ProtocolError

ROOT = Path(__file__).resolve().parents[1]


def git(path, *args, data=None):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1")
    return subprocess.check_output(["git", "-c", "commit.gpgSign=false", *args],
                                   cwd=path, env=env, input=data, stderr=subprocess.PIPE)


@pytest.fixture
def repositories(workspace):
    repository = workspace / "machine-A"
    remote = workspace / "remote.git"
    repository.mkdir()
    remote.mkdir()
    git(remote, "init", "--bare")
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.name", "ZHaiCode test")
    git(repository, "config", "user.email", "tests@zhaicode.invalid")
    (repository / "tracked.txt").write_text("base\n")
    (repository / ".gitignore").write_text(".runtime/\nignored.txt\n")
    git(repository, "add", ".")
    #= Put a file in HEAD without creating/deleting a working file to test missing tracked data.
    blob = git(repository, "hash-object", "-w", "--stdin", data=b"absent working file\n").strip()
    git(repository, "update-index", "--add", "--cacheinfo", "100644", blob.decode(), "absent.txt")
    git(repository, "commit", "-m", "Base project")
    git(repository, "remote", "add", "origin", str(remote))
    git(repository, "push", "origin", "main")
    (repository / "tracked.txt").write_text("staged version\n")
    git(repository, "add", "tracked.txt")
    (repository / "tracked.txt").write_text("dirty current version\n")
    (repository / "new file.txt").write_text("new untracked work\n")
    (repository / "not-selected.txt").write_text("not selected\n")
    return repository, remote


@pytest.fixture
def handoff():
    return json.loads((ROOT / "examples/handoff.json").read_text())


def capture(repository, handoff, checkpoint_id="CP-1"):
    engine = GitCheckpoint(repository)
    checkpoint = engine.capture(checkpoint_id, handoff, ["new file.txt"], quiesced=True)
    return engine, checkpoint


def test_dirty_snapshot_preserves_branch_index_and_worktree(repositories, handoff):
    repository, remote = repositories
    head = git(repository, "rev-parse", "HEAD")
    index = (repository / ".git/index").read_bytes()
    status = git(repository, "status", "--porcelain", "--untracked-files=all")
    engine, checkpoint = capture(repository, handoff)
    assert "durability" not in checkpoint
    assert git(repository, "show", f"{checkpoint['commit']}:tracked.txt") == b"dirty current version\n"
    assert git(repository, "show", f"{checkpoint['commit']}:new file.txt") == b"new untracked work\n"
    paths = git(repository, "ls-tree", "-r", "--name-only", checkpoint["commit"]).decode().splitlines()
    assert "absent.txt" not in paths
    assert "not-selected.txt" not in paths
    published = engine.publish(checkpoint)
    assert published["durability"] == "REMOTE_VERIFIED"
    assert git(remote, "rev-parse", checkpoint["ref"]).decode().strip() == checkpoint["commit"]
    assert git(repository, "rev-parse", "HEAD") == head
    assert git(remote, "rev-parse", "refs/heads/main") == head
    assert (repository / ".git/index").read_bytes() == index
    assert git(repository, "status", "--porcelain", "--untracked-files=all") == status
    assert engine.read_manifest(checkpoint["commit"])["handoff"] == handoff


def test_fresh_clone_reads_published_work_and_handoff(repositories, handoff):
    repository, remote = repositories
    engine, checkpoint = capture(repository, handoff)
    engine.publish(checkpoint)
    machine_b = repository.parent / "machine-B"
    git(repository.parent, "clone", "--no-checkout", "--branch", "main", str(remote), str(machine_b))
    git(machine_b, "fetch", "origin", checkpoint["ref"])
    worktree = machine_b / "recovered"
    git(machine_b, "worktree", "add", "--detach", str(worktree), checkpoint["commit"])
    assert (worktree / "tracked.txt").read_text() == "dirty current version\n"
    assert (worktree / "new file.txt").read_text() == "new untracked work\n"
    recovered = GitCheckpoint(worktree).read_manifest(checkpoint["commit"])
    assert recovered["handoff"]["next_action"] == handoff["next_action"]
    assert recovered["checkpoint"]["base_commit"] == checkpoint["base_commit"]


def test_operation_retry_keeps_original_snapshot(repositories, handoff):
    repository, _ = repositories
    engine, checkpoint = capture(repository, handoff)
    (repository / "tracked.txt").write_text("later work\n")
    assert engine.capture("CP-1", handoff, ["new file.txt"], quiesced=True) == checkpoint
    assert engine.publish(checkpoint) == engine.publish(checkpoint)
    with pytest.raises(ProtocolError, match="CHECKPOINT_CONFLICT"):
        engine.capture("CP-1", {**handoff, "next_action": "different"}, ["new file.txt"], quiesced=True)


def test_remote_ref_conflict_never_overwrites(repositories, handoff):
    repository, remote = repositories
    engine, checkpoint = capture(repository, handoff)
    git(remote, "update-ref", checkpoint["ref"], checkpoint["base_commit"])
    with pytest.raises(ProtocolError, match="REMOTE_REF_CONFLICT"):
        engine.publish(checkpoint)
    assert engine.remote_commit(checkpoint["ref"]) == checkpoint["base_commit"]


def test_remote_creation_race_is_fenced_by_git(repositories, handoff, monkeypatch):
    repository, remote = repositories
    engine, checkpoint = capture(repository, handoff)
    original = engine._git

    def race(*args, **kwargs):
        if args[0] == "push":
            git(remote, "update-ref", checkpoint["ref"], checkpoint["base_commit"])
        return original(*args, **kwargs)

    monkeypatch.setattr(engine, "_git", race)
    with pytest.raises(ProtocolError, match="GIT_OPERATION_FAILED"):
        engine.publish(checkpoint)
    assert engine.remote_commit(checkpoint["ref"]) == checkpoint["base_commit"]


def test_failed_push_retains_local_checkpoint_for_retry(repositories, handoff):
    repository, remote = repositories
    hook = remote / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\n#= Simulate an unavailable publisher.\nexit 1\n")
    hook.chmod(0o755)
    engine, checkpoint = capture(repository, handoff)
    with pytest.raises(ProtocolError, match="GIT_OPERATION_FAILED"):
        engine.publish(checkpoint)
    assert engine._existing(checkpoint["ref"]) == checkpoint["commit"]
    assert engine.remote_commit(checkpoint["ref"]) is None
    hook.write_text("#!/bin/sh\n#= Permit the retry without removing the hook.\nexit 0\n")
    assert engine.publish(checkpoint)["durability"] == "REMOTE_VERIFIED"


@pytest.mark.parametrize("name,code", [
    (".env", "CAPTURE_PATH_DENIED"), ("../escape", "INVALID_CAPTURE_PATH"),
    ("ignored.txt", "IGNORED_FILE_DENIED"), ("missing.txt", "INCLUDED_FILE_MISSING"),
    (".runtime/leak.txt", "CAPTURE_PATH_DENIED"),
])
def test_capture_path_policy(repositories, handoff, name, code):
    repository, _ = repositories
    (repository / "ignored.txt").write_text("ignored\n")
    engine = GitCheckpoint(repository)
    with pytest.raises(ProtocolError, match=code):
        engine.capture("CP-denied", handoff, [name], quiesced=True)
    assert engine._existing("refs/agents/TASK-001/checkpoints/1/CP-denied") is None


def test_symlink_and_secrets_are_rejected(repositories, handoff):
    repository, _ = repositories
    (repository / "alias").symlink_to(repository / "tracked.txt")
    engine = GitCheckpoint(repository)
    with pytest.raises(ProtocolError, match="SYMLINK_UNSUPPORTED"):
        engine.capture("CP-symlink", handoff, ["alias"], quiesced=True)
    (repository / "token.txt").write_text("ghp_" + "x" * 36)
    with pytest.raises(ProtocolError, match="SECRET_DETECTED"):
        engine.capture("CP-secret", handoff, ["token.txt"], quiesced=True)
    with pytest.raises(ProtocolError, match="SECRET_DETECTED"):
        engine.capture("CP-notes", {**handoff, "next_action": "ghp_" + "x" * 36}, quiesced=True)


def test_required_quiescence_and_detected_mutation(repositories, handoff, monkeypatch):
    repository, _ = repositories
    engine = GitCheckpoint(repository)
    with pytest.raises(ProtocolError, match="QUIESCENCE_REQUIRED"):
        engine.capture("CP-1", handoff)
    original = engine._snapshot
    calls = 0

    def changing(included):
        nonlocal calls
        calls += 1
        if calls == 2:
            (repository / "tracked.txt").write_text("concurrent worker write\n")
        return original(included)

    monkeypatch.setattr(engine, "_snapshot", changing)
    with pytest.raises(ProtocolError, match="WORKTREE_CHANGED"):
        engine.capture("CP-changing", handoff, quiesced=True)
    assert engine._existing("refs/agents/TASK-001/checkpoints/1/CP-changing") is None


def test_lock_prevents_cooperating_writer(repositories, handoff):
    repository, _ = repositories
    engine = GitCheckpoint(repository)
    with engine.worktree_lock():
        with pytest.raises(ProtocolError, match="WORKTREE_BUSY"):
            GitCheckpoint(repository).capture("CP-1", handoff, quiesced=True)


def test_size_limit_before_ref_creation(repositories, handoff, monkeypatch):
    repository, _ = repositories
    monkeypatch.setattr("agentd.git.checkpoint.MAX_FILE_BYTES", 2)
    with pytest.raises(ProtocolError, match="FILE_TOO_LARGE"):
        capture(repository, handoff)


def test_service_never_registers_unverified_ref(repositories, handoff):
    repository, remote = repositories
    hook = remote / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)

    class State:
        def authorize_checkpoint(self, value):
            return {"repository_url": str(remote)}

        def checkpoint(self, *args):
            pytest.fail("unverified checkpoint must not reach operational state")

    with pytest.raises(ProtocolError, match="GIT_OPERATION_FAILED"):
        create_checkpoint(State(), repository, "CP-1", handoff, quiesced=True)


def test_database_failure_keeps_verified_git_ref(repositories, handoff):
    repository, remote = repositories

    class State:
        def authorize_checkpoint(self, value):
            return {"repository_url": str(remote)}

        def checkpoint(self, *args):
            raise ProtocolError("SIMULATED_DATABASE_OUTAGE")

    with pytest.raises(ProtocolError, match="SIMULATED_DATABASE_OUTAGE"):
        create_checkpoint(State(), repository, "CP-1", handoff, quiesced=True)
    engine = GitCheckpoint(repository)
    ref = "refs/agents/TASK-001/checkpoints/1/CP-1"
    assert engine._existing(ref) is not None
    assert engine.remote_commit(ref) == engine._existing(ref)


def test_project_remote_binding(repositories, handoff):
    repository, _ = repositories

    class State:
        def authorize_checkpoint(self, value):
            return {"repository_url": "git@github.com:someone/else.git"}

    with pytest.raises(ProtocolError, match="PROJECT_REMOTE_MISMATCH"):
        create_checkpoint(State(), repository, "CP-1", handoff, quiesced=True)


def test_ssh_https_repository_equivalence():
    assert canonical_remote("git@github.com:LaurentFough/ZHaiCode.git", ROOT) == canonical_remote(
        "https://github.com/LaurentFough/ZHaiCode.git", ROOT)


def test_staged_additions_binary_bytes_and_modes(repositories, handoff):
    repository, _ = repositories
    binary = b"\0\xff\r\ncheckpoint raw bytes"
    (repository / "added.bin").write_bytes(binary)
    (repository / "run.sh").write_text("#!/bin/sh\nprintf ok\n")
    (repository / "run.sh").chmod(0o755)
    git(repository, "add", "added.bin", "run.sh")
    index = (repository / ".git/index").read_bytes()
    engine, checkpoint = capture(repository, handoff)
    assert git(repository, "show", f"{checkpoint['commit']}:added.bin") == binary
    assert git(repository, "ls-tree", checkpoint["commit"], "run.sh").startswith(b"100755 ")
    assert (repository / ".git/index").read_bytes() == index
    assert engine.read_manifest(checkpoint["commit"])["handoff"] == handoff


def test_sparse_worktree_rejected(repositories, handoff):
    repository, _ = repositories
    git(repository, "config", "core.sparseCheckout", "true")
    with pytest.raises(ProtocolError, match="SPARSE_CHECKOUT_UNSUPPORTED"):
        capture(repository, handoff)


def test_remote_verification_failure_is_not_durable(repositories, handoff, monkeypatch):
    repository, _ = repositories
    engine, checkpoint = capture(repository, handoff)
    original = engine.remote_commit
    calls = 0

    def missing_after_push(ref):
        nonlocal calls
        calls += 1
        return original(ref) if calls == 1 else None

    monkeypatch.setattr(engine, "remote_commit", missing_after_push)
    with pytest.raises(ProtocolError, match="REMOTE_VERIFICATION_FAILED"):
        engine.publish(checkpoint)


@pytest.fixture
def checkpoint_state(repositories, handoff):
    from uuid import uuid4

    from agentd.leases.model import Task
    from agentd.state.postgres import PostgresState

    dsn = os.environ.get("ZHAICODE_TEST_DSN")
    if not dsn:
        pytest.skip("ZHAICODE_TEST_DSN required for real Git + PostgreSQL verification")
    state = PostgresState(dsn)
    state.migrate()
    prefix = uuid4().hex[:12]
    state.register("project", dict(schema_version="0.1", project_id=prefix, name="ZHaiCode",
                                   repository_url=str(repositories[1]), default_branch="main",
                                   instructions=["AGENTS.md"]))
    for machine in ("A", "B"):
        state.register("machine", dict(schema_version="0.1", machine_id=prefix + machine,
                                       os="linux", arch="amd64", capabilities=[]))
        state.register("agent", dict(schema_version="0.1", agent_id=prefix + machine,
                                     machine_id=prefix + machine, role="implementer", runtime="test"))
    state.create(Task(prefix, prefix, handoff["objective"]))
    state.mutate(prefix, "claim", machine_id=prefix + "A", agent_id=prefix + "A")
    handoff.update(task_id=prefix, project_id=prefix, from_machine=prefix + "A",
                   from_agent=prefix + "A", handoff_id="HO-" + prefix)
    return state, prefix, handoff


def expire_in_database(state, task_id):
    from datetime import timedelta

    from psycopg.types.json import Jsonb

    from agentd.protocol import task_payload

    payload = task_payload(state.get(task_id))
    with state.connect() as conn:
        now = conn.execute("SELECT clock_timestamp()").fetchone()[0]
        for field, seconds in (("acquired_at", 100), ("heartbeat_at", 90), ("expires_at", 1)):
            payload["lease"][field] = (now - timedelta(seconds=seconds)).isoformat()
        conn.execute("UPDATE tasks SET payload=%s WHERE task_id=%s", (Jsonb(payload), task_id))


@pytest.mark.postgres
def test_real_git_registration_retry_and_new_owner(repositories, checkpoint_state):
    from agentd.state.postgres import PostgresState

    repository, remote = repositories
    state, prefix, handoff = checkpoint_state
    checkpoint = create_checkpoint(state, repository, "CP-" + prefix, handoff,
                                   included_untracked=["new file.txt"], quiesced=True)
    assert state.recovery(prefix)["checkpoint"] == checkpoint
    with pytest.raises(ProtocolError, match="CHECKPOINT_CONFLICT"):
        state.checkpoint({**checkpoint, "commit": "a" * 40}, handoff,
                         handoff["from_machine"], handoff["from_agent"])
    with pytest.raises(ProtocolError, match="HANDOFF_MISMATCH"):
        create_checkpoint(state, repository, "CP-wrong-" + prefix,
                          {**handoff, "project_id": "wrong-project"}, quiesced=True)
    assert create_checkpoint(state, repository, "CP-" + prefix, handoff,
                             included_untracked=["new file.txt"], quiesced=True) == checkpoint
    newer = create_checkpoint(state, repository, "CP-new-" + prefix, handoff, quiesced=True)
    create_checkpoint(state, repository, "CP-" + prefix, handoff,
                      included_untracked=["new file.txt"], quiesced=True)
    assert state.get(prefix).latest_checkpoint == newer["checkpoint_id"]
    with state.connect() as conn:
        count = conn.execute("SELECT count(*) FROM events WHERE task_id=%s AND kind='CHECKPOINT'",
                             (prefix,)).fetchone()[0]
    assert count == 2
    expire_in_database(state, prefix)
    fresh_service = PostgresState(state.dsn)
    resumed = fresh_service.mutate(prefix, "claim", machine_id=prefix + "B", agent_id=prefix + "B")
    assert resumed.generation == 2
    bundle = fresh_service.recovery(prefix)
    machine_b = repository.parent / "independent-machine-B"
    git(repository.parent, "clone", "--no-checkout", "--branch", "main", str(remote), str(machine_b))
    git(machine_b, "fetch", "origin", bundle["checkpoint"]["ref"])
    recovered = machine_b / "recovered"
    git(machine_b, "worktree", "add", "--detach", str(recovered), bundle["checkpoint"]["commit"])
    assert (recovered / "tracked.txt").read_text() == "dirty current version\n"
    assert GitCheckpoint(recovered).read_manifest(bundle["checkpoint"]["commit"])["handoff"] == handoff
    with pytest.raises(ProtocolError, match="STALE_LEASE"):
        create_checkpoint(state, repository, "CP-stale-" + prefix, handoff, quiesced=True)
    assert GitCheckpoint(repository).remote_commit(
        f"refs/agents/{prefix}/checkpoints/1/CP-stale-{prefix}") is None


@pytest.mark.postgres
def test_expiry_after_upload_leaves_orphan_not_operational_pointer(
        repositories, checkpoint_state, monkeypatch):
    repository, _ = repositories
    state, prefix, handoff = checkpoint_state
    original = state.checkpoint

    def expire_before_registration(*args):
        expire_in_database(state, prefix)
        return original(*args)

    monkeypatch.setattr(state, "checkpoint", expire_before_registration)
    with pytest.raises(ProtocolError, match="STALE_LEASE"):
        create_checkpoint(state, repository, "CP-" + prefix, handoff, quiesced=True)
    assert state.get(prefix).latest_checkpoint is None
    engine = GitCheckpoint(repository)
    ref = f"refs/agents/{prefix}/checkpoints/1/CP-{prefix}"
    assert engine._existing(ref) is not None
    assert engine.remote_commit(ref) == engine._existing(ref)


@pytest.mark.postgres
def test_checkpoint_cli_returns_verified_registered_json(
        repositories, checkpoint_state, monkeypatch, capsys):
    from agentctl.__main__ import main

    repository, _ = repositories
    state, prefix, handoff = checkpoint_state
    runtime = repository / ".runtime"
    runtime.mkdir(exist_ok=True)
    path = runtime / "handoff.json"
    path.write_text(json.dumps(handoff))
    monkeypatch.setenv("ZHAICODE_DSN", state.dsn)
    result = main(["checkpoint", "CP-cli-" + prefix, "--repository", str(repository),
                   "--handoff", str(path), "--include-untracked", "new file.txt", "--quiesced"])
    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["durability"] == "REMOTE_VERIFIED"
    assert state.get(prefix).latest_checkpoint == output["checkpoint_id"]
