"""SSE 流式端点"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from web.services.audit_session import get_session
from web.services.ai_orchestrator import run_audit

router = APIRouter()


@router.get("/api/audit/{session_id}/stream")
async def audit_stream(session_id: str):
    """SSE 端点：流式返回 AI 审核过程和结果"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if session.status != "running":
        raise HTTPException(400, f"Session status is {session.status}, not running")

    async def event_generator():
        try:
            async for event_str in run_audit(
                business_type=session.business_type,
                parsed_data=session.parsed_data,
            ):
                yield event_str

                # 检查是否是最终结果事件
                if event_str.startswith("event: result"):
                    import json
                    data_line = event_str.split("data: ", 1)[1].strip()
                    result_data = json.loads(data_line)
                    session.result = result_data.get("markdown", "")
                    session.status = "completed"

        except Exception as e:
            import json
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
            session.status = "error"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
