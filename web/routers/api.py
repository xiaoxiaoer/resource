"""REST API 路由"""

import json

from fastapi import APIRouter, UploadFile, File, HTTPException

from web.services.excel_parser import parse_audit_excel
from web.services.audit_session import create_session, get_session
from web.services.ai_orchestrator import build_prompt_context
from web.config import UPLOAD_DIR, ENABLE_LLM_AUDIT

router = APIRouter(prefix="/api")


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传 Excel/图片，解析返回结构化数据"""
    if not file.filename:
        raise HTTPException(400, "No filename")

    suffix = file.filename.rsplit('.', 1)[-1].lower()
    if suffix not in ('xlsx', 'xls', 'png', 'jpg', 'jpeg'):
        raise HTTPException(400, f"Unsupported file type: .{suffix}")

    # 保存文件
    session = create_session()
    session.file_name = file.filename
    save_path = UPLOAD_DIR / f"{session.session_id}.{suffix}"
    content = await file.read()
    save_path.write_bytes(content)

    session.status = "parsing"

    if suffix in ('xlsx', 'xls'):
        try:
            parsed = parse_audit_excel(save_path)
            session.parsed_data = parsed
            session.status = "ready"
        except Exception as e:
            session.status = "error"
            raise HTTPException(500, f"Excel parse error: {e}")
    else:
        # 图片暂时保存路径，后续由 image_parser 处理
        session.parsed_data = {
            "file_name": file.filename,
            "file_path": str(save_path),
            "business_type": "unknown",
            "note": "图片解析待实现",
        }
        session.status = "ready"

    return {
        "session_id": session.session_id,
        "file_name": session.file_name,
        "parsed_data": session.parsed_data,
        "status": session.status,
    }


@router.post("/audit/start")
async def start_audit(body: dict):
    """开始审核流程"""
    session_id = body.get("session_id")
    business_type = body.get("business_type", "parking_voucher")

    if not session_id:
        raise HTTPException(400, "session_id required")

    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if session.status not in ("ready", "created"):
        raise HTTPException(400, f"Session status is {session.status}, cannot start audit")

    session.business_type = business_type
    enable_llm = body.get("enable_llm")
    session.enable_llm = bool(enable_llm) if enable_llm is not None else ENABLE_LLM_AUDIT
    session.status = "running"

    return {
        "session_id": session.session_id,
        "status": "running",
        "stream_url": f"/api/audit/{session.session_id}/stream",
        "enable_llm": session.enable_llm,
    }


@router.get("/prompts/{business_type}")
async def get_prompt_context(business_type: str):
    """获取指定业务类型的 prompts 上下文约束"""
    if business_type not in ("parking_voucher", "spot_exchange"):
        raise HTTPException(400, f"Unsupported business_type: {business_type}")

    context = build_prompt_context(business_type)
    return {"business_type": business_type, "context": context}


@router.get("/audit/{session_id}")
async def get_audit_result(session_id: str):
    """获取审核结果"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    return {
        "session_id": session.session_id,
        "status": session.status,
        "business_type": session.business_type,
        "result": session.result,
    }
