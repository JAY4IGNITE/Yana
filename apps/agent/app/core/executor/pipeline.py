"""Execution Pipeline enforcing the YANA Critical Architectural Flow:

USER -> YANA UI -> DESKTOP IPC -> AGENT -> PLANNER -> TOOL REGISTRY
-> PERMISSION MANAGER -> EXECUTOR -> OPERATING SYSTEM -> VERIFIER -> AGENT -> YANA UI

The AI never directly accesses the operating system.
All operations must flow through this controlled pipeline.
"""

from dataclasses import dataclass

from app.core.verifier.base import BaseVerifier, StandardVerifier
from app.errors import PermissionError, ToolError, ValidationError
from app.permissions.manager import PermissionManager, permission_manager
from app.protocol.models import SafeErrorPayload, ToolCall, ToolResult, VerificationResult
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
    ) -> None:
        self.registry = tool_registry or registry
        self.permissions = perm_manager or permission_manager
        self.verifier = verifier or StandardVerifier()

    async def execute_tool_call(self, tool_call: ToolCall) -> PipelineExecutionResult:
        """Execute a requested tool call safely through the pipeline.

        1. Tool Validation: Ensure tool exists and arguments match schema.
        2. Permission Gate: Check risk level and ensure user consent is granted.
        3. Execution: Run tool via executor.
        4. Verification: Validate outcome via verifier.
        """
        # Step 1: Tool Registry lookup & validation
        try:
            tool = self.registry.validate_call(tool_call.tool, tool_call.arguments)
        except ValidationError as e:
            return PipelineExecutionResult(
                tool_result=ToolResult(
                    task_id=tool_call.task_id,
                    tool_call_id=tool_call.id,
                    success=False,
                    output=None,
                    error=SafeErrorPayload(**e.to_safe_payload()),
                ),
                verification=None,
            )

        # Step 2: Permission Manager check
        try:
            self.permissions.enforce_permission(tool, tool_call.id, tool_call.arguments)
        except PermissionError as e:
            return PipelineExecutionResult(
                tool_result=ToolResult(
                    task_id=tool_call.task_id,
                    tool_call_id=tool_call.id,
                    success=False,
                    output=None,
                    error=SafeErrorPayload(**e.to_safe_payload()),
                ),
                verification=None,
            )

        # Step 3: Tool Execution (Executor -> OS/Subsystem)
        try:
            output = await tool.execute(tool_call.arguments)
            success = True
            error_payload = None
        except Exception as e:
            success = False
            output = None
            tool_err = ToolError(
                f"Execution failed for tool '{tool.name}': {str(e)}",
                task_id=tool_call.task_id,
                tool_id=tool.name,
            )
            error_payload = SafeErrorPayload(**tool_err.to_safe_payload())

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

        return PipelineExecutionResult(tool_result=result, verification=verification)


# Global pipeline instance
execution_pipeline = ExecutionPipeline()
