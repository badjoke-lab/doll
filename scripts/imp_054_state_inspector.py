"""Inspect IMP-054 canonical state without constructing a runtime adapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from doll import state
from doll.instruction_origin import InstructionOriginService
from doll.memory import ConfirmedMemoryService
from doll.model_manifest import ModelManifestService
from doll.portability import PortabilityState
from doll.project_state import ProjectService
from doll.project_status import ProjectStatusService


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace")
    parser.add_argument("descriptor")
    return parser.parse_args()


def _record_count(repository: state.StateRepository, record_type: str) -> int:
    row = repository.connection.execute(
        "SELECT COUNT(*) FROM records WHERE record_type = ? AND status = 'active'",
        (record_type,),
    ).fetchone()
    return cast(int, row[0])


def _artifact_has_switch_probe(
    repository: state.StateRepository,
    workspace_root: Path,
    conversation_id: str,
) -> bool:
    marker = b"DOLL_SWITCH_OK"
    for event in repository.list_conversation_events(conversation_id):
        if event.content_reference is None:
            continue
        artifact_id = event.content_reference.removeprefix("artifact:")
        record = repository.get_record(artifact_id)
        managed_path = record.metadata.get("managed_path")
        if not isinstance(managed_path, str):
            return True
        path = workspace_root / "artifacts" / managed_path
        try:
            if marker in path.read_bytes():
                return True
        except OSError:
            return True
    return False


def inspect(workspace_root: Path, descriptor_path: Path) -> tuple[dict[str, bool], dict[str, int]]:
    descriptor: dict[str, Any] = json.loads(descriptor_path.read_text(encoding="utf-8"))
    required = {
        "memory_id",
        "memory_revision",
        "project_id",
        "project_revision",
        "source_environment_id",
        "source_environment_revision",
        "conversation_id",
        "expected_event_count",
        "scope_type",
        "scope_key",
        "runtime_manifest_id",
        "primary_model_manifest_id",
        "fallback_model_manifest_id",
        "primary_binding_id",
        "fallback_binding_id",
    }
    if set(descriptor) != required:
        raise RuntimeError("invalid runtime-continuity descriptor")

    with state.open_state_repository(workspace_root, read_only=True) as repository:
        memory = ConfirmedMemoryService(repository).get(cast(str, descriptor["memory_id"]))
        project = ProjectService(repository).get(cast(str, descriptor["project_id"]))
        environment = PortabilityState(repository).get_source_environment(
            cast(str, descriptor["source_environment_id"])
        )
        source_environment_envelope = repository.get_record(environment.environment_id)
        events = repository.list_conversation_events(cast(str, descriptor["conversation_id"]))
        manifests = ModelManifestService(repository)
        active, runtime, active_model = manifests.resolve_active_binding(
            scope_type=cast(str, descriptor["scope_type"]),
            scope_key=cast(str, descriptor["scope_key"]),
        )
        primary_binding = manifests.get_binding(cast(str, descriptor["primary_binding_id"]))
        fallback_binding = manifests.get_binding(cast(str, descriptor["fallback_binding_id"]))
        primary_model = manifests.get_model(
            cast(str, descriptor["primary_model_manifest_id"])
        )
        fallback_model = manifests.get_model(
            cast(str, descriptor["fallback_model_manifest_id"])
        )
        project_status = ProjectStatusService(repository).build(project.project_id)
        runtime_origins = tuple(
            item
            for item in InstructionOriginService(repository).list(limit=100)
            if item.origin_class == "runtime_output"
        )
        repository_status = repository.status()
        counts = {
            "conversation_events": len(events),
            "runtime_outputs": len(runtime_origins),
            "runtime_manifests": _record_count(repository, "runtime_manifest"),
            "model_manifests": _record_count(repository, "model_manifest"),
            "model_bindings": _record_count(repository, "model_binding"),
            "memories": _record_count(repository, "memory"),
            "projects": _record_count(repository, "project"),
            "source_environments": _record_count(repository, "source_environment"),
        }
        checks = {
            "schema_version_unchanged": repository_status.schema_version == 3,
            "memory_preserved": memory.revision == descriptor["memory_revision"],
            "project_preserved": project.revision == descriptor["project_revision"],
            "source_environment_preserved": (
                source_environment_envelope.revision
                == descriptor["source_environment_revision"]
            ),
            "project_checkpoint_current": (
                project_status.latest_checkpoint is not None
                and project_status.latest_checkpoint.freshness == "current"
            ),
            "canonical_event_count": len(events) == descriptor["expected_event_count"],
            "canonical_event_shape": all(
                event.event_kind in {
                    "user_message",
                    "system_context_snapshot",
                    "assistant_message",
                }
                for event in events
            ),
            "all_turns_completed": (
                len(events) % 3 == 0
                and sum(event.event_kind == "assistant_message" for event in events)
                == len(events) // 3
            ),
            "runtime_outputs_data_only": bool(runtime_origins)
            and all(
                item.data_only is True and item.authority_class == "untrusted_data"
                for item in runtime_origins
            ),
            "runtime_manifest_preserved": (
                runtime.runtime_manifest_id == descriptor["runtime_manifest_id"]
            ),
            "model_manifests_preserved": {
                primary_model.model_manifest_id,
                fallback_model.model_manifest_id,
            }
            == {
                descriptor["primary_model_manifest_id"],
                descriptor["fallback_model_manifest_id"],
            },
            "fallback_binding_active": (
                active.binding_id == descriptor["fallback_binding_id"]
                and fallback_binding.binding_state == "active"
                and active_model.model_manifest_id
                == descriptor["fallback_model_manifest_id"]
            ),
            "primary_binding_rolled_back": (
                primary_binding.binding_state == "rolled_back"
                and primary_binding.rollback_target_id == descriptor["fallback_binding_id"]
            ),
            "switch_probe_not_persisted": not _artifact_has_switch_probe(
                repository,
                workspace_root,
                cast(str, descriptor["conversation_id"]),
            ),
            "record_counts_present": all(value >= 1 for value in counts.values()),
        }
    return checks, counts


def main() -> int:
    arguments = _arguments()
    try:
        checks, counts = inspect(Path(arguments.workspace), Path(arguments.descriptor))
        if not all(checks.values()):
            raise RuntimeError("runtime-continuity inspection failed")
        payload: dict[str, object] = {
            "result": "pass",
            "checks": checks,
            "counts": counts,
        }
    except BaseException as exc:
        payload = {"result": "fail", "error_class": type(exc).__name__}
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
