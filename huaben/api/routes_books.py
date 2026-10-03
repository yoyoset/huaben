"""书架:列表 / 新建 / 详情 / 统计。"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from .. import cast, foreshadow_report, repo, stats
from ..prep import book_buffer_target
from ..tts.store import best_playable, index_paths
from ..voice_queue import unplayable_count
from .deps import book_or_404, get_conn
from .routes_profiles import profile_or_404

router = APIRouter(prefix="/api/books", tags=["books"])


class NewBook(BaseModel):
    title: str = Field(default="未命名", max_length=100)
    profile_id: int | None = None  # 开在谁的书架上;前端总会带上


def book_view(conn, b: dict, settings) -> dict:
    """generating = 后台还会继续补货(缓冲没满),前端据此决定要不要自动刷新。"""
    buffered = repo.buffered_ahead(conn, b["id"])
    buffer_target = book_buffer_target(b, settings.buffer_chapters)
    return {
        "id": b["id"], "title": b["title"], "genre": b["genre"], "status": b["status"],
        "profile_id": b["profile_id"],
        "read_pos": b["read_pos"],        # 读到的最远章
        "last_opened": b["last_opened"],  # 续读位置(最后打开/播放的章)
        "synopsis": b["synopsis"],
        "ready_chapters": repo.count_accepted(conn, b["id"]),
        "buffered_ahead": buffered,
        "generating": b["status"] == "serializing" and buffered < buffer_target,
        "gen_error": b["gen_error"],      # 非空 = 后台写文字遇到问题,界面应提示
        "audio_error": b["audio_error"],  # 非空 = 配音遇到问题(文字照常可读)
        "audio_pending": unplayable_count(conn, settings, b["id"]),  # 还没有能播音频的章数(等电脑配音)
    }


@router.get("")
def list_books(request: Request, profile: int | None = None, conn=Depends(get_conn)):
    """profile:只看这个人的书架(前端总会带上);不带则列出全部。读者不存在回 404,前端据此回到"谁在看"。"""
    if profile is not None:
        profile_or_404(conn, profile)
    settings = request.app.state.settings
    return [book_view(conn, b, settings) for b in repo.list_books(conn, profile)]


@router.post("", status_code=201)
def create_book(body: NewBook, request: Request, conn=Depends(get_conn)):
    if body.profile_id is not None:
        profile_or_404(conn, body.profile_id)
    book = repo.get_book(conn, repo.create_book(conn, body.title, profile_id=body.profile_id))
    return book_view(conn, book, request.app.state.settings)


@router.get("/{book_id}")
def get_book(book_id: int, request: Request, conn=Depends(get_conn)):
    return book_view(conn, book_or_404(conn, book_id), request.app.state.settings)


@router.get("/{book_id}/stats")
def book_stats(book_id: int, request: Request, conn=Depends(get_conn)):
    """可观测:单章平均成本/耗时、重写率、配音覆盖、失败分布(口径见 huaben/stats.py)。"""
    book_or_404(conn, book_id)
    settings = request.app.state.settings
    out = stats.book_stats(conn, book_id, audio_ok=lambda c: best_playable(settings, index_paths(c)) is not None)
    out["prompt"] = _prompt_size(conn, book_id, settings)
    return out


def _prompt_size(conn, book_id: int, settings) -> dict:
    """下一章实际会发的 prompt 体量(路线 68)。读库失败不影响统计本身。"""
    try:
        from ..context import load_context
        from ..prompt_size import measure
        return measure(load_context(conn, book_id, settings.recent_chapters_in_prompt), settings.chapter_words)
    except Exception:  # noqa: BLE001 —— 只是观测,不能因为它让统计页打不开
        return {}


@router.get("/{book_id}/foreshadows")
def foreshadows(book_id: int, conn=Depends(get_conn)):
    """伏笔回收报告:按卷的计划/实收/未收 + 全书汇总(v0 验收:"卷内伏笔有回收记录")。"""
    book_or_404(conn, book_id)
    return foreshadow_report.load(conn, book_id)


@router.get("/{book_id}/cast")
def cast_view(book_id: int, conn=Depends(get_conn)):
    """人物志:账本里的人物现状(招牌能力/阶段、关系、知情)整理成一页可读的列表(路线 61)。"""
    book_or_404(conn, book_id)
    return {"characters": cast.build(repo.list_characters(conn, book_id), repo.get_bible(conn, book_id))}
