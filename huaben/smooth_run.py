"""逐章接句:一章一次模型调用,章与章之间不共享任何东西。"""
from .pipeline.chop import comma_density
from .smooth import SMOOTH_TARGET, smooth_messages, smooth_problems


def smooth_chapter(llm, body: str, lines: list[str], attempts: int = 3) -> dict:
    """返回 {"text": 最终稿, "status": "ok" | "still_choppy" | "kept_original", "before": 密度, "after": 密度, "tries": 次数, "notes": [...]}"""
    before = comma_density(body)
    if before <= SMOOTH_TARGET:
        return {"text": body, "status": "ok", "before": before, "after": before, "tries": 0, "notes": []}
    feedback, best, best_d, tries, notes = [], None, None, 0, []
    for _ in range(attempts):
        res = llm.chat(smooth_messages(body, lines, feedback), max_tokens=12000, temperature=0.3)
        tries += 1
        if res.truncated:
            feedback = ["上一稿没有写完,必须从第一句改到最后一句。"]
            notes.append("truncated:上一稿被截断")
            continue
        problems = smooth_problems(body, res.text, lines)
        if problems:
            feedback, notes = problems, notes + problems
            continue
        d = comma_density(res.text)
        if d <= SMOOTH_TARGET:
            return {"text": res.text, "status": "ok", "before": before, "after": d, "tries": tries, "notes": notes}
        if best is None or d < best_d:
            best, best_d = res.text, d
        feedback = [f"还是太碎(每百字 {d:.1f} 个逗号,要降到 8 以下):把剩下的主谓之间、状语后面的逗号继续去掉。"]
    if best is not None:
        return {"text": best, "status": "still_choppy", "before": before, "after": best_d, "tries": tries,
                "notes": notes}
    return {"text": body, "status": "kept_original", "before": before, "after": before, "tries": tries, "notes": notes}
