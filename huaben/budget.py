"""花费安全阀:过去 24 小时的模型花费达到上限就停止调用模型。

为什么需要:后台在无人值守地调用付费模型。程序缺陷、模型异常(例如每稿都被打回)、配置错误都可能让它
持续烧钱而没人发现。上限按**滚动 24 小时、全部书合计**计算(钱是同一个人的;滚动窗口不受时区影响)。

做法:用装饰器包住真正的 LLM 客户端(所有模型调用的唯一出口),调用前查一次已花费;超限抛
BudgetExceeded(属于 LLMError,沿用现有的"写进 gen_error + 退避"路径,无需各处特判)。
"""
import logging

from . import repo
from .db import connect
from .llm import LLM, LLMError, LLMResult

WINDOW_HOURS = 24
log = logging.getLogger("huaben.budget")


class BudgetExceeded(LLMError):
    def __init__(self, spent: float, limit: float):
        super().__init__(f"过去 {WINDOW_HOURS} 小时花费 ${spent:.4f} ≥ 上限 ${limit:.2f}", kind="budget")
        self.spent, self.limit = spent, limit


def spent_recently(conn, hours: int = WINDOW_HOURS) -> float:
    return repo.spent_usd(conn, hours)


class BudgetGuard:
    """LLM 的装饰器:接口与被包的客户端一致。limit_usd <= 0 表示不设上限。"""

    def __init__(self, llm: LLM, db_path, limit_usd: float):
        self._llm, self._db_path, self._limit = llm, db_path, limit_usd
        self._warned_unpriced = False  # 每个进程只告警一次;持续的可见性由 /api/health 与统计页从数据推导

    def spent(self) -> float:
        conn = connect(self._db_path, check_same_thread=False)
        try:
            return spent_recently(conn)
        finally:
            conn.close()

    def chat(self, messages, **kw) -> LLMResult:
        if self._limit > 0:
            spent = self.spent()
            if spent >= self._limit:
                raise BudgetExceeded(spent, self._limit)
        res = self._llm.chat(messages, **kw)
        if res.tokens_in + res.tokens_out > 0 and not res.cost_usd and not self._warned_unpriced:
            self._warned_unpriced = True
            log.warning("上游没有返回本次调用的费用(usage.cost):花费上限与统计里的金额将不可信。"
                        "若换了非 OpenRouter 的接口,请自行监控花费")
        return res


def spend_status(spent: float, remind_usd: float, limit_usd: float, unpriced_calls: int,
                 subscription: bool = False) -> dict:
    """给界面/运维看的花费状态。over_remind:超过提醒线(只提醒,不拦);reliable=False:有调用上游没报费用,金额偏低。
    subscription:当前走包月订阅(OpenCode Go)——不按量计费,两种提醒都不适用。"""
    return {
        "spent_usd": round(spent, 6), "remind_usd": remind_usd, "limit_usd": limit_usd,
        "over_remind": not subscription and remind_usd > 0 and spent >= remind_usd,
        "unpriced_calls": unpriced_calls, "reliable": subscription or unpriced_calls == 0,
        "billing": "subscription" if subscription else "metered",
    }
