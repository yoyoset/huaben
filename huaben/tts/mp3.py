"""产物格式校验。前身踩坑:Edge TTS 插件默认吐 WebM/Opus,iOS 兼容性存疑 —— 入库前必须确认是 MP3。"""


def is_mp3(data: bytes) -> bool:
    if len(data) < 4:
        return False
    if data[:3] == b"ID3":  # ID3v2 标签开头
        return True
    return data[0] == 0xFF and (data[1] & 0xE0) == 0xE0  # MPEG 帧同步字
