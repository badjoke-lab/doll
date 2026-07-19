from pathlib import Path

path = Path("src/doll/local_writing.py")
text = path.read_text(encoding="utf-8")

old = '''        selected_service = SelectedWritingContextService(self.repository)
        try:
            selected_plan = selected_service.plan(
                memory_ids=memory_ids,
                project_ids=project_ids,
                decision_ids=decision_ids,
            )
            selected_service.require_unused(
                operation_id=safe_operation_id,
                plan=selected_plan,
            )
        except SelectedWritingContextValidationError as exc:
            raise LocalWritingWorkflowValidationError(
                "selected writing context is invalid"
            ) from exc
'''
new = '''        selected_service = SelectedWritingContextService(self.repository)
        bundle_service = ResumeBundleWritingContextService(self.repository)
        try:
            selected_plan = selected_service.plan(
                memory_ids=memory_ids,
                project_ids=project_ids,
                decision_ids=decision_ids,
            )
            bundle_plan = bundle_service.plan(resume_bundle_path)
            if len(selected_plan.snapshots) + int(bundle_plan.selected) > MAX_SELECTED_CONTEXT_ITEMS:
                raise LocalWritingWorkflowValidationError(
                    "selected writing context exceeds the configured item limit"
                )
            if (
                selected_plan.character_count + bundle_plan.character_count
                > MAX_SELECTED_CONTEXT_CHARS
            ):
                raise LocalWritingWorkflowValidationError(
                    "selected writing context exceeds the configured character limit"
                )
            selected_service.require_unused(
                operation_id=safe_operation_id,
                plan=selected_plan,
            )
            bundle_service.require_unused(
                operation_id=safe_operation_id,
                plan=bundle_plan,
            )
        except (
            SelectedWritingContextValidationError,
            ResumeBundleWritingContextValidationError,
        ) as exc:
            raise LocalWritingWorkflowValidationError(
                "selected writing context is invalid"
            ) from exc
'''
if text.count(old) != 1:
    raise SystemExit("selected-plan integration target not found exactly once")
text = text.replace(old, new, 1)

old = '''        try:
            selected_result = selected_service.materialize(
                conversation_id=conversation_id,
                operation_id=safe_operation_id,
                plan=selected_plan,
            )
        except SelectedWritingContextValidationError as exc:
            raise LocalWritingWorkflowValidationError(
                "selected writing context could not be prepared"
            ) from exc

        effective_sensitivity = maximum_writing_sensitivity(
            sensitivity,
            selected_result.required_sensitivity,
        )
        context_instruction_ids = source_instruction_ids + selected_result.instruction_ids
'''
new = '''        try:
            selected_result = selected_service.materialize(
                conversation_id=conversation_id,
                operation_id=safe_operation_id,
                plan=selected_plan,
            )
            bundle_result = bundle_service.materialize(
                conversation_id=conversation_id,
                operation_id=safe_operation_id,
                plan=bundle_plan,
            )
        except (
            SelectedWritingContextValidationError,
            ResumeBundleWritingContextValidationError,
        ) as exc:
            raise LocalWritingWorkflowValidationError(
                "selected writing context could not be prepared"
            ) from exc

        effective_sensitivity = maximum_writing_sensitivity(
            sensitivity,
            selected_result.required_sensitivity,
        )
        effective_sensitivity = maximum_writing_sensitivity(
            effective_sensitivity,
            bundle_result.required_sensitivity,
        )
        context_instruction_ids = (
            source_instruction_ids
            + selected_result.instruction_ids
            + bundle_result.instruction_ids
        )
'''
if text.count(old) != 1:
    raise SystemExit("materialization integration target not found exactly once")
text = text.replace(old, new, 1)

old = "                selected_decision_count=len(selected_result.decision_ids),\n            ),\n"
new = (
    "                selected_decision_count=len(selected_result.decision_ids),\n"
    "                selected_resume_bundle_count=int(bundle_result.project_id is not None),\n"
    "            ),\n"
)
if text.count(old) != 1:
    raise SystemExit("render-call target not found exactly once")
text = text.replace(old, new, 1)

old = "            selected_result=selected_result,\n            local_result=local_result,\n"
new = (
    "            selected_result=selected_result,\n"
    "            bundle_result=bundle_result,\n"
    "            local_result=local_result,\n"
)
if text.count(old) != 1:
    raise SystemExit("result-call target not found exactly once")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("IMP-067 local-writing part 2 applied")
