"""MCP サーバー ⇔ TUI 間のブリッジプロトコル。

フレーミングは NDJSON（1 行 1 メッセージ）。メッセージは type を discriminator と
する tagged union。詳細は docs/dev/protocol.md を参照。
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

from agenttakt.models.plan import Plan


class ReviewMeta(BaseModel):
    summary: str | None = None
    cwd: str | None = None
    timestamp: str | None = None


class ReviewRequest(BaseModel):
    type: Literal["review_request"] = "review_request"
    request_id: str
    plan: Plan
    meta: ReviewMeta = Field(default_factory=ReviewMeta)


class ShowPlanRequest(BaseModel):
    """表示のみの依頼。TUI は受信直後に ack を返し、人間の操作を待たない。"""

    type: Literal["show_plan"] = "show_plan"
    request_id: str
    plan: Plan
    meta: ReviewMeta = Field(default_factory=ReviewMeta)


class Ack(BaseModel):
    type: Literal["ack"] = "ack"
    request_id: str


class ReviewResponse(BaseModel):
    type: Literal["review_response"] = "review_response"
    request_id: str
    decision: Literal["approved", "rejected"]
    plan: Plan
    reason: str | None = None


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    request_id: str | None = None
    code: str
    message: str


Message = Annotated[
    Union[ReviewRequest, ShowPlanRequest, Ack, ReviewResponse, ErrorMessage],
    Field(discriminator="type"),
]

_adapter: TypeAdapter[Message] = TypeAdapter(Message)


def encode(
    message: ReviewRequest | ShowPlanRequest | Ack | ReviewResponse | ErrorMessage,
) -> bytes:
    """1 行の NDJSON フレームにエンコードする。"""
    return message.model_dump_json().encode("utf-8") + b"\n"


def decode(line: bytes | str) -> Message:
    """NDJSON 1 行をメッセージにデコードする。不正なら pydantic.ValidationError。"""
    return _adapter.validate_json(line)
