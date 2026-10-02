"""端到端模拟:剧本 LLM 连载 35 章(每卷 10 章,跨 3 次封卷),核对架构文档里的核心承诺:
分层记忆让 prompt 体量不随章数增长、账本让人物/伏笔状态持续有效、卷封存不丢信息、失败不留空洞。
"""
import pytest

from huaben import repo
from huaben.config import Settings
from huaben.scheduler import top_up
from scripted_llm import ScriptedLLM

N = 35


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    from huaben.db import connect
    s = Settings(openrouter_api_key="x", chapter_words=1000, data_dir=tmp_path_factory.mktemp("e2e"), buffer_chapters=N, _env_file=None)
    conn = connect(s.db_path)
    bid = repo.create_book(conn, "夜行录")
    repo.update_book(conn, bid, status="serializing", synopsis="开篇梗概")
    repo.save_bible(conn, bid, world="灵气枯竭的王朝", style_fingerprint="短句,冷幽默", taboos=["现代梗"],
                    characters=[{"name": "沈照", "role": "主角", "traits": "腹黑"}])
    repo.upsert_character(conn, bid, "沈照", core=True)
    llm = ScriptedLLM(vol_chapters=10, contradiction_at=12)
    res = top_up(conn, llm, s, bid)
    assert res.error == "" and res.generated == N
    return conn, bid, llm


def test_all_chapters_contiguous_and_summarised(world):
    conn, bid, _ = world
    chs = repo.accepted_chapters(conn, bid)
    assert [c["idx"] for c in chs] == list(range(1, N + 1))
    assert all(c["summary"] and c["body"] for c in chs)


def test_volumes_rolled_over_with_sealed_summaries(world):
    conn, bid, _ = world
    vols = repo.list_volumes(conn, bid)
    assert [(v["idx"], v["status"]) for v in vols] == [(1, "sealed"), (2, "sealed"), (3, "sealed"), (4, "active")]
    assert [v["summary"] for v in vols[:3]] == ["第1卷摘要", "第2卷摘要", "第3卷摘要"]
    per_vol = {}
    for c in repo.accepted_chapters(conn, bid):
        per_vol[c["volume_id"]] = per_vol.get(c["volume_id"], 0) + 1
    assert sorted(per_vol.values()) == [5, 10, 10, 10]
    assert repo.get_book(conn, bid)["synopsis"] == "梗概至第3卷"  # 每次封卷都刷新了全书梗概


def test_prompt_size_is_bounded_not_linear(world):
    """架构核心承诺:第 N 章的 prompt 体量不随 N 线性增长(封卷压缩 + 只带最近 3 章原文)。"""
    _, _, llm = world
    p15, p25, p35 = (len(llm.write_prompts[n]) for n in (15, 25, 35))
    total_text = sum(len(f"（第{n}章）") + 600 for n in range(1, 35))
    assert p35 < p15 * 1.25 and p25 < p15 * 1.25
    assert p35 < total_text * 0.3  # 远小于"把前文全塞进去"


def test_recent_original_text_in_prompt_old_text_only_as_summary(world):
    _, _, llm = world
    p = llm.write_prompts[35]
    assert "（第34章）" in p and "（第32章）" in p            # 最近 3 章原文
    assert "（第10章）" not in p and "（第30章）" not in p   # 更早的原文不带
    assert "第31章《章31》:第31章摘要" in p                  # 本卷更早章只带摘要
    assert "第1卷:第1卷摘要" in p and "第3卷:第3卷摘要" in p  # 往卷摘要都在
    assert "梗概至第3卷" in p                                # 全书梗概是封卷后刷新的


def test_foreshadow_ledger_tracks_plant_and_payoff(world):
    conn, bid, _ = world
    fs = repo.list_foreshadows(conn, bid)
    assert [f["planted_ch"] for f in fs] == [5, 10, 15, 20, 25, 30, 35]
    resolved = {f["planted_ch"]: f["resolved_ch"] for f in fs if f["status"] == "resolved"}
    assert resolved == {5: 8, 10: 13, 15: 18, 20: 23, 25: 28, 30: 33}  # 每个都在埋下 3 章后回收
    assert [f["planted_ch"] for f in repo.list_foreshadows(conn, bid, open_only=True)] == [35]
    assert "第35章伏笔" not in world[2].write_prompts[35]  # 本章刚埋的,还没进账本(入账在写完之后)
    assert "第30章伏笔" in world[2].write_prompts[32]       # 未回收的伏笔会出现在后续章的 prompt 里


def test_character_state_persists_and_is_loaded_selectively(world):
    _, _, llm = world
    assert "老道" not in llm.write_prompts[24]               # 非核心人物,章纲没提 → 不占 prompt
    assert "老道(已死亡)" in llm.write_prompts[25]           # 章纲提到 → 带上,且是死亡状态(防复活)
    assert "沈照(存活)" in llm.write_prompts[35]             # 核心人物每章都在


def test_contradiction_triggered_exactly_one_rewrite(world):
    conn, bid, llm = world
    assert repo.get_chapter(conn, bid, 12)["attempts"] == 2
    assert all(repo.get_chapter(conn, bid, n)["attempts"] == 1 for n in range(1, N + 1) if n != 12)
    assert "重写稿" in repo.get_chapter(conn, bid, 12)["body"]
    assert "沈照的位置与账本矛盾" in llm.write_prompts[12]    # 打回的理由被带进了重写的 prompt
    failures = conn.execute("SELECT COUNT(*) FROM pipeline_runs WHERE ok=0").fetchone()[0]
    assert failures == 1                                       # 整个连载里只有这一次核对失败


def test_observability_covers_every_step(world):
    conn, bid, llm = world
    s = repo.cost_summary(conn, bid)
    assert s["chapters"] == N and s["avg_cost_usd"] > 0
    steps = {r[0] for r in conn.execute("SELECT DISTINCT step FROM pipeline_runs")}
    assert {"outline", "write", "ledger", "check", "volume_plan", "volume_seal"} <= steps
    assert llm.steps.count("volume_seal") == 3 and llm.steps.count("volume_plan") == 4
    assert repo.buffered_ahead(conn, bid) == N


def test_world_facts_survive_volume_seals_via_canon(world):
    """第 1 章确立的事实到第 35 章仍在 prompt 里(经定本),本卷的事实逐条在;不再按条数截断丢掉最早的。"""
    conn, bid, llm = world
    p = llm.write_prompts[35]
    canon_part = p.split("【账本·世界设定定本")[1].split("【账本·本卷新确立的事实】")[0]
    assert "第1章确立的事实" in canon_part and "第30章确立的事实" in canon_part
    current_part = p.split("【账本·本卷新确立的事实】")[1]
    assert "第34章确立的事实" in current_part and "第30章确立的事实" not in current_part
    assert repo.get_bible(conn, bid)["canon"].count("确立的事实") == 30  # 3 次封卷,每次并入一卷
