# DATA Enterprise Telemetry Data Dictionary

Quick reference for all telemetry signals emitted by DATA Enterprise. For configuration and architecture details, see [README.md](./README.md).

## Resource Attributes

Attached to every signal (Span, Metric, Log).

| Attribute | Type | Example |
|-----------|------|---------|
| `service.name` | string | `data` |
| `host.name` | string | `data-api-7f8b` |

## Traces (Spans)

### `data.workflow.run`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.trace_id` | string | Business trace ID (Workflow Run ID) |
| `data.tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.workflow.id` | string | Workflow definition ID |
| `data.workflow.run_id` | string | Unique ID for this run |
| `data.workflow.status` | string | `succeeded`, `failed`, `stopped`, etc. |
| `data.workflow.error` | string | Error message if failed |
| `data.workflow.elapsed_time` | float | Total execution time (seconds) |
| `data.invoke_from` | string | `api`, `webapp`, `debug` |
| `data.conversation.id` | string | Conversation ID (optional) |
| `data.message.id` | string | Message ID (optional) |
| `data.invoked_by` | string | User ID who triggered the run |
| `gen_ai.usage.total_tokens` | int | Total tokens across all nodes (optional) |
| `gen_ai.user.id` | string | End-user identifier (optional) |
| `data.parent.trace_id` | string | Parent workflow trace ID (optional) |
| `data.parent.workflow.run_id` | string | Parent workflow run ID (optional) |
| `data.parent.node.execution_id` | string | Parent node execution ID (optional) |
| `data.parent.app.id` | string | Parent app ID (optional) |

### `data.node.execution`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.trace_id` | string | Business trace ID |
| `data.tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.workflow.id` | string | Workflow definition ID |
| `data.workflow.run_id` | string | Workflow Run ID |
| `data.message.id` | string | Message ID (optional) |
| `data.conversation.id` | string | Conversation ID (optional) |
| `data.node.execution_id` | string | Unique node execution ID |
| `data.node.id` | string | Node ID in workflow graph |
| `data.node.type` | string | Node type (see appendix) |
| `data.node.title` | string | Display title |
| `data.node.status` | string | `succeeded`, `failed` |
| `data.node.error` | string | Error message if failed |
| `data.node.elapsed_time` | float | Execution time (seconds) |
| `data.node.index` | int | Execution order index |
| `data.node.predecessor_node_id` | string | Triggering node ID |
| `data.node.iteration_id` | string | Iteration ID (optional) |
| `data.node.loop_id` | string | Loop ID (optional) |
| `data.node.parallel_id` | string | Parallel branch ID (optional) |
| `data.node.invoked_by` | string | User ID who triggered execution |
| `gen_ai.usage.input_tokens` | int | Prompt tokens (LLM nodes only) |
| `gen_ai.usage.output_tokens` | int | Completion tokens (LLM nodes only) |
| `gen_ai.usage.total_tokens` | int | Total tokens (LLM nodes only) |
| `gen_ai.request.model` | string | LLM model name (LLM nodes only) |
| `gen_ai.provider.name` | string | LLM provider name (LLM nodes only) |
| `gen_ai.user.id` | string | End-user identifier (optional) |

### `data.node.execution.draft`

Same attributes as `data.node.execution`. Emitted during Preview/Debug runs.

## Counters

All counters are cumulative and emitted at 100% accuracy.

### Token Counters

| Metric | Unit | Description |
|--------|------|-------------|
| `data.tokens.total` | `{token}` | Total tokens consumed |
| `data.tokens.input` | `{token}` | Input (prompt) tokens |
| `data.tokens.output` | `{token}` | Output (completion) tokens |

**Labels:**

- `tenant_id`, `app_id`, `operation_type`, `model_provider`, `model_name`, `node_type` (if node_execution)

⚠️ **Warning:** `data.tokens.total` at workflow level includes all node tokens. Filter by `operation_type` to avoid double-counting.

#### Token Hierarchy & Query Patterns

Token metrics are emitted at multiple layers. Understanding the hierarchy prevents double-counting:

```
App-level total
├── workflow          ← sum of all node_execution tokens (DO NOT add both)
│   └── node_execution ← per-node breakdown
├── message           ← independent (non-workflow chat apps only)
├── rule_generate     ← independent helper LLM call
├── code_generate     ← independent helper LLM call
├── structured_output ← independent helper LLM call
└── instruction_modify← independent helper LLM call
```

**Key rule:** `workflow` tokens already include all `node_execution` tokens. Never sum both.

