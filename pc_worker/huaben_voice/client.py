"""与话本服务器打交道:取任务、交 MP3。只用 httpx,接受注入的 httpx.Client(测试直接传 FastAPI 的 TestClient)。"""
import httpx


class ServerError(Exception):
    pass


class VoiceClient:
    def __init__(self, http: httpx.Client, token: str = ""):
        self._http = http
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    @classmethod
    def connect(cls, server: str, token: str = "", timeout_s: float = 60.0) -> "VoiceClient":
        return cls(httpx.Client(base_url=server.rstrip("/"), timeout=timeout_s), token)

    def fetch_jobs(self, limit: int = 1) -> list[dict]:
        """[{book_id, idx, title, text}],按服务器排好的先后。取任务本身也是"我还在线"的心跳。"""
        r = self._http.get("/api/voice/jobs", params={"limit": limit}, headers=self._headers)
        if r.status_code != 200:
            raise ServerError(f"取任务失败 HTTP {r.status_code}: {r.text[:200]}")
        return r.json()

    def upload(self, book_id: int, idx: int, mp3: bytes) -> None:
        r = self._http.put(f"/api/voice/jobs/{book_id}/{idx}", content=mp3,
                           headers={**self._headers, "Content-Type": "audio/mpeg"})
        if r.status_code != 200:
            raise ServerError(f"交音频失败(第 {idx} 章)HTTP {r.status_code}: {r.text[:200]}")
