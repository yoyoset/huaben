# T022 书架:显示"已备稿、还没放出"的章数

依赖:无。

## 为什么

2026-10-03 用户导入了 30 章写好的正文,书架上只显示"已写 4 章",以为没更新。实际是:导入的正文也要等读者读到附近才定稿
(后台只比读者多备 3 章,见 `huaben/prep.py`),另外 26 章在库里等着,界面上看不出来。这张卡让书架把这个数显示出来。

## 已定的方案

### 1. `huaben/repo/scripts.py` 加一个函数,并在 `huaben/repo/__init__.py` 里导出(照同文件其它函数的导出方式)

```python
def count_pending_bodies(conn, book_id: int, after_idx: int) -> int:
    """导入了正文、章号大于 after_idx 的章数(= 备好了稿、还没定稿放出的)。"""
    return conn.execute("SELECT COUNT(*) FROM scripted_bodies WHERE book_id=? AND idx>?", (book_id, after_idx)).fetchone()[0]
```

### 2. `huaben/api/routes_books.py` 的 `book_view`

返回的字典里加一项(放在 `"ready_chapters"` 那一行后面;`ready_chapters` 的值先存进局部变量,不要查两次):

```python
"pending_drafts": repo.count_pending_bodies(conn, b["id"], ready),  # 导入了正文、还没放出的章数
```

### 3. `web/js/views/shelf.js` 的 `card()`

`progress` 那个模板字符串里,在 `已写 ${b.ready_chapters} 章` 后面紧接着加:

```js
${b.pending_drafts ? `(另有 ${b.pending_drafts} 章已备稿,读到附近或点「预备」就放出)` : ''}
```

其余不动。

### 4. 测试(新建 `tests/test_shelf_pending.py`)

- `count_pending_bodies`:照 `tests/test_script_text.py` 开头的办法导入一本剧本书和 3 章章纲,导入第 1、2、3 章正文 →
  `count_pending_bodies(conn, bid, 0) == 3`、`(conn, bid, 2) == 1`、`(conn, bid, 3) == 0`。
- `book_view`:同一本书还没写任何一章时,`book_view(conn, repo.get_book(conn, bid), S)["pending_drafts"] == 3`;
  没有导入正文的普通书 → 0。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化(现在 497)。
2. `tests/test_structure.py` 通过。

## 这次不做

- 不改"读到附近才放出"的规则,不做前端别的页面。

## 审核记录