**Available labels on token metrics:** `tenant_id`, `app_id`, `operation_type`, `model_provider`, `model_name`, `node_type`.
App name is only available on span attributes (`data.app.name`), not metric labels — use `app_id` for metric queries.

**Common queries** (PromQL):

```promql
# ── Totals ──────────────────────────────────────────────────
# App-level total (exclude node_execution to avoid double-counting)
sum by (app_id) (data_tokens_total{operation_type!="node_execution"})

# Single app total
sum (data_tokens_total{app_id="<app_id>", operation_type!="node_execution"})

# Per-tenant totals
sum by (tenant_id) (data_tokens_total{operation_type!="node_execution"})

# ── Drill-down ──────────────────────────────────────────────
# Workflow-level tokens for an app
sum (data_tokens_total{app_id="<app_id>", operation_type="workflow"})

# Node-level breakdown within an app
sum by (node_type) (data_tokens_total{app_id="<app_id>", operation_type="node_execution"})

# Model breakdown for an app
sum by (model_provider, model_name) (data_tokens_total{app_id="<app_id>"})

# Input vs output per model
sum by (model_name) (data_tokens_input_total{app_id="<app_id>"})
sum by (model_name) (data_tokens_output_total{app_id="<app_id>"})

# ── Rates ───────────────────────────────────────────────────
# Token consumption rate (per hour)
sum(rate(data_tokens_total{operation_type!="node_execution"}[1h]))

# Per-app consumption rate
sum by (app_id) (rate(data_tokens_total{operation_type!="node_execution"}[1h]))
```

**Finding `app_id` from app name** (trace query — Tempo / Jaeger):

```
{ resource.data.app.name = "My Chatbot" } | select(resource.data.app.id)
```

### Request Counters

| Metric | Unit | Description |
|--------|------|-------------|
| `data.requests.total` | `{request}` | Total operations count |

**Labels by type:**

| `type` | Additional Labels |
|--------|-------------------|
| `workflow` | `tenant_id`, `app_id`, `status`, `invoke_from` |
| `node` | `tenant_id`, `app_id`, `node_type`, `model_provider`, `model_name`, `status` |
| `draft_node` | `tenant_id`, `app_id`, `node_type`, `model_provider`, `model_name`, `status` |
| `message` | `tenant_id`, `app_id`, `model_provider`, `model_name`, `status`, `invoke_from` |
| `tool` | `tenant_id`, `app_id`, `tool_name` |
| `moderation` | `tenant_id`, `app_id` |
| `suggested_question` | `tenant_id`, `app_id`, `model_provider`, `model_name` |
| `dataset_retrieval` | `tenant_id`, `app_id` |
| `generate_name` | `tenant_id`, `app_id` |
| `prompt_generation` | `tenant_id`, `app_id`, `operation_type`, `model_provider`, `model_name`, `status` |

### Error Counters

| Metric | Unit | Description |
|--------|------|-------------|
| `data.errors.total` | `{error}` | Total failed operations |

**Labels by type:**

| `type` | Additional Labels |
|--------|-------------------|
| `workflow` | `tenant_id`, `app_id` |
| `node` | `tenant_id`, `app_id`, `node_type`, `model_provider`, `model_name` |
| `draft_node` | `tenant_id`, `app_id`, `node_type`, `model_provider`, `model_name` |
| `message` | `tenant_id`, `app_id`, `model_provider`, `model_name` |
| `tool` | `tenant_id`, `app_id`, `tool_name` |
| `prompt_generation` | `tenant_id`, `app_id`, `operation_type`, `model_provider`, `model_name` |

### Other Counters

| Metric | Unit | Labels |
|--------|------|--------|
| `data.feedback.total` | `{feedback}` | `tenant_id`, `app_id`, `rating` |
| `data.dataset.retrievals.total` | `{retrieval}` | `tenant_id`, `app_id`, `dataset_id`, `embedding_model_provider`, `embedding_model`, `rerank_model_provider`, `rerank_model` |
| `data.app.created.total` | `{app}` | `tenant_id`, `app_id`, `mode` |
| `data.app.updated.total` | `{app}` | `tenant_id`, `app_id` |
| `data.app.deleted.total` | `{app}` | `tenant_id`, `app_id` |

## Histograms

