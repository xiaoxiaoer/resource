"""
审核会话管理 — 内存存储
"""

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class AuditSession:
    session_id: str
    file_name: str = ""
    parsed_data: dict = field(default_factory=dict)
    business_type: str = ""  # parking_voucher / spot_exchange
    status: str = "created"  # created / parsing / ready / running / completed / error
    result: str = ""
    enable_llm: bool = False  # 是否启用 LLM 增强分析
    created_at: float = field(default_factory=time.time)


# 内存会话存储
_sessions: dict[str, AuditSession] = {}


def create_session() -> AuditSession:
    session = AuditSession(session_id=uuid.uuid4().hex[:12])
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> AuditSession | None:
    return _sessions.get(session_id)


def list_sessions() -> list[AuditSession]:
    return sorted(_sessions.values(), key=lambda s: s.created_at, reverse=True)
