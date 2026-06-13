import os
import time
import logging
import httpx
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.web import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web", tags=["web-repository"])

# 全局内存缓存，保存清洗后的数据
_cached_data = {
    "repo_info": None,
    "commits": None,
    "updated_at": None,  # 上一次成功获取的本地时间戳 (float)
}

# 缓存 TTL 为 3600 秒 (1小时)
CACHE_TTL = 3600

def format_iso_datetime(iso_str: str) -> str:
    """将 GitHub ISO8601 时间格式化为本地易读字符串"""
    if not iso_str:
        return ""
    try:
        iso_str = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_str)
        # 这里使用当前时区进行本地化呈现
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str

async def fetch_github_data() -> tuple[dict, list, bool]:
    """
    拉取 GitHub 仓库描述与最近 20 条 Commits 列表。
    优先读取 5 分钟内的内存缓存；如果接口报错/超时，只要有历史成功数据就进行缓存兜底。
    
    返回:
        (repo_info, commits_list, is_cached_or_fallback)
    """
    global _cached_data
    now = time.time()
    
    # 检查内存缓存是否仍在有效期内
    is_cache_valid = (
        _cached_data["updated_at"] is not None and 
        (now - _cached_data["updated_at"]) < CACHE_TTL
    )
    
    if is_cache_valid:
        return _cached_data["repo_info"], _cached_data["commits"], True
        
    # 尝试请求 GitHub API
    github_token = os.getenv("GITHUB_TOKEN")
    headers = {
        "User-Agent": "telegram-auto-message-server-web-app",
        "Accept": "application/vnd.github.v3+json",
    }
    if github_token:
        headers["Authorization"] = f"token {github_token}"
        
    repo_url = "https://api.github.com/repos/dunea/telegram-auto-message-server"
    commits_url = "https://api.github.com/repos/dunea/telegram-auto-message-server/commits?per_page=20"
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            # 1. 并步拉取仓库信息
            repo_resp = await client.get(repo_url, headers=headers)
            if repo_resp.status_code != 200:
                raise RuntimeError(f"GitHub API 仓库接口返回异常状态码: {repo_resp.status_code}")
            repo_info = repo_resp.json()
            
            # 2. 并步拉取最近 20 条 Commit 记录
            commits_resp = await client.get(commits_url, headers=headers)
            if commits_resp.status_code != 200:
                raise RuntimeError(f"GitHub API Commits 接口返回异常状态码: {commits_resp.status_code}")
            commits = commits_resp.json()
            
            # 清洗仓库数据，只保留页面渲染所需字段
            cleaned_repo = {
                "name": repo_info.get("name", "telegram-auto-message-server"),
                "full_name": repo_info.get("full_name", "dunea/telegram-auto-message-server"),
                "description": repo_info.get("description", "Telegram 自动消息服务端（FastAPI + Telethon + MySQL + APScheduler）"),
                "html_url": repo_info.get("html_url", "https://github.com/dunea/telegram-auto-message-server"),
                "stargazers_count": repo_info.get("stargazers_count", 0),
                "forks_count": repo_info.get("forks_count", 0),
                "open_issues_count": repo_info.get("open_issues_count", 0),
                "license": repo_info.get("license", {}).get("name") if repo_info.get("license") else None,
                "pushed_at": format_iso_datetime(repo_info.get("pushed_at")),
            }
            
            # 清洗 Commit 数据
            cleaned_commits = []
            for item in commits:
                sha = item.get("sha", "")
                commit_obj = item.get("commit", {})
                author_obj = item.get("author")  # 如果提交者邮箱未关联 GitHub 账号，这可能是 None
                
                commit_author = commit_obj.get("author", {})
                
                cleaned_commits.append({
                    "sha": sha,
                    "short_sha": sha[:7] if sha else "",
                    "message": commit_obj.get("message", ""),
                    "author_name": commit_author.get("name", "Unknown"),
                    "author_email": commit_author.get("email", ""),
                    "date": format_iso_datetime(commit_author.get("date")),
                    "avatar_url": author_obj.get("avatar_url") if author_obj else None,
                    "html_url": author_obj.get("html_url", "#") if author_obj else "#",
                })
                
            # 写入全局缓存
            _cached_data["repo_info"] = cleaned_repo
            _cached_data["commits"] = cleaned_commits
            _cached_data["updated_at"] = now
            
            return cleaned_repo, cleaned_commits, False
            
    except Exception as e:
        logger.warning(f"获取 GitHub 仓库数据失败: {e}。将尝试使用内存缓存数据兜底。")
        # 错误或超时兜底：如果存在历史成功缓存，则直接返回
        if _cached_data["repo_info"] is not None:
            return _cached_data["repo_info"], _cached_data["commits"], True
        # 否则，抛出异常交由路由拦截渲染
        raise e

@router.get("/repository", response_class=HTMLResponse)
async def repository_page(request: Request):
    """项目开源仓库描述与 Commits 时间线展示页"""
    error_msg = None
    repo_info = None
    commits = None
    is_cached = False
    cache_time_str = None
    
    try:
        repo_info, commits, is_cached = await fetch_github_data()
        if _cached_data["updated_at"]:
            dt = datetime.fromtimestamp(_cached_data["updated_at"])
            cache_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.exception("渲染项目仓库页面失败，无历史缓存可用")
        error_msg = "暂时无法获取仓库数据，请稍后重试。"
        
    return templates.TemplateResponse(request, "repository/index.html", {
        "repo_info": repo_info,
        "commits": commits,
        "is_cached": is_cached,
        "cache_time": cache_time_str,
        "error_detail": error_msg,
    })