| Metric | Unit | Labels |
|--------|------|--------|
| `data.workflow.duration` | `s` | `tenant_id`, `app_id`, `status` |
| `data.node.duration` | `s` | `tenant_id`, `app_id`, `node_type`, `model_provider`, `model_name`, `plugin_name` |
| `data.message.duration` | `s` | `tenant_id`, `app_id`, `model_provider`, `model_name` |
| `data.message.time_to_first_token` | `s` | `tenant_id`, `app_id`, `model_provider`, `model_name` |
| `data.tool.duration` | `s` | `tenant_id`, `app_id`, `tool_name` |
| `data.prompt_generation.duration` | `s` | `tenant_id`, `app_id`, `operation_type`, `model_provider`, `model_name` |

## Structured Logs

### Span Companion Logs

Logs that accompany spans. Signal type: `span_detail`

#### `data.workflow.run` Companion Log

**Common attributes:** All span attributes (see Traces section) plus:

| Additional Attribute | Type | Always Present | Description |
|---------------------|------|----------------|-------------|
| `data.app.name` | string | No | Application display name |
| `data.workspace.name` | string | No | Workspace display name |
| `data.workflow.version` | string | Yes | Workflow definition version |
| `data.workflow.inputs` | string/JSON | Yes | Input parameters (content-gated) |
| `data.workflow.outputs` | string/JSON | Yes | Output results (content-gated) |
| `data.workflow.query` | string | No | User query text (content-gated) |

**Event attributes:**

- `data.event.name`: `"data.workflow.run"`
- `data.event.signal`: `"span_detail"`
- `trace_id`, `span_id`, `tenant_id`, `user_id`

#### `data.node.execution` and `data.node.execution.draft` Companion Logs

**Common attributes:** All span attributes (see Traces section) plus:

| Additional Attribute | Type | Always Present | Description |
|---------------------|------|----------------|-------------|
| `data.app.name` | string | No | Application display name |
| `data.workspace.name` | string | No | Workspace display name |
| `data.invoke_from` | string | No | Invocation source |
| `gen_ai.tool.name` | string | No | Tool name (tool nodes only) |
| `data.node.total_price` | float | No | Cost (LLM nodes only) |
| `data.node.currency` | string | No | Currency code (LLM nodes only) |
| `data.node.iteration_index` | int | No | Iteration index (iteration nodes) |
| `data.node.loop_index` | int | No | Loop index (loop nodes) |
| `data.plugin.name` | string | No | Plugin name (tool/knowledge nodes) |
| `data.credential.name` | string | No | Credential name (plugin nodes) |
| `data.credential.id` | string | No | Credential ID (plugin nodes) |
| `data.dataset.ids` | JSON array | No | Dataset IDs (knowledge nodes) |
| `data.dataset.names` | JSON array | No | Dataset names (knowledge nodes) |
| `data.node.inputs` | string/JSON | Yes | Node inputs (content-gated) |
| `data.node.outputs` | string/JSON | Yes | Node outputs (content-gated) |
| `data.node.process_data` | string/JSON | No | Processing data (content-gated) |

**Event attributes:**

- `data.event.name`: `"data.node.execution"` or `"data.node.execution.draft"`
- `data.event.signal`: `"span_detail"`
- `trace_id`, `span_id`, `tenant_id`, `user_id`

### Standalone Logs

Logs without structural spans. Signal type: `metric_only`

#### `data.message.run`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.message.run"` |
| `data.event.signal` | string | `"metric_only"` |
| `trace_id` | string | OTEL trace ID (32-char hex) |
| `span_id` | string | OTEL span ID (16-char hex) |
| `tenant_id` | string | Tenant identifier |
| `user_id` | string | User identifier (optional) |
| `data.app_id` | string | Application identifier |
| `data.message.id` | string | Message identifier |
| `data.conversation.id` | string | Conversation ID (optional) |
| `data.workflow.run_id` | string | Workflow run ID (optional) |
| `data.invoke_from` | string | `service-api`, `web-app`, `debugger`, `explore` |
| `gen_ai.provider.name` | string | LLM provider |
| `gen_ai.request.model` | string | LLM model |
| `gen_ai.usage.input_tokens` | int | Input tokens |
| `gen_ai.usage.output_tokens` | int | Output tokens |
| `gen_ai.usage.total_tokens` | int | Total tokens |
| `data.message.status` | string | `succeeded`, `failed` |
| `data.message.error` | string | Error message (if failed) |
| `data.message.duration` | float | Duration (seconds) |
| `data.message.time_to_first_token` | float | TTFT (seconds) |
| `data.message.inputs` | string/JSON | Inputs (content-gated) |
| `data.message.outputs` | string/JSON | Outputs (content-gated) |

