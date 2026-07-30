# ruff: noqa: E501
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def update_local_conversation() -> None:
    path = "src/doll/local_conversation.py"
    replace_once(
        path,
        "from doll.model_manifest import (\n",
        "from doll.local_failure_guidance import (\n    LocalFailureGuidance,\n    guidance_for_runtime_failure,\n)\nfrom doll.model_manifest import (\n",
    )
    replace_once(
        path,
        "    runtime_id: str | None = None\n\n\n@dataclass(slots=True)",
        "    runtime_id: str | None = None\n    failure_guidance: LocalFailureGuidance | None = None\n\n\n@dataclass(slots=True)",
    )
    replace_once(
        path,
        '                    "failure_code": result.failure_code,\n                    "finding_count": result.prompt_injection_finding_count,',
        '                    "failure_code": result.failure_code,\n                    "guidance_id": (\n                        result.failure_guidance.guidance_id\n                        if result.failure_guidance is not None\n                        else None\n                    ),\n                    "available_option_count": (\n                        len(result.failure_guidance.available_options)\n                        if result.failure_guidance is not None\n                        else 0\n                    ),\n                    "finding_count": result.prompt_injection_finding_count,',
    )
    replace_once(
        path,
        "        error_event = ConversationEventRecord(\n",
        "        failure_guidance = _failure_guidance(runtime_result)\n        if failure_guidance is None:  # pragma: no cover - completed returned above\n            raise LocalConversationPersistenceError(\n                \"failed local runtime result has no guidance\"\n            )\n        error_event = ConversationEventRecord(\n",
    )
    replace_once(
        path,
        '            extensions={\n                "failure_code": runtime_result.failure_code,\n                "outcome": runtime_result.outcome,\n            },',
        '            extensions={\n                "failure_code": runtime_result.failure_code,\n                "outcome": runtime_result.outcome,\n                "guidance_id": failure_guidance.guidance_id,\n                "guidance_summary": failure_guidance.summary,\n                "available_options": list(failure_guidance.available_options),\n                "state_preserved": failure_guidance.state_preserved,\n                "automatic_action_taken": failure_guidance.automatic_action_taken,\n                "cloud_fallback_used": failure_guidance.cloud_fallback_used,\n            },',
    )
    replace_once(
        path,
        "\n\ndef _result(\n",
        "\n\ndef _failure_guidance(\n    runtime_result: RuntimeGenerationResult,\n) -> LocalFailureGuidance | None:\n    if runtime_result.outcome == \"completed\":\n        return None\n    if runtime_result.failure_code is None:\n        raise LocalConversationPersistenceError(\n            \"failed local runtime result has no failure code\"\n        )\n    return guidance_for_runtime_failure(runtime_result.failure_code)\n\n\ndef _result(\n",
    )
    replace_once(
        path,
        "        failure_code=runtime_result.failure_code,\n        prompt_injection_finding_count=package.prompt_injection_finding_count,",
        "        failure_code=runtime_result.failure_code,\n        failure_guidance=_failure_guidance(runtime_result),\n        prompt_injection_finding_count=package.prompt_injection_finding_count,",
    )


def update_local_conversation_tests() -> None:
    path = "tests/test_local_conversation.py"
    replace_once(
        path,
        "        assert result.failure_code is None\n        assert result.runtime_manifest_id == runtime_id",
        "        assert result.failure_code is None\n        assert result.failure_guidance is None\n        assert result.runtime_manifest_id == runtime_id",
    )
    replace_once(
        path,
        '        assert result.failure_code == "adapter_failure"\n        assert result.assistant_event_id is None',
        '        assert result.failure_code == "adapter_failure"\n        assert result.failure_guidance is not None\n        assert result.failure_guidance.failure_code == "adapter_failure"\n        assert result.failure_guidance.state_preserved is True\n        assert result.failure_guidance.automatic_action_taken is False\n        assert result.failure_guidance.cloud_fallback_used is False\n        assert result.assistant_event_id is None',
    )
    replace_once(
        path,
        '        assert events[-1].extensions == {\n            "failure_code": "adapter_failure",\n            "outcome": "failed",\n        }',
        '        assert events[-1].extensions == {\n            "failure_code": "adapter_failure",\n            "outcome": "failed",\n            "guidance_id": "doll.local-runtime.adapter-failure.v1",\n            "guidance_summary": (\n                "The selected local runtime adapter failed without returning usable "\n                "output."\n            ),\n            "available_options": [\n                "Retry the request locally.",\n                "Inspect local runtime health.",\n                "Manually switch to an approved local fallback binding.",\n            ],\n            "state_preserved": True,\n            "automatic_action_taken": False,\n            "cloud_fallback_used": False,\n        }',
    )
    replace_once(
        path,
        "            assert result.failure_code == expected_code\n            assert (",
        "            assert result.failure_code == expected_code\n            assert result.failure_guidance is not None\n            assert result.failure_guidance.failure_code == expected_code\n            assert result.failure_guidance.state_preserved is True\n            assert result.failure_guidance.automatic_action_taken is False\n            assert result.failure_guidance.cloud_fallback_used is False\n            assert (",
    )
    replace_once(
        path,
        '        assert result.failure_code == "invalid_response"\n\n\ndef test_adapter_declaration_mismatch',
        '        assert result.failure_code == "invalid_response"\n        assert result.failure_guidance is not None\n        assert result.failure_guidance.failure_code == "invalid_response"\n\n\ndef test_adapter_declaration_mismatch',
    )


def main() -> None:
    update_local_conversation()
    update_local_conversation_tests()
    print("IMP-071 runtime guidance integration applied")


if __name__ == "__main__":
    main()
