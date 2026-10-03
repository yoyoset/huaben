"""每本书的"写法设定":叙事结构 / 文笔 / 想象力 / 伏笔布局 / 节奏 + 读者自己的补充要求。纯函数。

为什么(2026-10-03 用户):叙事要大师级——像诺兰那样有结构、更专业、更有艺术性,不要小孩子式的平铺直叙;
伏笔要有尾田式的超长线。这些在开书聊天时读者想不到去提,系统要主动给模板让人选,开书后也能改。
此前同一本书的风格只有"风格指纹"一段形容词,实测(2026-10-02,同一章对比)便宜模型照着形容词写不出效果,
换成"具体怎么写"的要求后明显改善——所以每个选项的说明都写成作者能照做的写法,而不是形容词。
"""

CATEGORIES: dict[str, tuple[str, dict[str, tuple[str, str]]]] = {
    "narrative": ("叙事结构", {
        "linear": ("线性顺叙", "按时间顺序讲,清楚好跟;只在关键处用少量插叙交代前因"),
        "braided": ("多线交织", "两三条故事线(不同人物或地点)交替推进、彼此呼应,在关键节点汇合;"
                                "章内可在线与线之间切换,切在悬念处"),
        "nonlinear": ("非线性·诺兰式", "打乱时间顺序:倒叙开场、插叙、多条时间线并行;利用读者与人物之间的信息差制造悬念与误导,"
                                     "真相分块给出,揭晓时让读者把前面的碎片重新拼合、恍然大悟。每次跳时间都要让读者清楚此刻在哪个时间点"),
        "ensemble": ("群像", "多个视角轮转,每章贴紧一个人物的视角与私心,各自只看到一部分,拼起来才是全貌"),
    }),
    "prose": ("文笔", {
        "light": ("轻快口语", "网文节奏,口语化短句,爽点直给,对白推动情节"),
        "literary": ("文学质感", "用画面、动作、物件和潜台词表现情绪,不直白解释人物心理;留白,意象前后呼应;对白有言外之意;"
                                "少用形容词和成语堆砌,不写总结性的感慨"),
        "cold": ("冷峻克制", "白描,节制,少形容词,情绪压在水面下,用细节而不是形容说话"),
        "classical": ("古典华丽", "辞采丰赡,讲究句式节奏与对仗,带古典小说韵味,但不能堆砌到影响叙事"),
    }),
    # 2026-10-03 用户:开书时说了四遍"放开想象力",出来的世界观还是炼气筑基金丹元婴 + 三大宗门 + 黑市 + 情报组织,
    # 前 4 章全是户籍、茶棚、山门核验——默认模板。想象力要成为一项明确的设定,并且落到"每卷/每章要有什么"上
    "imagination": ("想象力", {
        "conventional": ("类型惯例", "沿用这个类型读者熟悉的设定与桥段,好进入、好理解"),
        "fresh": ("有新意", "在熟悉的框架上做出自己的东西:每卷至少出现一个原创的设定、地方、职业、生物或制度,"
                            "有自己的运作规则和代价,并且真正推动情节;用到类型里用滥的桥段时必须给出新的转折"),
        # 用户举的例子:死神、火影、海贼王——设定各不相同但想象力丰富。提炼的是它们的做法,不是它们的设定
        "wild": ("大开脑洞", "像死神、火影、海贼王那样有自己的一套:①一个原创的核心力量机制,一句话说得清规则、有明确的代价或限制、"
                             "又能千变万化——每个重要角色的能力都独一无二,是他性格和经历的外化,有自己的命名和进阶形态;"
                             "②换一个地方就像换了一个世界,各有自己的规则、风俗和样子;③势力有鲜明的标志和理念。"
                             "不照搬类型默认模板(照抄五个修炼境界、宗门大比、拍卖会、秘境夺宝),也不照搬那几部作品的具体设定和名词;"
                             "每章都要有一样读者没见过的东西,写成可感的画面而不是解释,并且改变人物的处境"),
    }),
    "foreshadow": ("伏笔布局", {
        "light": ("轻", "以短线伏笔为主,埋下很快兑现,不留太多悬而未决"),
        "standard": ("标准", "短线、中线、长线搭配"),
        "deep": ("深埋·尾田式", "在短中长线之外,布置少数全书级超长线伏笔:早期一个不起眼的细节、一句话、一个物件,"
                               "几十上百章后翻出来改变全书的意义;平时偶尔轻轻回响,绝不点破"),
    }),
    "pacing": ("节奏", {
        "fast": ("快", "每章至少一个爽点或反转,不拖沓"),
        "balanced": ("张弛有度", "紧张与舒缓交替,高潮前有足够铺垫"),
        "slow": ("慢热", "重氛围与人物塑造,冲突逐步升级"),
    }),
}
DEFAULT = {"narrative": "linear", "prose": "literary", "imagination": "fresh", "foreshadow": "standard", "pacing": "balanced"}
NOTES_MAX = 1000


def normalize_craft(d) -> dict:
    """来自页面或数据库的写法设定 → 合法形状;认不出的项用默认值,补充要求截断到 NOTES_MAX。"""
    d = d if isinstance(d, dict) else {}
    out = {k: (d.get(k) if d.get(k) in CATEGORIES[k][1] else DEFAULT[k]) for k in CATEGORIES}
    out["notes"] = str(d.get("notes") or "").strip()[:NOTES_MAX]
    return out


def render_craft(craft) -> str:
    """写进章纲/正文/卷规划提示词的一段。"""
    c = normalize_craft(craft)
    lines = [f"- {CATEGORIES[k][0]}:{CATEGORIES[k][1][c[k]][0]}——{CATEGORIES[k][1][c[k]][1]}" for k in CATEGORIES]
    if c["notes"]:
        lines.append(f"- 读者的补充要求:{c['notes']}")
    return "【写法设定(读者选定,全书遵守)】\n" + "\n".join(lines)


def options_view() -> list[dict]:
    """给页面列选项用。"""
    return [{"key": k, "label": label, "default": DEFAULT[k],
             "choices": [{"value": v, "label": lab, "hint": hint} for v, (lab, hint) in choices.items()]}
            for k, (label, choices) in CATEGORIES.items()]


def from_book(book: dict | None) -> dict:
    """books.craft(JSON 文本;旧书为空)→ 写法设定。坏数据当默认,不让一本书因为这个写不下去。"""
    import json
    try:
        return normalize_craft(json.loads((book or {}).get("craft") or "{}"))
    except ValueError:
        return normalize_craft({})


# 搭世界观时的要求与采样温度。原来定稿圣经固定用 0.5(求稳),而且没有任何"要原创"的要求——
# 《算尽仙朝》开书对话里读者说了四遍放开想象力,世界观仍是类型默认模板。温度跟着想象力档位走。
WORLD_TEMPERATURE = {"conventional": 0.5, "fresh": 0.8, "wild": 1.0}
WORLD_RULE = ("world 里必须原创地设计出:【核心力量机制】名字、一句话规则、代价或限制、因人而异的变化与进阶形态;"
              "【地方】至少三个风格迥异、各有自己规则和风俗的地方;【势力】每个势力的鲜明标志与理念。"
              "不要照抄类型默认模板(如五个修炼境界、三大宗门、拍卖会、秘境夺宝),也不要照搬任何现成作品的设定和名词。")


def world_brief(craft) -> tuple[str, float]:
    """(写进"定稿圣经"指令的世界观要求, 采样温度)。类型惯例档不加要求。"""
    level = normalize_craft(craft)["imagination"]
    return ("" if level == "conventional" else WORLD_RULE), WORLD_TEMPERATURE[level]
