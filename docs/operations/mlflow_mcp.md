# MLflow MCP Server Setup

This guide captures how to expose the MLflow tracking store to MCP-compatible AI
tools (Claude Desktop, VS Code MCP panel, Cursor, etc.) so that assistants can
search traces, inspect spans, and log feedback directly from MLflow.

> The MCP capability was added in MLflow **3.5.1** and is still experimental.

## 1. Prerequisites

- MLflow tracking stack running locally via Docker (see `docker/mlops/docker-compose.yml`).
- Python tooling managed by `uv` (already used for this project).
- An MCP-capable client (`.vscode/mcp.json`, `.cursor/mcp.json`, Claude custom server, etc.).

## 2. Start/Verify the MLflow tracker

```bash
# Pick an open port (5000 by default). Override when necessary.
export MLFLOW_PORT=${MLFLOW_PORT:-5050}
MLFLOW_PORT=$MLFLOW_PORT docker compose -f docker/mlops/docker-compose.yml up mlflow
```

The UI is available at `http://localhost:$MLFLOW_PORT` and uses the shared
`artifacts/mlruns/` volume so every run logged by Hydra/Optuna shows up here.

## 3. Launch the MCP server

The MCP server runs as a separate process that speaks the MCP protocol over
stdio. Use `uv` to install/run MLflow with the `mcp` extra on demand:

```bash
MLFLOW_TRACKING_URI="http://localhost:${MLFLOW_PORT:-5050}" \
uv run --with "mlflow[mcp]>=3.5.1" mlflow mcp run
```

Notes:

- `MLFLOW_TRACKING_URI` must match the running tracker (Docker container or
  local file URI).
- Use `mlflow mcp --help` to confirm the CLI is available before wiring it into
  an MCP client.

## 4. MCP client configuration snippets

### VS Code (`.vscode/mcp.json`)

```json
{
  "servers": {
    "mlflow-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "mlflow[mcp]>=3.5.1",
        "mlflow",
        "mcp",
        "run"
      ],
      "env": {
        "MLFLOW_TRACKING_URI": "http://localhost:${MLFLOW_PORT:-5050}"
      }
    }
  }
}
```

### Cursor (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "mlflow-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "mlflow[mcp]>=3.5.1",
        "mlflow",
        "mcp",
        "run"
      ],
      "env": {
        "MLFLOW_TRACKING_URI": "http://localhost:${MLFLOW_PORT:-5050}"
      }
    }
  }
}
```

Adjust the env block if the tracker is exposed via HTTPS or inside Docker
Desktop with a different hostname.

## 5. Supported MCP tools (summary)

Once connected, the MLflow MCP server exposes the following operations to
assistants:

- `search_traces(filter_string, order_by, limit, extract_fields)` – query traces
  with SQL-like predicates and optional field selectors.
- `get_trace(trace_id, extract_fields)` – fetch a specific trace (spans, tags,
  assessments).
- `delete_trace(trace_id)` – remove a trace.
- `log_feedback(trace_id, score, reason)` – attach manual assessments.
- `log_assessment(trace_id, name, value, reasoning, source_type)` –
  fine-grained assessment logging.
- `get_assessment(trace_id, assessment_id)` / `update_assessment(...)` /
  `delete_assessment(...)` – manage recorded assessments.

The optional `extract_fields` parameter accepts comma-separated field paths
(`info.trace_id`, `info.tags.*`, `data.spans.*.name`, etc.) and supports
wildcards to keep responses small.

## 6. Workflow Tips

1. Start Dockerized MLflow (`docker/mlops/docker-compose.yml`).
2. Launch the MCP server via `uv run --with "mlflow[mcp]..."`.
3. Connect your MCP client using the JSON snippets above.
4. Use the newly available tools inside your AI assistant to search traces,
   inspect failing requests, or log evaluations without leaving MLflow.
