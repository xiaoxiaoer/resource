"""
技能脚本调用器 — 通过子进程调用 BEM 和企查查脚本

子进程隔离 Playwright 浏览器，避免崩溃影响 web 服务。
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from web.config import SKILLS_DIR

logger = logging.getLogger(__name__)

BEM_SCRIPT = SKILLS_DIR / 'bem-fetch' / 'scripts' / 'fetch_all_reports.py'
COMPANY_SCRIPT = SKILLS_DIR / 'company-lookup' / 'scripts' / 'query_company_baidu.py'

# 子进程环境：强制 UTF-8，避免 Windows 默认 GBK 导致中文乱码
_SUBPROCESS_ENV = {**os.environ, 'PYTHONUTF8': '1'}


def _subprocess_run_sync(args: list[str], timeout: int) -> tuple[int, str, str]:
    """同步版子进程调用，供 asyncio.to_thread 使用。"""
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_SUBPROCESS_ENV,
            timeout=timeout,
        )
        return (
            proc.returncode,
            proc.stdout.decode('utf-8', errors='replace'),
            proc.stderr.decode('utf-8', errors='replace'),
        )
    except subprocess.TimeoutExpired:
        logger.error("子进程超时 (%ds): %s", timeout, ' '.join(args))
        return (-1, '', f'子进程超时 ({timeout}s)')


async def _run_subprocess(args: list[str], timeout: int = 180) -> tuple[int, str, str]:
    """启动子进程并返回 (returncode, stdout_str, stderr_str)，统一 UTF-8 解码。

    使用 subprocess.run + asyncio.to_thread 代替 asyncio.create_subprocess_exec，
    避免 Windows 上 uvicorn 的事件循环不支持子进程 (NotImplementedError)。
    """
    return await asyncio.to_thread(_subprocess_run_sync, args, timeout)


async def run_bem_fetch(car_park_name: str, date_range: str | None = None) -> dict:
    """调用 BEM 统一数据获取脚本"""
    args = [sys.executable, str(BEM_SCRIPT), '--car-park', car_park_name]
    if date_range:
        args.extend(['--date-range', date_range])

    logger.info("BEM fetch: %s", ' '.join(args))

    returncode, stdout_str, stderr_str = await _run_subprocess(args)

    logger.info("BEM fetch done: returncode=%d, stdout=%d bytes, stderr=%d bytes",
                returncode, len(stdout_str), len(stderr_str))

    if returncode != 0:
        # BEM 脚本出错时错误信息在 stdout（JSON），stderr 可能有 Playwright 日志
        try:
            result = json.loads(stdout_str)
            if isinstance(result, dict):
                result['_stderr'] = stderr_str[:500]
                logger.warning("BEM fetch error (from stdout): %s", result.get('error', '')[:200])
                return result
        except json.JSONDecodeError:
            pass
        logger.warning("BEM fetch error: rc=%d, stderr=%s", returncode, stderr_str[:200])
        return {
            'status': 'error',
            'error': stderr_str[:500] or stdout_str[:500],
            'returncode': returncode,
        }

    try:
        result = json.loads(stdout_str)
        # 摘要日志：数据量
        data = result.get('data', {})
        temp_count = len(data.get('temp_parking', {}).get('monthly', []))
        ticket_count = len(data.get('monthly_ticket', {}).get('monthly', []))
        logger.info("BEM fetch success: temp=%d months, ticket=%d months", temp_count, ticket_count)
        return result
    except json.JSONDecodeError as e:
        return {'status': 'error', 'error': f'JSON decode error: {e}', 'raw': stdout_str[:500]}


async def run_company_lookup(company_name: str) -> dict:
    """调用企查查/启信宝查询脚本"""
    args = [sys.executable, str(COMPANY_SCRIPT), '--company', company_name]

    returncode, stdout_str, stderr_str = await _run_subprocess(args)

    if returncode != 0:
        try:
            result = json.loads(stdout_str)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
        return {'status': 'error', 'error': stderr_str[:500] or stdout_str[:500]}

    try:
        return json.loads(stdout_str)
    except json.JSONDecodeError as e:
        return {'status': 'error', 'error': f'JSON decode error: {e}'}
