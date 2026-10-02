"""网页"设置"页保存的配置(键值对)。值优先于环境变量,见 huaben/llm_config.py。"""


def get_app_settings(conn) -> dict[str, str]:
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM app_settings")}


def set_app_settings(conn, values: dict[str, str]) -> None:
    """一次保存多项(同一事务):接口地址、模型、密钥要么一起生效,要么都不变。"""
    with conn:
        for k, v in values.items():
            conn.execute("INSERT INTO app_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET "
                         "value=excluded.value, updated_at=datetime('now')", (k, v))
