"""端到端测试用的"剧本 LLM":不按调用顺序吐回复,而是读 prompt 判断这是哪一步、第几章,
返回确定性的内容。这样跑的是**真实的 prompt 组装**,断言才能覆盖"记忆/账本有没有被带进 prompt"。
"""
import json
import re

from huaben.llm import LLMResult

def body_for(n: int) -> str:
    """约 700 字,让"原文是否被带进 prompt"在体量上可观察;每章各不相同(否则会被"照抄前文"检查打回):
    每个 12 字窗口里都带章号。"""
    return "".join(f"第{n}章第{i}夜,风过{n}号竹林。" for i in range(45))


def _j(d) -> str:
    return json.dumps(d, ensure_ascii=False)


class ScriptedLLM:
    def __init__(self, vol_chapters: int = 10, contradiction_at: int | None = None):
        self.vol_chapters = vol_chapters
        self.contradiction_at = contradiction_at
        self._ledger_calls: dict[int, int] = {}
        self.write_prompts: dict[int, str] = {}   # 章序号 → 正文步骤的完整 prompt(取最后一次)
        self.steps: list[str] = []

    def chat(self, messages, *, max_tokens=None, temperature=0.9, json_mode=False) -> LLMResult:
        text = "\n".join(m["content"] for m in messages)
        user = messages[-1]["content"]
        if m := re.search(r"请规划第 (\d+) 卷", user):
            self.steps.append("volume_plan")
            k = int(m[1])
            modes = ["智斗骗局", "破案追查", "逃亡求生"]  # 每卷换一种打法,检验"往卷打法"会传给下一卷的规划
            arc = {"antagonist": f"第{k}卷对手", "motive": "他有他的道理", "stakes": "师门", "mode": modes[(k - 1) % 3],
                   "low_point_beat": 3, "low_point": "被逼到绝境", "cost": "失去一位同伴", "change": "格局改变"}
            return self._r(_j({"goal": f"第{k}卷目标", "beats": ["起", "承", "转", "合"], "plant": [], "resolve": [],
                               "target_chapters": self.vol_chapters, "arc": arc}))
        if "请封卷" in user:
            self.steps.append("volume_seal")
            k = int(re.search(r"本卷\(第(\d+)卷\)目标", user)[1])
            old = re.search(r"【旧世界设定定本】\n(.*?)\n\n", user, re.S)[1]
            facts = re.search(r"【本卷新确立的事实】\n(.*?)\n\n", user, re.S)[1]
            merged = [x for x in old.splitlines() if x != "(尚无)"] + [x for x in facts.splitlines() if x != "(无)"]
            return self._r(_j({"volume_summary": f"第{k}卷摘要", "synopsis": f"梗概至第{k}卷",
                               "canon": "\n".join(merged)}))
        if m := re.search(r"请为第 (\d+) 章写章纲工单", user):
            self.steps.append("outline")
            n = int(m[1])
            return self._r(_j({"title": f"章{n}", "outline": "老道的遗物引出新线索" if n == 25 else f"第{n}章事件",
                               "characters": ["沈照"], "foreshadows": [], "planned_reversals": [], "hook": "钩"}))
        if m := re.search(r"现在写第 (\d+) 章正文", user):
            self.steps.append("write")
            n = int(m[1])
            self.write_prompts[n] = text
            return self._r(f"（第{n}章）{body_for(n)}" + ("重写稿" if self._ledger_calls.get(n) else ""))
        if m := re.search(r"【第 (\d+) 章正文】", user):
            self.steps.append("ledger")
            return self._r(self._ledger(int(m[1])))
        raise AssertionError(f"ScriptedLLM 认不出这是哪一步: {user[:80]!r}")

    def _ledger(self, n: int) -> str:
        self._ledger_calls[n] = self._ledger_calls.get(n, 0) + 1
        chars = [{"name": "沈照", "location": f"第{n}章的地点"}]
        if n == 2:
            chars.append({"name": "老道", "location": "后山"})
        if n == 20:
            chars.append({"name": "老道", "alive": False})
        contradictions = []
        if n == self.contradiction_at and self._ledger_calls[n] == 1:
            contradictions = [{"what": "沈照的位置与账本矛盾", "planned": False}]
        return _j({
            "summary": f"第{n}章摘要", "characters": chars,
            "foreshadows_new": [{"content": f"第{n}章伏笔", "payoff_plan": "三章后"}] if n % 5 == 0 else [],
            # 第 5k 章埋的伏笔编号恰为 k;在第 5k+3 章回收
            "foreshadows_update": [{"id": (n - 3) // 5, "status": "resolved"}] if n % 5 == 3 and n > 3 else [],
            "facts": [f"第{n}章确立的事实"], "contradictions": contradictions})

    @staticmethod
    def _r(text: str) -> LLMResult:
        return LLMResult(text=text, tokens_in=100, tokens_out=200, cost_usd=0.001, duration_ms=5)
