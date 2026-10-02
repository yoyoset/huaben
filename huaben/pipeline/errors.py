"""流水线的显式失败类型:调用方据此决定重试、告警还是提示用户。"""


class ChapterFailed(Exception):
    """某一步最终没能产出可入账的结果(已在 pipeline_runs 留痕)。
    step:outline / write / volume_plan / volume_seal / finalize;idx:章序号(卷级步骤为 None)。"""

    def __init__(self, message: str, step: str = "", idx: int | None = None):
        super().__init__(message)
        self.step = step
        self.idx = idx


class NoActiveVolume(ChapterFailed):
    """没有进行中的卷:需要先规划(volume.ensure_active_volume)。"""
