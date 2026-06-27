"""Apply the reviewed IMP-054 State Package v2 conversation support patch."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one source pattern, found {count}")
    file.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    replace_once(
        "src/doll/state_package_registry.py",
        '''    AuthoritativeRecordCategory(
        "model_binding",
        "records/model-bindings.jsonl",
        False,
        "model_binding",
    ),
)''',
        '''    AuthoritativeRecordCategory(
        "model_binding",
        "records/model-bindings.jsonl",
        False,
        "model_binding",
    ),
    AuthoritativeRecordCategory(
        "conversation",
        "records/conversations.jsonl",
        False,
        "conversation",
    ),
    AuthoritativeRecordCategory(
        "conversation_event",
        "records/conversation-events.jsonl",
        False,
        "conversation_event",
    ),
)''',
    )

    package = "src/doll/state_package.py"
    replace_once(
        package,
        '''    StateError,
    _utc_now,
''',
        '''    StateCorruptError,
    StateError,
    _utc_now,
''',
    )
    replace_once(
        package,
        "from doll.state_repository import StateRepository, _validate_record_fields\n",
        '''from doll.state_repository import (
    StateRepository,
    _conversation_event_from_envelope,
    _conversation_from_envelope,
    _validate_record_fields,
)
''',
    )
    replace_once(
        package,
        '''    "model_binding": _binding_from_record,
}''',
        '''    "model_binding": _binding_from_record,
    "conversation": _conversation_from_envelope,
    "conversation_event": _conversation_event_from_envelope,
}''',
    )
    replace_once(
        package,
        '''        SettingsCorruptError,
        TruthCorruptError,
''',
        '''        SettingsCorruptError,
        StateCorruptError,
        TruthCorruptError,
''',
    )
    replace_once(
        package,
        '''    _validate_work_item_package_graph(records)
    _validate_procedure_package_graph(records)
    _validate_checkpoint_package_graph(records)


def _validate_work_item_package_graph''',
        '''    _validate_conversation_package_graph(records)
    _validate_work_item_package_graph(records)
    _validate_procedure_package_graph(records)
    _validate_checkpoint_package_graph(records)


def _validate_conversation_package_graph(records: dict[str, RecordEnvelope]) -> None:
    conversations = {
        record.id: _conversation_from_envelope(record)
        for record in records.values()
        if record.record_type == "conversation"
    }
    events = {
        record.id: _conversation_event_from_envelope(record)
        for record in records.values()
        if record.record_type == "conversation_event"
    }
    graph: dict[str, tuple[str, ...]] = {}
    for event in events.values():
        if event.conversation_id not in conversations:
            raise StatePackageValidationError(
                "conversation event references a missing conversation"
            )
        for parent_id in event.parent_event_ids:
            parent = events.get(parent_id)
            if parent is None:
                raise StatePackageValidationError(
                    "conversation event references a missing parent"
                )
            if parent.conversation_id != event.conversation_id:
                raise StatePackageValidationError(
                    "conversation event parent crosses conversation scope"
                )
        graph[event.event_id] = event.parent_event_ids

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(event_id: str) -> None:
        if event_id in visiting:
            raise StatePackageValidationError("conversation event graph contains a cycle")
        if event_id in visited:
            return
        visiting.add(event_id)
        for parent_id in graph.get(event_id, ()):
            visit(parent_id)
        visiting.remove(event_id)
        visited.add(event_id)

    for event_id in graph:
        visit(event_id)


def _validate_work_item_package_graph''',
    )

    replace_once(
        "tests/test_state_package_registry.py",
        '''        "model_binding",
    }''',
        '''        "model_binding",
        "conversation",
        "conversation_event",
    }''',
    )
    replace_once(
        "tests/test_state_package_registry.py",
        '''        "records/model-bindings.jsonl",
    }''',
        '''        "records/model-bindings.jsonl",
        "records/conversations.jsonl",
        "records/conversation-events.jsonl",
    }''',
    )
    replace_once(
        "tests/test_state_package_v2.py",
        '''        "records/model-bindings.jsonl",
    ):
''',
        '''        "records/model-bindings.jsonl",
        "records/conversations.jsonl",
        "records/conversation-events.jsonl",
    ):
''',
    )
    replace_once(
        "tests/test_state_package_v2.py",
        '''        "model_binding",
    ):
''',
        '''        "model_binding",
        "conversation",
        "conversation_event",
    ):
''',
    )


if __name__ == "__main__":
    main()
