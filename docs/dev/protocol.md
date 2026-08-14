# Bridge Protocol (MCP server ⇔ TUI)

Specification of the Unix domain socket protocol that connects the MCP server process (`agenttakt serve`) and the TUI process (`agenttakt`).

## Socket path

1. If the `AGENTTAKT_SOCKET` environment variable is set, use it (an override for isolating sockets per project)
2. Default: `{tempdir}/agenttakt-{uid}/takt.sock`
   - The directory is created with permission `0700`
   - The path is kept shallow to respect macOS's 104-byte `sun_path` limit

## Framing

NDJSON (one message per line, UTF-8, `\n`-delimited).

- pydantic's `model_dump_json()` never emits newlines, so this is safe
- A binary length prefix was rejected in favor of debuggability — you can test by hand with `nc -U <socket>`

## Message types

A tagged union discriminated by the `type` field.

### `review_request` (MCP → TUI)

```json
{
  "type": "review_request",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "plan": { "graph_id": "...", "nodes": [], "edges": [] },
  "meta": {
    "summary": "Refactoring plan for the auth layer",
    "cwd": "/path/to/project",
    "timestamp": "2026-08-02T12:00:00+09:00"
  }
}
```

- `request_id`: assigned by the MCP side as a uuid4
- `meta.summary`: optional one-line description shown in the TUI header

### `show_plan` (MCP → TUI)

Same shape as `review_request` (with `"type": "show_plan"`), but display-only: the TUI writes back an `ack` immediately on receipt and never sends a `review_response` for it. The plan is queued and shown with a `[view-only]` header; whatever the human does with it is not reported back.

### `ack` (TUI → MCP)

```json
{ "type": "ack", "request_id": "550e8400-..." }
```

Acknowledges receipt of a `show_plan` request. The MCP side disconnects as soon as it arrives.

### `review_response` (TUI → MCP)

```json
{
  "type": "review_response",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "approved",
  "plan": { "graph_id": "...", "status": "approved", "nodes": [], "edges": [] },
  "reason": null
}
```

- `decision`: `"approved"` | `"rejected"`
- `plan`: the plan with the human's edits applied (`status` already rewritten)
- `reason`: optional reason for rejection

### `error` (both directions)

```json
{
  "type": "error",
  "request_id": "550e8400-...",
  "code": "invalid_plan",
  "message": "..."
}
```

## Connection lifecycle

- **One request per connection.** The MCP side treats `connect → send review_request → receive review_response → disconnect` as one cycle (no multiplexing). For `show_plan` the cycle is `connect → send show_plan → receive ack → disconnect`.
- The TUI side (`BridgeServer`) accepts multiple simultaneous connections, queues requests FIFO, and processes them one at a time. Responses are written back to the connection they arrived on.
- **Disconnect detection**: the TUI watches each connection's reader for EOF. If a connection drops because of an Executor-side timeout or cancellation, the request is removed from the queue; if it was being edited, the human is notified and returned to the idle screen. `show_plan` requests are exempt: they are already acked, so the sender's immediate disconnect is the normal case and the plan stays queued.

## Failure handling

| Situation | Behavior |
|---|---|
| TUI not running (`connect` raises `FileNotFoundError` / `ConnectionRefusedError`) | The MCP tool returns an error: `AgentTakt editor is not running. Ask the user to run "agenttakt" in a separate terminal, then call request_approval again.` |
| Stale socket (leftover from an abnormal TUI exit) | On TUI startup: bind fails → try to connect → if refused, unlink and re-bind |
| Normal TUI exit | The socket is unlinked in `finally` plus SIGINT/SIGTERM handlers |
