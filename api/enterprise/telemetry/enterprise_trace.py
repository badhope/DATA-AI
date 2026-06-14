"""Enterprise trace handler — duck-typed, NOT a BaseTraceInstance subclass.

Invoked directly in the Celery task, not through OpsTraceManager dispatch.
Only requires a matching ``trace(trace_info)`` method signature.

Signal strategy:
- **Traces (spans)**: workflow run, node execution, draft node execution only.
- **Metrics + structured logs**: all other event types.

Token metric labels (unified structure):
All token metrics (data.tokens.input, data.tokens.output, data.tokens.total) use the
same label set for consistent filtering and aggregation:
- tenant_id: Tenant identifier
- app_id: Application identifier
- operation_type: Source of token usage (workflow | node_execution | message | rule_generate | etc.)
- model_provider: LLM provider name (empty string if not applicable)
- model_name: LLM model name (empty string if not applicable)
- node_type: Workflow node type (empty string if not node_execution)

This unified structure allows filtering by operation_type to separate:
- Workflow-level aggregates (operation_type=workflow)
- Individual node executions (operation_type=node_execution)
- Direct message calls (operation_type=message)
- Prompt generation operations (operation_type=rule_generate, code_generate, etc.)

Without this, tokens are double-counted when querying totals (workflow totals include
node totals, since workflow.total_tokens is the sum of all node tokens).
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from opentelemetry.util.types import AttributeValue

from core.ops.entities.trace_entity import (
    BaseTraceInfo,
    DatasetRetrievalTraceInfo,
    DraftNodeExecutionTrace,
    GenerateNameTraceInfo,
    MessageTraceInfo,
    ModerationTraceInfo,
    OperationType,
    PromptGenerationTraceInfo,
    SuggestedQuestionTraceInfo,
    ToolTraceInfo,
    WorkflowNodeTraceInfo,
    WorkflowTraceInfo,
)
from enterprise.telemetry.entities import (
    EnterpriseTelemetryCounter,
    EnterpriseTelemetryEvent,
    EnterpriseTelemetryHistogram,
    EnterpriseTelemetrySpan,
    TokenMetricLabels,
)
from enterprise.telemetry.telemetry_log import emit_metric_only_event, emit_telemetry_log

logger = logging.getLogger(__name__)


class EnterpriseOtelTrace:
    """Duck-typed enterprise trace handler.

    ``*_trace`` methods emit spans (workflow/node only) or structured logs
    (all other events), plus metrics at 100 % accuracy.
    """

    def __init__(self) -> None:
        from extensions.ext_enterprise_telemetry import get_enterprise_exporter

        exporter = get_enterprise_exporter()
        if exporter is None:
            raise RuntimeError("EnterpriseOtelTrace instantiated but exporter is not initialized")
        self._exporter = exporter

    def trace(self, trace_info: BaseTraceInfo) -> None:
        match trace_info:
            case WorkflowTraceInfo():
                self._workflow_trace(trace_info)
            case MessageTraceInfo():
                self._message_trace(trace_info)
            case ToolTraceInfo():
                self._tool_trace(trace_info)
            case DraftNodeExecutionTrace():
                self._draft_node_execution_trace(trace_info)
            case WorkflowNodeTraceInfo():
                self._node_execution_trace(trace_info)
            case ModerationTraceInfo():
                self._moderation_trace(trace_info)
            case SuggestedQuestionTraceInfo():
                self._suggested_question_trace(trace_info)
            case DatasetRetrievalTraceInfo():
                self._dataset_retrieval_trace(trace_info)
            case GenerateNameTraceInfo():
                self._generate_name_trace(trace_info)
            case PromptGenerationTraceInfo():
                self._prompt_generation_trace(trace_info)
            case _:
                raise AssertionError("this statment should be unreachable")

    def _common_attrs(self, trace_info: BaseTraceInfo) -> dict[str, Any]:
        metadata = self._metadata(trace_info)
        tenant_id, app_id, user_id = self._context_ids(trace_info, metadata)
        return {
            "data.trace_id": trace_info.resolved_trace_id,
            "data.tenant_id": tenant_id,
            "data.app_id": app_id,
            "data.app.name": metadata.get("app_name"),
            "data.workspace.name": metadata.get("workspace_name"),
            "gen_ai.user.id": user_id,
            "data.message.id": trace_info.message_id,
        }

    def _metadata(self, trace_info: BaseTraceInfo) -> dict[str, Any]:
        return trace_info.metadata

    def _context_ids(
        self,
        trace_info: BaseTraceInfo,
        metadata: dict[str, Any],
    ) -> tuple[str | None, str | None, str | None]:
        tenant_id = getattr(trace_info, "tenant_id", None) or metadata.get("tenant_id")
        app_id = getattr(trace_info, "app_id", None) or metadata.get("app_id")
        user_id = getattr(trace_info, "user_id", None) or metadata.get("user_id")
        return tenant_id, app_id, user_id

    def _labels(self, **values: AttributeValue) -> dict[str, AttributeValue]:
        return dict(values)

    def _safe_payload_value(self, value: Any) -> str | dict[str, Any] | list[object] | None:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return cast(dict[str, Any], value)
        if isinstance(value, list):
            items: list[object] = []
            for item in cast(list[object], value):
                items.append(item)
            return items
        return None

    def _content_or_ref(self, value: Any, ref: str) -> Any:
        if self._exporter.include_content:
            return self._maybe_json(value)
        return ref

    def _maybe_json(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError):
            return str(value)

    # ------------------------------------------------------------------
    # SPAN-emitting handlers (workflow, node execution, draft node)
    # ------------------------------------------------------------------

    def _workflow_trace(self, info: WorkflowTraceInfo) -> None:
        metadata = self._metadata(info)
        tenant_id, app_id, user_id = self._context_ids(info, metadata)
        # -- Span attrs: identity + structure + status + timing + gen_ai scalars --
        span_attrs: dict[str, Any] = {
            "data.trace_id": info.resolved_trace_id,
            "data.tenant_id": tenant_id,
            "data.app_id": app_id,
            "data.workflow.id": info.workflow_id,
            "data.workflow.run_id": info.workflow_run_id,
            "data.workflow.status": info.workflow_run_status,
            "data.workflow.error": info.error,
            "data.workflow.elapsed_time": info.workflow_run_elapsed_time,
            "data.invoke_from": metadata.get("triggered_from"),
            "data.conversation.id": info.conversation_id,
            "data.message.id": info.message_id,
            "data.invoked_by": info.invoked_by,
            "gen_ai.usage.total_tokens": info.total_tokens,
            "gen_ai.user.id": user_id,
        }

        trace_correlation_override, parent_span_id_source = info.resolved_parent_context

        parent_ctx = metadata.get("parent_trace_context")
        if isinstance(parent_ctx, dict):
            parent_ctx_dict = cast(dict[str, Any], parent_ctx)
            span_attrs["data.parent.trace_id"] = parent_ctx_dict.get("trace_id")
            span_attrs["data.parent.node.execution_id"] = parent_ctx_dict.get("parent_node_execution_id")
            span_attrs["data.parent.workflow.run_id"] = parent_ctx_dict.get("parent_workflow_run_id")
            span_attrs["data.parent.app.id"] = parent_ctx_dict.get("parent_app_id")

        self._exporter.export_span(
            EnterpriseTelemetrySpan.WORKFLOW_RUN,
            span_attrs,
            correlation_id=info.workflow_run_id,
            span_id_source=info.workflow_run_id,
            start_time=info.start_time,
            end_time=info.end_time,
            trace_correlation_override=trace_correlation_override,
            parent_span_id_source=parent_span_id_source,
        )

        # -- Companion log: ALL attrs (span + detail) for full picture --
        log_attrs: dict[str, Any] = {**span_attrs}
        log_attrs.update(
            {
                "data.app.name": metadata.get("app_name"),
                "data.workspace.name": metadata.get("workspace_name"),
                "gen_ai.user.id": user_id,
                "gen_ai.usage.total_tokens": info.total_tokens,
                "data.workflow.version": info.workflow_run_version,
            }
        )

        ref = f"ref:workflow_run_id={info.workflow_run_id}"
        log_attrs["data.workflow.inputs"] = self._content_or_ref(info.workflow_run_inputs, ref)
        log_attrs["data.workflow.outputs"] = self._content_or_ref(info.workflow_run_outputs, ref)
        log_attrs["data.workflow.query"] = self._content_or_ref(info.query, ref)

        emit_telemetry_log(
            event_name=EnterpriseTelemetryEvent.WORKFLOW_RUN,
            attributes=log_attrs,
            signal="span_detail",
            trace_id_source=info.workflow_run_id,
            span_id_source=info.workflow_run_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        # -- Metrics --
        labels = self._labels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
        )
        token_labels = TokenMetricLabels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
            operation_type=OperationType.WORKFLOW,
            model_provider="",
            model_name="",
            node_type="",
        ).to_dict()
        self._exporter.increment_counter(EnterpriseTelemetryCounter.TOKENS, info.total_tokens, token_labels)
        if info.prompt_tokens is not None and info.prompt_tokens > 0:
            self._exporter.increment_counter(EnterpriseTelemetryCounter.INPUT_TOKENS, info.prompt_tokens, token_labels)
        if info.completion_tokens is not None and info.completion_tokens > 0:
            self._exporter.increment_counter(
                EnterpriseTelemetryCounter.OUTPUT_TOKENS, info.completion_tokens, token_labels
            )
        invoke_from = metadata.get("triggered_from", "")
        self._exporter.increment_counter(
            EnterpriseTelemetryCounter.REQUESTS,
            1,
            self._labels(
                **labels,
                type="workflow",
                status=info.workflow_run_status,
                invoke_from=invoke_from,
            ),
        )
        # Prefer wall-clock timestamps over the elapsed_time field: elapsed_time defaults
        # to 0 in the DB and can be stale if the Celery write races with the trace task.
        # start_time = workflow_run.created_at, end_time = workflow_run.finished_at.
        if info.start_time and info.end_time:
            workflow_duration = (info.end_time - info.start_time).total_seconds()
        elif info.workflow_run_elapsed_time:
            workflow_duration = float(info.workflow_run_elapsed_time)
        else:
            workflow_duration = 0.0
        self._exporter.record_histogram(
            EnterpriseTelemetryHistogram.WORKFLOW_DURATION,
            workflow_duration,
            self._labels(
                **labels,
                status=info.workflow_run_status,
            ),
        )

        if info.error:
            self._exporter.increment_counter(
                EnterpriseTelemetryCounter.ERRORS,
                1,
                self._labels(
                    **labels,
                    type="workflow",
                ),
            )

    def _node_execution_trace(self, info: WorkflowNodeTraceInfo) -> None:
        self._emit_node_execution_trace(info, EnterpriseTelemetrySpan.NODE_EXECUTION, "node")

    def _draft_node_execution_trace(self, info: DraftNodeExecutionTrace) -> None:
        self._emit_node_execution_trace(
            info,
            EnterpriseTelemetrySpan.DRAFT_NODE_EXECUTION,
            "draft_node",
            correlation_id_override=info.node_execution_id,
            trace_correlation_override_param=info.workflow_run_id,
        )

    def _emit_node_execution_trace(
        self,
        info: WorkflowNodeTraceInfo,
        span_name: EnterpriseTelemetrySpan,
        request_type: str,
        correlation_id_override: str | None = None,
        trace_correlation_override_param: str | None = None,
    ) -> None:
        metadata = self._metadata(info)
        tenant_id, app_id, user_id = self._context_ids(info, metadata)
        # -- Span attrs: identity + structure + status + timing + gen_ai scalars --
        span_attrs: dict[str, Any] = {
            "data.trace_id": info.resolved_trace_id,
            "data.tenant_id": tenant_id,
            "data.app_id": app_id,
            "data.workflow.id": info.workflow_id,
            "data.workflow.run_id": info.workflow_run_id,
            "data.message.id": info.message_id,
            "data.conversation.id": metadata.get("conversation_id"),
            "data.node.execution_id": info.node_execution_id,
            "data.node.id": info.node_id,
            "data.node.type": info.node_type,
            "data.node.title": info.title,
            "data.node.status": info.status,
            "data.node.error": info.error,
            "data.node.elapsed_time": info.elapsed_time,
            "data.node.index": info.index,
            "data.node.predecessor_node_id": info.predecessor_node_id,
            "data.node.iteration_id": info.iteration_id,
            "data.node.loop_id": info.loop_id,
            "data.node.parallel_id": info.parallel_id,
            "data.node.invoked_by": info.invoked_by,
            "gen_ai.usage.input_tokens": info.prompt_tokens,
            "gen_ai.usage.output_tokens": info.completion_tokens,
            "gen_ai.usage.total_tokens": info.total_tokens,
            "gen_ai.request.model": info.model_name,
            "gen_ai.provider.name": info.model_provider,
            "gen_ai.user.id": user_id,
        }

        resolved_override, _ = info.resolved_parent_context
        trace_correlation_override = trace_correlation_override_param or resolved_override

        effective_correlation_id = correlation_id_override or info.workflow_run_id
        self._exporter.export_span(
            span_name,
            span_attrs,
            correlation_id=effective_correlation_id,
            span_id_source=info.node_execution_id,
            start_time=info.start_time,
            end_time=info.end_time,
            trace_correlation_override=trace_correlation_override,
        )

        # -- Companion log: ALL attrs (span + detail) --
        log_attrs: dict[str, Any] = {**span_attrs}
        log_attrs.update(
            {
                "data.app.name": metadata.get("app_name"),
                "data.workspace.name": metadata.get("workspace_name"),
                "data.invoke_from": metadata.get("invoke_from"),
                "gen_ai.user.id": user_id,
                "gen_ai.usage.total_tokens": info.total_tokens,
                "data.node.total_price": info.total_price,
                "data.node.currency": info.currency,
                "gen_ai.provider.name": info.model_provider,
                "gen_ai.request.model": info.model_name,
                "gen_ai.tool.name": info.tool_name,
                "data.node.iteration_index": info.iteration_index,
                "data.node.loop_index": info.loop_index,
                "data.plugin.name": metadata.get("plugin_name"),
                "data.credential.name": metadata.get("credential_name"),
                "data.credential.id": metadata.get("credential_id"),
                "data.dataset.ids": self._maybe_json(metadata.get("dataset_ids")),
                "data.dataset.names": self._maybe_json(metadata.get("dataset_names")),
            }
        )

        ref = f"ref:node_execution_id={info.node_execution_id}"
        log_attrs["data.node.inputs"] = self._content_or_ref(info.node_inputs, ref)
        log_attrs["data.node.outputs"] = self._content_or_ref(info.node_outputs, ref)
        log_attrs["data.node.process_data"] = self._content_or_ref(info.process_data, ref)

        emit_telemetry_log(
            event_name=span_name.value,
            attributes=log_attrs,
            signal="span_detail",
            trace_id_source=info.workflow_run_id,
            span_id_source=info.node_execution_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        # -- Metrics --
        labels = self._labels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
            node_type=info.node_type,
            model_provider=info.model_provider or "",
        )
        if info.total_tokens:
            token_labels = TokenMetricLabels(
                tenant_id=tenant_id or "",
                app_id=app_id or "",
                operation_type=OperationType.NODE_EXECUTION,
                model_provider=info.model_provider or "",
                model_name=info.model_name or "",
                node_type=info.node_type,
            ).to_dict()
            self._exporter.increment_counter(EnterpriseTelemetryCounter.TOKENS, info.total_tokens, token_labels)
            if info.prompt_tokens is not None and info.prompt_tokens > 0:
                self._exporter.increment_counter(
                    EnterpriseTelemetryCounter.INPUT_TOKENS, info.prompt_tokens, token_labels
                )
            if info.completion_tokens is not None and info.completion_tokens > 0:
                self._exporter.increment_counter(
                    EnterpriseTelemetryCounter.OUTPUT_TOKENS, info.completion_tokens, token_labels
                )
        self._exporter.increment_counter(
            EnterpriseTelemetryCounter.REQUESTS,
            1,
            self._labels(
                **labels,
                type=request_type,
                status=info.status,
                model_name=info.model_name or "",
            ),
        )
        duration_labels = dict(labels)
        duration_labels["model_name"] = info.model_name or ""
        plugin_name = metadata.get("plugin_name")
        if plugin_name and info.node_type in {"tool", "knowledge-retrieval"}:
            duration_labels["plugin_name"] = plugin_name
        self._exporter.record_histogram(EnterpriseTelemetryHistogram.NODE_DURATION, info.elapsed_time, duration_labels)

        if info.error:
            self._exporter.increment_counter(
                EnterpriseTelemetryCounter.ERRORS,
                1,
                self._labels(
                    **labels,
                    type=request_type,
                    model_name=info.model_name or "",
                ),
            )

    # ------------------------------------------------------------------
    # METRIC-ONLY handlers (structured log + counters/histograms)
    # ------------------------------------------------------------------

    def _message_trace(self, info: MessageTraceInfo) -> None:
        metadata = self._metadata(info)
        tenant_id, app_id, user_id = self._context_ids(info, metadata)
        attrs = self._common_attrs(info)
        attrs.update(
            {
                "data.invoke_from": metadata.get("from_source"),
                "data.conversation.id": metadata.get("conversation_id"),
                "data.conversation.mode": info.conversation_mode,
                "gen_ai.provider.name": metadata.get("ls_provider"),
                "gen_ai.request.model": metadata.get("ls_model_name"),
                "gen_ai.usage.input_tokens": info.message_tokens,
                "gen_ai.usage.output_tokens": info.answer_tokens,
                "gen_ai.usage.total_tokens": info.total_tokens,
                "data.message.status": metadata.get("status"),
                "data.message.error": info.error,
                "data.message.from_source": metadata.get("from_source"),
                "data.message.from_end_user_id": metadata.get("from_end_user_id"),
                "data.message.from_account_id": metadata.get("from_account_id"),
                "data.streaming": info.is_streaming_request,
                "data.message.time_to_first_token": info.gen_ai_server_time_to_first_token,
                "data.message.streaming_duration": info.llm_streaming_time_to_generate,
                "data.workflow.run_id": metadata.get("workflow_run_id"),
            }
        )

        if info.start_time and info.end_time:
            attrs["data.message.duration"] = (info.end_time - info.start_time).total_seconds()

        node_execution_id = metadata.get("node_execution_id")
        if node_execution_id:
            attrs["data.node.execution_id"] = node_execution_id

        ref = f"ref:message_id={info.message_id}"
        inputs = self._safe_payload_value(info.inputs)
        outputs = self._safe_payload_value(info.outputs)
        attrs["data.message.inputs"] = self._content_or_ref(inputs, ref)
        attrs["data.message.outputs"] = self._content_or_ref(outputs, ref)

        emit_metric_only_event(
            event_name=EnterpriseTelemetryEvent.MESSAGE_RUN,
            attributes=attrs,
            trace_id_source=metadata.get("workflow_run_id") or (str(info.message_id) if info.message_id else None),
            span_id_source=node_execution_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        labels = self._labels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
            model_provider=metadata.get("ls_provider") or "",
            model_name=metadata.get("ls_model_name") or "",
        )
        token_labels = TokenMetricLabels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
            operation_type=OperationType.MESSAGE,
            model_provider=metadata.get("ls_provider") or "",
            model_name=metadata.get("ls_model_name") or "",
            node_type="",
        ).to_dict()
        self._exporter.increment_counter(EnterpriseTelemetryCounter.TOKENS, info.total_tokens, token_labels)
        if info.message_tokens > 0:
            self._exporter.increment_counter(EnterpriseTelemetryCounter.INPUT_TOKENS, info.message_tokens, token_labels)
        if info.answer_tokens > 0:
            self._exporter.increment_counter(EnterpriseTelemetryCounter.OUTPUT_TOKENS, info.answer_tokens, token_labels)
        invoke_from = metadata.get("from_source", "")
        self._exporter.increment_counter(
            EnterpriseTelemetryCounter.REQUESTS,
            1,
            self._labels(
                **labels,
                type="message",
                status=metadata.get("status", ""),
                invoke_from=invoke_from,
            ),
        )

        if info.start_time and info.end_time:
            duration = (info.end_time - info.start_time).total_seconds()
            self._exporter.record_histogram(EnterpriseTelemetryHistogram.MESSAGE_DURATION, duration, labels)

        if info.gen_ai_server_time_to_first_token is not None:
            self._exporter.record_histogram(
                EnterpriseTelemetryHistogram.MESSAGE_TTFT, info.gen_ai_server_time_to_first_token, labels
            )

        if info.error:
            self._exporter.increment_counter(
                EnterpriseTelemetryCounter.ERRORS,
                1,
                self._labels(
                    **labels,
                    type="message",
                ),
            )

    def _tool_trace(self, info: ToolTraceInfo) -> None:
        metadata = self._metadata(info)
        tenant_id, app_id, user_id = self._context_ids(info, metadata)
        attrs = self._common_attrs(info)
        attrs.update(
            {
                "data.tool.name": info.tool_name,
                "data.tool.duration": float(info.time_cost),
                "data.tool.status": "failed" if info.error else "succeeded",
                "data.tool.error": info.error,
                "data.workflow.run_id": metadata.get("workflow_run_id"),
            }
        )
        node_execution_id = metadata.get("node_execution_id")
        if node_execution_id:
            attrs["data.node.execution_id"] = node_execution_id

        ref = f"ref:message_id={info.message_id}"
        attrs["data.tool.inputs"] = self._content_or_ref(info.tool_inputs, ref)
        attrs["data.tool.outputs"] = self._content_or_ref(info.tool_outputs, ref)
        attrs["data.tool.parameters"] = self._content_or_ref(info.tool_parameters, ref)
        attrs["data.tool.config"] = self._content_or_ref(info.tool_config, ref)

        emit_metric_only_event(
            event_name=EnterpriseTelemetryEvent.TOOL_EXECUTION,
            attributes=attrs,
            trace_id_source=info.resolved_trace_id,
            span_id_source=node_execution_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        labels = self._labels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
            tool_name=info.tool_name,
        )
        self._exporter.increment_counter(
            EnterpriseTelemetryCounter.REQUESTS,
            1,
            self._labels(
                **labels,
                type="tool",
            ),
        )
        self._exporter.record_histogram(EnterpriseTelemetryHistogram.TOOL_DURATION, float(info.time_cost), labels)

        if info.error:
            self._exporter.increment_counter(
                EnterpriseTelemetryCounter.ERRORS,
                1,
                self._labels(
                    **labels,
                    type="tool",
                ),
            )

    def _moderation_trace(self, info: ModerationTraceInfo) -> None:
        metadata = self._metadata(info)
        tenant_id, app_id, user_id = self._context_ids(info, metadata)
        attrs = self._common_attrs(info)
        attrs.update(
            {
                "data.moderation.flagged": info.flagged,
                "data.moderation.action": info.action,
                "data.moderation.preset_response": info.preset_response,
                "data.moderation.type": metadata.get("moderation_type", "input"),
                "data.moderation.categories": self._maybe_json(metadata.get("moderation_categories", [])),
                "data.workflow.run_id": metadata.get("workflow_run_id"),
            }
        )
        node_execution_id = metadata.get("node_execution_id")
        if node_execution_id:
            attrs["data.node.execution_id"] = node_execution_id

        attrs["data.moderation.query"] = self._content_or_ref(
            info.query,
            f"ref:message_id={info.message_id}",
        )

        emit_metric_only_event(
            event_name=EnterpriseTelemetryEvent.MODERATION_CHECK,
            attributes=attrs,
            trace_id_source=info.resolved_trace_id,
            span_id_source=node_execution_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        labels = self._labels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
        )
        self._exporter.increment_counter(
            EnterpriseTelemetryCounter.REQUESTS,
            1,
            self._labels(
                **labels,
                type="moderation",
            ),
        )

    def _suggested_question_trace(self, info: SuggestedQuestionTraceInfo) -> None:
        metadata = self._metadata(info)
        tenant_id, app_id, user_id = self._context_ids(info, metadata)
        attrs = self._common_attrs(info)
        duration: float | None = None
        if info.start_time is not None and info.end_time is not None:
            duration = (info.end_time - info.start_time).total_seconds()
        error = info.error or (info.metadata.get("error") if info.metadata else None)
        status = "failed" if error else (info.status or "succeeded")
        attrs.update(
            {
                "gen_ai.usage.total_tokens": info.total_tokens,
                "data.suggested_question.status": status,
                "data.suggested_question.error": error,
                "data.suggested_question.duration": duration,
                "gen_ai.provider.name": info.model_provider,
                "gen_ai.request.model": info.model_id,
                "data.suggested_question.count": len(info.suggested_question),
                "data.workflow.run_id": metadata.get("workflow_run_id"),
            }
        )
        node_execution_id = metadata.get("node_execution_id")
        if node_execution_id:
            attrs["data.node.execution_id"] = node_execution_id

        attrs["data.suggested_question.questions"] = self._content_or_ref(
            info.suggested_question,
            f"ref:message_id={info.message_id}",
        )

        emit_metric_only_event(
            event_name=EnterpriseTelemetryEvent.SUGGESTED_QUESTION_GENERATION,
            attributes=attrs,
            trace_id_source=info.resolved_trace_id,
            span_id_source=node_execution_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        labels = self._labels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
        )
        self._exporter.increment_counter(
            EnterpriseTelemetryCounter.REQUESTS,
            1,
            self._labels(
                **labels,
                type="suggested_question",
                model_provider=info.model_provider or "",
                model_name=info.model_id or "",
            ),
        )

    def _dataset_retrieval_trace(self, info: DatasetRetrievalTraceInfo) -> None:
        metadata = self._metadata(info)
        tenant_id, app_id, user_id = self._context_ids(info, metadata)
        attrs = self._common_attrs(info)
        attrs["data.retrieval.error"] = info.error
        attrs["data.retrieval.status"] = "failed" if info.error else "succeeded"
        if info.start_time and info.end_time:
            attrs["data.retrieval.duration"] = (info.end_time - info.start_time).total_seconds()
        attrs["data.workflow.run_id"] = metadata.get("workflow_run_id")
        node_execution_id = metadata.get("node_execution_id")
        if node_execution_id:
            attrs["data.node.execution_id"] = node_execution_id

        docs: list[dict[str, Any]] = []
        documents_any: Any = info.documents
        documents_list: list[Any] = documents_any if isinstance(documents_any, list) else []
        for entry in documents_list:
            if isinstance(entry, dict):
                entry_dict: dict[str, Any] = cast(dict[str, Any], entry)
                docs.append(entry_dict)
        dataset_ids: list[str] = []
        dataset_names: list[str] = []
        structured_docs: list[dict[str, Any]] = []
        for doc in docs:
            meta_raw = doc.get("metadata")
            meta: dict[str, Any] = cast(dict[str, Any], meta_raw) if isinstance(meta_raw, dict) else {}
            did = meta.get("dataset_id")
            dname = meta.get("dataset_name")
            if did and did not in dataset_ids:
                dataset_ids.append(did)
            if dname and dname not in dataset_names:
                dataset_names.append(dname)
            structured_docs.append(
                {
                    "dataset_id": did,
                    "document_id": meta.get("document_id"),
                    "segment_id": meta.get("segment_id"),
                    "score": meta.get("score"),
                }
            )

        attrs["data.dataset.id"] = self._maybe_json(dataset_ids)
        attrs["data.dataset.name"] = self._maybe_json(dataset_names)
        attrs["data.retrieval.document_count"] = len(docs)

        embedding_models_raw: Any = metadata.get("embedding_models")
        embedding_models: dict[str, Any] = (
            cast(dict[str, Any], embedding_models_raw) if isinstance(embedding_models_raw, dict) else {}
        )
        if embedding_models:
            providers: list[str] = []
            models: list[str] = []
            for ds_info in embedding_models.values():
                if isinstance(ds_info, dict):
                    ds_info_dict: dict[str, Any] = cast(dict[str, Any], ds_info)
                    p = ds_info_dict.get("embedding_model_provider", "")
                    m = ds_info_dict.get("embedding_model", "")
                    if p and p not in providers:
                        providers.append(p)
                    if m and m not in models:
                        models.append(m)
            attrs["data.dataset.embedding_providers"] = self._maybe_json(providers)
            attrs["data.dataset.embedding_models"] = self._maybe_json(models)

        # Add rerank model to logs
        rerank_provider = metadata.get("rerank_model_provider", "")
        rerank_model = metadata.get("rerank_model_name", "")
        if rerank_provider or rerank_model:
            attrs["data.retrieval.rerank_provider"] = rerank_provider
            attrs["data.retrieval.rerank_model"] = rerank_model

        ref = f"ref:message_id={info.message_id}"
        retrieval_inputs = self._safe_payload_value(info.inputs)
        attrs["data.retrieval.query"] = self._content_or_ref(retrieval_inputs, ref)
        attrs["data.dataset.documents"] = self._content_or_ref(structured_docs, ref)

        emit_metric_only_event(
            event_name=EnterpriseTelemetryEvent.DATASET_RETRIEVAL,
            attributes=attrs,
            trace_id_source=metadata.get("workflow_run_id") or (str(info.message_id) if info.message_id else None),
            span_id_source=node_execution_id or (str(info.message_id) if info.message_id else None),
            tenant_id=tenant_id,
            user_id=user_id,
        )

        labels = self._labels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
        )
        self._exporter.increment_counter(
            EnterpriseTelemetryCounter.REQUESTS,
            1,
            self._labels(
                **labels,
                type="dataset_retrieval",
            ),
        )

        for did in dataset_ids:
            # Get embedding model for this specific dataset
            ds_embedding_info = embedding_models.get(did, {})
            embedding_provider = ds_embedding_info.get("embedding_model_provider", "")
            embedding_model = ds_embedding_info.get("embedding_model", "")

            # Get rerank model (same for all datasets in this retrieval)
            rerank_provider = metadata.get("rerank_model_provider", "")
            rerank_model = metadata.get("rerank_model_name", "")

            self._exporter.increment_counter(
                EnterpriseTelemetryCounter.DATASET_RETRIEVALS,
                1,
                self._labels(
                    **labels,
                    dataset_id=did,
                    embedding_model_provider=embedding_provider,
                    embedding_model=embedding_model,
                    rerank_model_provider=rerank_provider,
                    rerank_model=rerank_model,
                ),
            )

    def _generate_name_trace(self, info: GenerateNameTraceInfo) -> None:
        metadata = self._metadata(info)
        tenant_id, app_id, user_id = self._context_ids(info, metadata)
        attrs = self._common_attrs(info)
        attrs["data.conversation.id"] = info.conversation_id
        node_execution_id = metadata.get("node_execution_id")
        if node_execution_id:
            attrs["data.node.execution_id"] = node_execution_id

        duration: float | None = None
        if info.start_time is not None and info.end_time is not None:
            duration = (info.end_time - info.start_time).total_seconds()
        error: str | None = metadata.get("error") if metadata else None
        status = "failed" if error else "succeeded"
        attrs["data.generate_name.duration"] = duration
        attrs["data.generate_name.status"] = status
        attrs["data.generate_name.error"] = error

        ref = f"ref:conversation_id={info.conversation_id}"
        inputs = self._safe_payload_value(info.inputs)
        outputs = self._safe_payload_value(info.outputs)
        attrs["data.generate_name.inputs"] = self._content_or_ref(inputs, ref)
        attrs["data.generate_name.outputs"] = self._content_or_ref(outputs, ref)

        emit_metric_only_event(
            event_name=EnterpriseTelemetryEvent.GENERATE_NAME_EXECUTION,
            attributes=attrs,
            trace_id_source=info.resolved_trace_id,
            span_id_source=node_execution_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        labels = self._labels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
        )
        self._exporter.increment_counter(
            EnterpriseTelemetryCounter.REQUESTS,
            1,
            self._labels(
                **labels,
                type="generate_name",
            ),
        )

    def _prompt_generation_trace(self, info: PromptGenerationTraceInfo) -> None:
        metadata = self._metadata(info)
        tenant_id, app_id, user_id = self._context_ids(info, metadata)
        attrs = {
            "data.trace_id": info.resolved_trace_id,
            "data.tenant_id": tenant_id,
            "gen_ai.user.id": user_id,
            "data.app_id": app_id or "",
            "data.app.name": metadata.get("app_name"),
            "data.workspace.name": metadata.get("workspace_name"),
            "data.prompt_generation.operation_type": info.operation_type,
            "gen_ai.provider.name": info.model_provider,
            "gen_ai.request.model": info.model_name,
            "gen_ai.usage.input_tokens": info.prompt_tokens,
            "gen_ai.usage.output_tokens": info.completion_tokens,
            "gen_ai.usage.total_tokens": info.total_tokens,
            "data.prompt_generation.duration": info.latency,
            "data.prompt_generation.status": "failed" if info.error else "succeeded",
            "data.prompt_generation.error": info.error,
        }
        node_execution_id = metadata.get("node_execution_id")
        if node_execution_id:
            attrs["data.node.execution_id"] = node_execution_id

        if info.total_price is not None:
            attrs["data.prompt_generation.total_price"] = info.total_price
            attrs["data.prompt_generation.currency"] = info.currency

        ref = f"ref:trace_id={info.trace_id}"
        outputs = self._safe_payload_value(info.outputs)
        attrs["data.prompt_generation.instruction"] = self._content_or_ref(info.instruction, ref)
        attrs["data.prompt_generation.output"] = self._content_or_ref(outputs, ref)

        emit_metric_only_event(
            event_name=EnterpriseTelemetryEvent.PROMPT_GENERATION_EXECUTION,
            attributes=attrs,
            trace_id_source=info.resolved_trace_id,
            span_id_source=node_execution_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        token_labels = TokenMetricLabels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
            operation_type=info.operation_type,
            model_provider=info.model_provider,
            model_name=info.model_name,
            node_type="",
        ).to_dict()

        labels = self._labels(
            tenant_id=tenant_id or "",
            app_id=app_id or "",
            operation_type=info.operation_type,
            model_provider=info.model_provider,
            model_name=info.model_name,
        )

        self._exporter.increment_counter(EnterpriseTelemetryCounter.TOKENS, info.total_tokens, token_labels)
        if info.prompt_tokens > 0:
            self._exporter.increment_counter(EnterpriseTelemetryCounter.INPUT_TOKENS, info.prompt_tokens, token_labels)
        if info.completion_tokens > 0:
            self._exporter.increment_counter(
                EnterpriseTelemetryCounter.OUTPUT_TOKENS, info.completion_tokens, token_labels
            )

        prompt_status = "failed" if info.error else "succeeded"
        self._exporter.increment_counter(
            EnterpriseTelemetryCounter.REQUESTS,
            1,
            self._labels(
                **labels,
                type="prompt_generation",
                status=prompt_status,
            ),
        )

        self._exporter.record_histogram(
            EnterpriseTelemetryHistogram.PROMPT_GENERATION_DURATION,
            info.latency,
            labels,
        )

        if info.error:
            self._exporter.increment_counter(
                EnterpriseTelemetryCounter.ERRORS,
                1,
                self._labels(
                    **labels,
                    type="prompt_generation",
                ),
            )