#### `data.tool.execution`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.tool.execution"` |
| `data.event.signal` | string | `"metric_only"` |
| `trace_id` | string | OTEL trace ID |
| `span_id` | string | OTEL span ID |
| `tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.message.id` | string | Message identifier |
| `data.tool.name` | string | Tool name |
| `data.tool.duration` | float | Duration (seconds) |
| `data.tool.status` | string | `succeeded`, `failed` |
| `data.tool.error` | string | Error message (if failed) |
| `data.tool.inputs` | string/JSON | Inputs (content-gated) |
| `data.tool.outputs` | string/JSON | Outputs (content-gated) |
| `data.tool.parameters` | string/JSON | Parameters (content-gated) |
| `data.tool.config` | string/JSON | Configuration (content-gated) |

#### `data.moderation.check`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.moderation.check"` |
| `data.event.signal` | string | `"metric_only"` |
| `trace_id` | string | OTEL trace ID |
| `span_id` | string | OTEL span ID |
| `tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.message.id` | string | Message identifier |
| `data.moderation.type` | string | `input`, `output` |
| `data.moderation.action` | string | `pass`, `block`, `flag` |
| `data.moderation.flagged` | boolean | Whether flagged |
| `data.moderation.categories` | JSON array | Flagged categories |
| `data.moderation.query` | string | Content (content-gated) |

#### `data.suggested_question.generation`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.suggested_question.generation"` |
| `data.event.signal` | string | `"metric_only"` |
| `trace_id` | string | OTEL trace ID |
| `span_id` | string | OTEL span ID |
| `tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.message.id` | string | Message identifier |
| `data.suggested_question.count` | int | Number of questions |
| `data.suggested_question.duration` | float | Duration (seconds) |
| `data.suggested_question.status` | string | `succeeded`, `failed` |
| `data.suggested_question.error` | string | Error message (if failed) |
| `data.suggested_question.questions` | JSON array | Questions (content-gated) |

#### `data.dataset.retrieval`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.dataset.retrieval"` |
| `data.event.signal` | string | `"metric_only"` |
| `trace_id` | string | OTEL trace ID |
| `span_id` | string | OTEL span ID |
| `tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.message.id` | string | Message identifier |
| `data.dataset.id` | string | Dataset identifier |
| `data.dataset.name` | string | Dataset name |
| `data.dataset.embedding_providers` | JSON array | Embedding model providers (one per dataset) |
| `data.dataset.embedding_models` | JSON array | Embedding models (one per dataset) |
| `data.retrieval.rerank_provider` | string | Rerank model provider |
| `data.retrieval.rerank_model` | string | Rerank model name |
| `data.retrieval.query` | string | Search query (content-gated) |
| `data.retrieval.document_count` | int | Documents retrieved |
| `data.retrieval.duration` | float | Duration (seconds) |
| `data.retrieval.status` | string | `succeeded`, `failed` |
| `data.retrieval.error` | string | Error message (if failed) |
| `data.dataset.documents` | JSON array | Documents (content-gated) |

#### `data.generate_name.execution`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.generate_name.execution"` |
| `data.event.signal` | string | `"metric_only"` |
| `trace_id` | string | OTEL trace ID |
| `span_id` | string | OTEL span ID |
| `tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.conversation.id` | string | Conversation identifier |
| `data.generate_name.duration` | float | Duration (seconds) |
| `data.generate_name.status` | string | `succeeded`, `failed` |
| `data.generate_name.error` | string | Error message (if failed) |
| `data.generate_name.inputs` | string/JSON | Inputs (content-gated) |
| `data.generate_name.outputs` | string | Generated name (content-gated) |

#### `data.prompt_generation.execution`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.prompt_generation.execution"` |
| `data.event.signal` | string | `"metric_only"` |
| `trace_id` | string | OTEL trace ID |
| `span_id` | string | OTEL span ID |
| `tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.prompt_generation.operation_type` | string | Operation type (see appendix) |
| `gen_ai.provider.name` | string | LLM provider |
| `gen_ai.request.model` | string | LLM model |
| `gen_ai.usage.input_tokens` | int | Input tokens |
| `gen_ai.usage.output_tokens` | int | Output tokens |
| `gen_ai.usage.total_tokens` | int | Total tokens |
| `data.prompt_generation.duration` | float | Duration (seconds) |
| `data.prompt_generation.status` | string | `succeeded`, `failed` |
| `data.prompt_generation.error` | string | Error message (if failed) |
| `data.prompt_generation.instruction` | string | Instruction (content-gated) |
| `data.prompt_generation.output` | string/JSON | Output (content-gated) |

