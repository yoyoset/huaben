"""流水线的显式失败类型:调用方据此决定重试、告警还是提示用户。"""


class ChapterFailed(Exception):
    """某一步最终没能产出可入账的结果(已在 pipeline_runs 留痕)。"""


class NoActiveVolume(ChapterFailed):
    """没有进行中的卷:需要先规划(volume.ensure_active_volume)。"""
