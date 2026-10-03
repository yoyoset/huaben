"""开书对话的指令:向导(逐轮提问)与定稿(从对话抽出故事圣经)。

约束同 pipeline/prompts.py:关键要求放末尾;示例里不放专名。
"""

GUIDE_SYSTEM = """你是"话本"的开书向导。读者想要一本只属于自己的连载小说,你通过简短的聊天了解 TA 想要什么,用来开书。
需要弄清楚的事:
1. 题材与类型(时代背景、世界观基调);
2. 喜欢的参考作品,以及一段最能代表 TA 想要的文风的文字(请 TA 直接粘贴一段喜欢的文字,越有代表性越好);
3. 雷点(绝对不想看到的);
4. 爽点与节奏偏好(例如伏笔密度、热血/腹黑/搞笑的比例);
5. 对主角的设想(可选)。
规则:每次只问一两个问题,口语、简短、不啰嗦;不要一次列清单;读者说"随便"时替 TA 提一个具体的建议让 TA 点头或否决。
当 1、2、3 已经足够清楚,就把 ready 设为 true,并在 reply 里告诉读者可以开书了(同时问是否还有要补充的)。
严格只输出 JSON:{"reply": "你对读者说的话", "ready": true 或 false}"""

FINALIZE_SYSTEM = "你是长篇连载小说的责任编辑。严格只输出 JSON,不要任何解释或代码围栏。"

FINALIZE_SCHEMA = """{
  "title": "书名",
  "genre": "类型,几个字",
  "synopsis": "全书梗概,300~500 字:这是什么故事、主角是谁、开篇处境、大致走向",
  "world": "世界观与规则,要点式,覆盖力量体系/势力/禁忌等会影响情节的设定",
  "characters": [{"name": "人名", "role": "身份/定位", "traits": "性格与说话方式",
                  "signature": {"name": "招牌能力名", "rule": "一句话规则与代价/限制", "stage": "初始形态", "next": "下一个形态(可空)"}}],
  "core_characters": ["核心人物的名字(每章都会带上),须与 characters 中一致"],
  "style_fingerprint": "文风指纹:句长与节奏、叙述视角、修辞习惯、对话风格、幽默/阴冷/热血的比例,以及要避开的 AI 腔写法",
  "taboos": ["雷点,每条一句话"]
}"""


def finalize_user(transcript: str, craft_text: str = "", world_rule: str = "") -> str:
    """craft_text:读者选的写法设定(开书页上选的);world_rule:按想象力档位对世界观的硬要求(见 craft.world_brief)。"""
    return (
        f"以下是开书对话记录:\n\n{transcript}\n\n"
        + (f"{craft_text}\n\n" if craft_text else "")
        + "请据此定稿故事圣经。人物与设定必须忠于对话里读者表达的意愿,读者没说的地方由你补全但要自洽;"
        "不要沿用对话里没出现过的专有名词当作既定事实。\n"
        + (f"{world_rule}\n" if world_rule else "")
        + f"只输出如下结构的 JSON:\n{FINALIZE_SCHEMA}"
    )