#### `data.app.created`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.app.created"` |
| `data.event.signal` | string | `"metric_only"` |
| `tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.app.mode` | string | `chat`, `completion`, `agent-chat`, `workflow` |
| `data.app.created_at` | string | Timestamp (ISO 8601) |

#### `data.app.updated`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.app.updated"` |
| `data.event.signal` | string | `"metric_only"` |
| `tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.app.updated_at` | string | Timestamp (ISO 8601) |

#### `data.app.deleted`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.app.deleted"` |
| `data.event.signal` | string | `"metric_only"` |
| `tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.app.deleted_at` | string | Timestamp (ISO 8601) |

#### `data.feedback.created`

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.feedback.created"` |
| `data.event.signal` | string | `"metric_only"` |
| `trace_id` | string | OTEL trace ID |
| `span_id` | string | OTEL span ID |
| `tenant_id` | string | Tenant identifier |
| `data.app_id` | string | Application identifier |
| `data.message.id` | string | Message identifier |
| `data.feedback.rating` | string | `like`, `dislike`, `null` |
| `data.feedback.content` | string | Feedback text (content-gated) |
| `data.feedback.created_at` | string | Timestamp (ISO 8601) |

#### `data.telemetry.rehydration_failed`

Diagnostic event for telemetry system health monitoring.

| Attribute | Type | Description |
|-----------|------|-------------|
| `data.event.name` | string | `"data.telemetry.rehydration_failed"` |
| `data.event.signal` | string | `"metric_only"` |
| `tenant_id` | string | Tenant identifier |
| `data.telemetry.error` | string | Error message |
| `data.telemetry.payload_type` | string | Payload type (see appendix) |
| `data.telemetry.correlation_id` | string | Correlation ID |

## Content-Gated Attributes

When `ENTERPRISE_INCLUDE_CONTENT=false`, these attributes are replaced with reference strings (`ref:{id_type}={uuid}`).

| Attribute | Signal |
|-----------|--------|
| `data.workflow.inputs` | `data.workflow.run` |
| `data.workflow.outputs` | `data.workflow.run` |
| `data.workflow.query` | `data.workflow.run` |
| `data.node.inputs` | `data.node.execution` |
| `data.node.outputs` | `data.node.execution` |
| `data.node.process_data` | `data.node.execution` |
| `data.message.inputs` | `data.message.run` |
| `data.message.outputs` | `data.message.run` |
| `data.tool.inputs` | `data.tool.execution` |
| `data.tool.outputs` | `data.tool.execution` |
| `data.tool.parameters` | `data.tool.execution` |
| `data.tool.config` | `data.tool.execution` |
| `data.moderation.query` | `data.moderation.check` |
| `data.suggested_question.questions` | `data.suggested_question.generation` |
| `data.retrieval.query` | `data.dataset.retrieval` |
| `data.dataset.documents` | `data.dataset.retrieval` |
| `data.generate_name.inputs` | `data.generate_name.execution` |
| `data.generate_name.outputs` | `data.generate_name.execution` |
| `data.prompt_generation.instruction` | `data.prompt_generation.execution` |
| `data.prompt_generation.output` | `data.prompt_generation.execution` |
| `data.feedback.content` | `data.feedback.created` |

## Appendix

### Operation Types

- `workflow`, `node_execution`, `message`, `rule_generate`, `code_generate`, `structured_output`, `instruction_modify`

### Node Types

- `start`, `end`, `answer`, `llm`, `knowledge-retrieval`, `knowledge-index`, `if-else`, `code`, `template-transform`, `question-classifier`, `http-request`, `tool`, `datasource`, `variable-aggregator`, `loop`, `iteration`, `parameter-extractor`, `assigner`, `document-extractor`, `list-operator`, `agent`, `trigger-webhook`, `trigger-schedule`, `trigger-plugin`, `human-input`

### Workflow Statuses

- `running`, `succeeded`, `failed`, `stopped`, `partial-succeeded`, `paused`

### Payload Types

- `workflow`, `node`, `message`, `tool`, `moderation`, `suggested_question`, `dataset_retrieval`, `generate_name`, `prompt_generation`, `app`, `feedback`

### Null Value Behavior

**Spans:** Attributes with `null` values are omitted.

**Logs:** Attributes with `null` values appear as `null` in JSON.

**Content-Gated:** Replaced with reference strings, not set to `null`.
