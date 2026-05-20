import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

# BEM 系统
BEM_BASE_URL = os.getenv('BEM_BASE_URL', 'https://bemaomp.yidianting.xin')
BEM_USERNAME = os.getenv('BEM_USERNAME')
BEM_PASSWORD = os.getenv('BEM_PASSWORD')

# LLM 配置（OpenAI 兼容）
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.deepseek.com')
LLM_MODEL = os.getenv('LLM_MODEL', 'deepseek-chat')

# 审核模式总开关：true 时启用 LLM 增强分析；默认 false 走纯程序化校验
ENABLE_LLM_AUDIT = os.getenv('ENABLE_LLM_AUDIT', 'false').lower() in ('true', '1', 'yes')

# 路径常量
SKILLS_DIR = BASE_DIR / 'skills'
PROMPTS_DIR = BASE_DIR / 'prompts'
TEMPLATES_DIR = BASE_DIR / 'templates'
DOC_DIR = BASE_DIR / 'doc'
UPLOAD_DIR = BASE_DIR / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)
