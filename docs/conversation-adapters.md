# Conversation integration

The main UI remains a conversation, with source files at the upper right and the
Android device preview at the lower right. There is no separate execution home.

## Boundaries

- Conversation adapters own upstream sessions and normalize text, tool, permission,
  status, error and completion events. A capability record controls visible UI.
- Model providers and credentials are adapter configuration, not adapter identities.
- Android actions and independent verification remain shared application tools.
- A generic CLI adapter must not advertise persistent sessions or tool streaming
  merely because it returns text. Direct model APIs need an explicit tool loop.

## OpenCode first

Use the installed server's `/doc` schema as the implementation authority. The
published server API describes health, session creation, asynchronous prompts,
events, abort, provider selection and permission responses. Validate installed
schemas before binding event fields; upstream versions can differ.

Persist mappings scoped by authenticated owner, local conversation, project and
adapter. Never accept an arbitrary upstream session ID from a browser. Reconnect
must reconcile messages and pending permissions; it must not resubmit a prompt.
Subscribe before dispatch to avoid missing initial events. Filter events to the
mapped session and distinguish assistant parts from user parts. A disconnect must
not be reported as successful completion. Concurrent sends on one session need an
explicit conflict response. Cancelling the UI must abort the upstream generation.

Credentials stay server-side and outside tracked files. Configuration responses
contain presence/status only. Permissions default to the existing read-only
policy until the UI can handle explicit requests. Device preview does not imply
that the conversation can operate the device.

## Delivery state

Contracts are defined in `backend/app/agents/contracts.py`. OpenCode chat routes through the HTTP service with owner/project-bound SQLite
session mapping, NDJSON text/tool/status events and an abort endpoint. Other
providers retain their original transports. Conversation text and tool events are
journaled for reconnect, and unfinished turns are reconciled after restart.
`python -m app.local_services` starts the backend and OpenCode together on loopback,
using process-local random credentials. `GUI_OPENCODE_URL` can target an existing
service instead.
The name `dsh` is unconfirmed and does not yet identify an adapter.

Reference: https://opencode.ai/docs/server/


## Browser reconnect checkpoint

Generation now runs in a retained asyncio task. The HTTP response tails the SQLite
journal and its cancellation does not cancel the producer. Reopening a conversation
reads cursor pages, reconstructs the current text parts and polls while running.
An explicit abort still targets the mapped upstream session. Text and tool/status
events remain separate, and only the authenticated owner can retrieve them.

A deterministic asynchronous test closes the browser consumer while a generation
is waiting, verifies that it remains running, rejects a concurrent send, releases
the generation and checks one prompt plus the persisted final text. This tests
application lifecycle semantics, not real model/network behavior. Backend process
restart recovery has separate deterministic coverage. One backend worker is
required while producer ownership is process-local.

The conversation composer includes a model/provider selector. The administrator
console owns API-key save and model-connection testing. Catalog responses use an
explicit field allowlist. Credentials
are sent to OpenCode's auth endpoint, not written to the repository or returned to
the browser. Saved credentials are shared by the local OpenCode service. Connected
provider status does not prove the selected model can generate a response, so the
admin test creates a temporary deny-all-tools session, requests a fixed reply and
deletes the session afterward.


Live transport check: installed OpenCode 1.19.0 reports a connected `opencode`
provider with zero-cost model catalog entries. A file-free greeting using
`mimo-v2.6-flash-free` reached the real busy/retry event stream but did not produce
text within 55 seconds. The test timeout requested upstream abort; the subsequent
session status was no longer active. This verifies request/event/abort transport,
not successful model generation. Production generations now have a five-minute
wall limit even if heartbeat/retry events keep the connection alive.


## Backend restart recovery

Unfinished turns are identified from persisted start/finish journal markers.
Before a new prompt reuses such a session, the backend requests upstream abort,
then atomically saves received text with an interruption notice and closes the
old journal turn. If upstream cannot be reached, recovery remains pending and the
new prompt is rejected. A missing upstream session (404) is treated as no longer
running. Tests cover retained partial text, idempotence and unreachable service.
This is explicit interrupted-turn recovery, not automatic prompt replay. Model
execution is never silently resubmitted after a restart.


## Device tool integration checkpoint

From `backend`, run `python -m app.local_services` to start the paired local
services. The launcher copies the versioned `agent-tools/opencode/gui_*.ts`
tools into an ignored service config directory. It generates separate random OpenCode
server and device bridge credentials in process memory and passes them only to
its children. It verifies `gui_observe`, `gui_act`, and `gui_verify` through the authenticated tool catalog.

The right source pane lets the user choose a line range and bind it with the
selected device. The composer displays the explicit per-message device task and
action budget, and lets the user remove it. Sending creates a version-bound Run;
the tool resolves the trusted OpenCode context session ID to that Run and owner.
No supplied tool argument can choose another Run. The Run stops when generation
finishes. Binding is unavailable until the bridge is configured. Before each prompt, the adapter updates the mapped session permissions using the
installed server schema: only source-read tools and the session-bound device tool
are allowed. This also migrates earlier sessions without granting shell or edit
permissions.

Model-driven Android action acceptance remains outstanding. Tool registration,
unit tests and source compilation alone are not evidence of autonomous execution.


Conversation task cards now read the authenticated Run/evidence endpoints and show
frozen source, actions, paired screenshots and independent verification results.
A real emulator observation through the session-bound bridge returned 27 UI nodes
and a saved screenshot for the Android launcher. This was an in-process transport
acceptance with no model invocation and no device actions; it is not autonomous
Agent acceptance. Raw evidence remains in ignored local experiment/Run storage.
