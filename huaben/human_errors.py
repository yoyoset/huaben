"""把失败翻译成给读者看的人话:发生了什么 + 读者能做什么(或者"不用管,会自动重试")。

分层:技术细节(HTTP 状态、响应片段、异常栈)只进日志和 pipeline_runs;
界面上的 books.gen_error 与 API 错误文案只用这里的结果。
"""
from .llm import LLMError
from .pipeline.errors import ChapterFailed
from .tts.base import TTSError

AUTO = "稍后会自动重试,不用管。"

_LLM = {
    "no_key": "还没有配置模型密钥:请在右上角「⚙ 设置」里填写(或在服务器 .env 里填 HUABEN_OPENROUTER_API_KEY)。",
    "auth": "模型密钥无效或已失效:请在右上角「⚙ 设置」里更新密钥。",
    "quota": "OpenRouter 账户余额不足:充值后会自动继续。",
    "rate_limit": "模型调用太频繁被限流了," + AUTO,
    "server": "模型服务暂时不可用," + AUTO,
    "network": "连不上模型服务(网络问题)," + AUTO,
    "timeout": "模型调用卡住超过总时长上限,已放弃这一稿," + AUTO,
    "empty": "模型返回了空内容," + AUTO,
    "bad_response": "模型返回的内容无法识别," + AUTO,
    "budget": "过去 24 小时的模型花费已达上限,已暂停生成;额度回落后会自动继续。"
              "如需调整,改服务器 .env 里的 HUABEN_SPEND_LIMIT_USD_24H。",
    "request": "模型拒绝了这次请求(可能是模型名或参数配置有误):请检查 HUABEN_LLM_MODEL,详情见服务日志。",
}

_STEP = {
    "outline": "编辑没能给出可用的章纲",
    "write": "连续几稿都没通过核对",
    "volume_plan": "编辑没能给出可用的分卷规划",
    "volume_seal": "封卷总结没能完成",
    "finalize": "没能从对话里整理出故事设定",
    "volume": "这本书还没有进行中的分卷",
}


def explain(exc: BaseException, auto_retry: bool = True) -> str:
    """auto_retry:后台任务失败会自动重试("不用管");用户当场点的操作不会,要请用户再试。"""
    msg = _explain(exc)
    return msg if auto_retry else msg.replace(AUTO, MANUAL)


MANUAL = "请稍后再试一次。"


def _explain(exc: BaseException) -> str:
    if isinstance(exc, LLMError):
        return _LLM.get(exc.kind, _LLM["bad_response"])
    if isinstance(exc, ChapterFailed):
        where = f"第 {exc.idx} 章:" if exc.idx else ""
        return f"{where}{_STEP.get(exc.step, '生成没有成功')}," + AUTO
    if isinstance(exc, TTSError):
        return "配音服务暂时不可用,文字可以照常阅读;" + AUTO
    return "程序内部出错(已记录日志)," + AUTO + "如果一直出现,请把服务日志发给维护者。"
