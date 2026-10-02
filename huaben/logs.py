"""结构化日志:每行自动带上"哪本书、第几章",方便在 docker logs 里 grep 一本书/一章的完整经过。

用 contextvars 携带上下文:调度器进入一本书时 `with log_context(book=3):`,流水线进入一章时再加 `chapter=12`,
其间任何模块的日志都会带上 `book=3 ch=12`,不用层层传参。格式是 key=value(logfmt 风格),人读机读都方便。
"""
import contextvars
import logging
from contextlib import contextmanager

_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("huaben_log_ctx", default={})
_SHORT = {"book": "book", "chapter": "ch"}

FORMAT = "%(asctime)s %(levelname)s %(name)s%(ctx)s %(message)s"


@contextmanager
def log_context(**fields):
    """在 with 块内给日志加上下文字段;嵌套时合并,退出时恢复。"""
    token = _ctx.set({**_ctx.get(), **{k: v for k, v in fields.items() if v is not None}})
    try:
        yield
    finally:
        _ctx.reset(token)


def render_ctx(ctx: dict) -> str:
    if not ctx:
        return ""
    return " [" + " ".join(f"{_SHORT.get(k, k)}={v}" for k, v in ctx.items()) + "]"


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.ctx = render_ctx(_ctx.get())
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(FORMAT))
    handler.addFilter(ContextFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
