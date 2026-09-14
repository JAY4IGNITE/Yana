"""Execution Pipeline enforcing the YANA Critical Architectural Flow:

USER -> YANA UI -> DESKTOP IPC -> AGENT -> PLANNER -> TOOL REGISTRY
-> PERMISSION MANAGER -> EXECUTOR -> OPERATING SYSTEM -> VERIFIER -> AGENT -> YANA UI

The AI never directly accesses the operating system.
All operations must flow through this controlled pipeline.
"""

import time
from dataclasses import dataclass

from app.core.performance import performance_monitor
from app.core.verifier.base import BaseVerifier, StandardVerifier
from app.errors import ErrorCode, ToolError, ValidationError, YanaBaseError
from app.permissions.manager import PermissionManager, permission_manager
from app.protocol.models import SafeErrorPayload, ToolCall, ToolResult, VerificationResult
from app.security.audit import AuditLogger, audit_logger
from app.tools.registry import ToolRegistry, registry


@dataclass
class PipelineExecutionResult:
    tool_result: ToolResult
    verification: VerificationResult | None


class ExecutionPipeline:
    """Orchestrates tool discovery, permission verification, execution, and result verification."""

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        perm_manager: PermissionManager | None = None,
        verifier: BaseVerifier | None = None,
        audit: AuditLogger | None = None,
    ) -> None:
        self.registry = tool_registry or registry
        self.permissions = perm_manager or permission_manager
        self.verifier = verifier or StandardVerifier()
        self.audit = audit or audit_logger

    async def execute_tool_call(
        self, tool_call: ToolCall, user_request: str | None = None
    ) -> PipelineExecutionResult:
        """Execute a requested tool call safely through the pipeline.

        1. Tool Validation: Ensure tool exists and arguments match schema.
        2. Permission Gate: Check risk level and ensure user consent is granted.
        3. Execution: Run tool via executor.
        4. Verification: Validate outcome via verifier.
        5. Audit: Record tamper-evident sanitized audit trail.
        """
        # Step 1: Tool Registry lookup & validation
        try:
            tool = self.registry.validate_call(tool_call.tool, tool_call.arguments)
        except ValidationError as e:
            err_payload = SafeErrorPayload(**e.to_safe_payload())
            await self.audit.record_event(
                tool=tool_call.tool,
                arguments=tool_call.arguments,
                permission_result="validation_error",
                task_id=tool_call.task_id,
                user_request=user_request,
                execution_result={"error": err_payload.model_dump(by_alias=True)},
            )
            return PipelineExecutionResult(
                tool_result=ToolResult(
                    task_id=tool_call.task_id,
                    tool_call_id=tool_call.id,
                    success=False,
                    output=None,
                    error=err_payload,
                ),
                verification=None,
            )

        # Step 2: Permission Manager authorization check
        decision = self.permissions.authorize(tool, tool_call.id, tool_call.arguments)
        if not decision.granted:
            err_payload = SafeErrorPayload(
                code=ErrorCode.PERMISSION_ERROR,
                message=(
                    f"Permission denied for '{tool.name}' "
                    f"(Risk: {tool.risk_level.value}): {decision.reason}"
                ),
                task_id=tool_call.task_id,
                tool_id=tool.name,
            )
            await self.audit.record_event(
                tool=tool.name,
                arguments=tool_call.arguments,
                permission_result=f"denied: {decision.reason}",
                task_id=tool_call.task_id,
                user_request=user_request,
                execution_result={"error": err_payload.model_dump(by_alias=True)},
            )
            return PipelineExecutionResult(
                tool_result=ToolResult(
                    task_id=tool_call.task_id,
                    tool_call_id=tool_call.id,
                    success=False,
                    output=None,
                    error=err_payload,
                ),
                verification=None,
            )

        # Step 3: Tool Execution (Executor -> OS/Subsystem)
        tool_start = time.perf_counter()
        try:
            output = await tool.execute(tool_call.arguments)
            success = True
            error_payload = None
        except Exception as e:
            success = False
            output = None
            if isinstance(e, YanaBaseError):
                error_payload = SafeErrorPayload(**e.to_safe_payload())
            else:
                tool_err = ToolError(
                    f"Execution failed for tool '{tool.name}': {str(e)}",
                    task_id=tool_call.task_id,
                    tool_id=tool.name,
                )
                error_payload = SafeErrorPayload(**tool_err.to_safe_payload())
        finally:
            tool_dur_ms = (time.perf_counter() - tool_start) * 1000.0
            performance_monitor.record_tool_latency(tool.name, tool_dur_ms)

        result = ToolResult(
            task_id=tool_call.task_id,
            tool_call_id=tool_call.id,
            success=success,
            output=output,
            error=error_payload,
        )

        # Step 4: Verification (Verifier)
        verification = None
        if success:
            if hasattr(tool, "verify") and callable(tool.verify):
                try:
                    verification = await tool.verify(tool_call.arguments, output)
                    verification.task_id = tool_call.task_id
                    verification.tool_call_id = tool_call.id
                except Exception as e:
                    verification = VerificationResult(
                        task_id=tool_call.task_id,
                        tool_call_id=tool_call.id,
                        verified=False,
                        notes=f"Tool verification raised an error: {str(e)}",
                    )
            else:
                verification = await self.verifier.verify(
                    task_id=tool_call.task_id,
                    tool_call_id=tool_call.id,
                    tool_name=tool.name,
                    tool_output=output,
                )

        # Step 5: Audit Log Event Recording
        exec_record = (
            output
            if success
            else ({"error": error_payload.model_dump(by_alias=True)} if error_payload else None)
        )
        verif_record = verification.model_dump(by_alias=True) if verification else None
        await self.audit.record_event(
            tool=tool.name,
            arguments=tool_call.arguments,
            permission_result="granted",
            task_id=tool_call.task_id,
            user_request=user_request,
            execution_result=exec_record,
            verification=verif_record,
        )

        return PipelineExecutionResult(tool_result=result, verification=verification)


# Global pipeline instance
execution_pipeline = ExecutionPipeline()
