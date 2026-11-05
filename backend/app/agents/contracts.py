"""Provider-neutral conversation contracts.

Adapters advertise only implemented capabilities. Transport details and upstream
session IDs stay behind the authenticated application boundary.
"""
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal, Protocol


@dataclass(frozen=True)
class Capabilities:
    persistent_sessions: bool = False
    streaming_text: bool = False
    tool_events: bool = False
    cancellation: bool = False
    permission_requests: bool = False
    model_selection: bool = False
    attachments: bool = False


@dataclass(frozen=True)
class Conversation:
    owner: str
    local_id: str
    project_id: str
    directory: str
    remote_id: str


@dataclass(frozen=True)
class AgentEvent:
    kind: Literal['text_delta', 'text_snapshot', 'tool', 'permission', 'status', 'error', 'done']
    payload: dict[str, Any] = field(default_factory=dict)


class ConversationAdapter(Protocol):
    id: str
    capabilities: Capabilities

    async def health(self) -> dict[str, Any]: ...

    async def create(self, *, directory: str, title: str) -> str: ...

    def send(self, conversation: Conversation, text: str,
             model: dict[str, str] | None = None) -> AsyncIterator[AgentEvent]: ...

    async def abort(self, conversation: Conversation) -> None: ...

    async def permission(self, conversation: Conversation, request_id: str,
                         response: Literal['once', 'always', 'reject']) -> None: ...
