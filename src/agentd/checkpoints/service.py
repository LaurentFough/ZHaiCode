"""Trusted orchestration: authorize, capture, publish, verify, then fence registration."""

from pathlib import Path

from agentd.git.checkpoint import GitCheckpoint, canonical_remote
from agentd.leases.model import ProtocolError
from agentd.protocol import validate
from agentd.state.postgres import PostgresState


def create_checkpoint(state: PostgresState, repository: Path, checkpoint_id: str,
                      handoff: dict, *, remote: str = "origin", included_untracked=(),
                      quiesced: bool = False) -> dict:
    validate("handoff", handoff)
    project = state.authorize_checkpoint(handoff)
    git = GitCheckpoint(repository, remote)
    if canonical_remote(project["repository_url"], git.repository) != canonical_remote(
            git.remote_url, git.repository):
        raise ProtocolError("PROJECT_REMOTE_MISMATCH")
    checkpoint = git.capture(checkpoint_id, handoff, included_untracked, quiesced=quiesced)
    #= Expiry between this check and push may leave an orphan ref, never a stale DB pointer.
    state.authorize_checkpoint(handoff)
    checkpoint = git.publish(checkpoint)
    state.checkpoint(checkpoint, handoff, handoff["from_machine"], handoff["from_agent"])
    return checkpoint
