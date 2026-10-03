# T026 "备 N 章":N 指"再往后多备 N 章",不是"从当前章数 N 章"

依赖:无。

## 为什么

2026-10-04 用户实测:已写好 4 章、读到第 1 章,点"备 10 章",备的是第 1~10 章(只多了 6 章);用户以为是第 5~14 章。
现在的规则是"从正在读的那章起连续 N 章"(`huaben/prep.py` 的 `prep_range`),已经写好的章也算在 N 里,所以点了之后新增的章数说不准。
改成用户理解的那样:**在已经写好的基础上,再往后多备 N 章**;下载和进度显示的范围仍从正在读的那章开始。

## 已定的方案

### 1. `huaben/prep.py`

`prep_range` 改成(文件开头的说明文字和函数说明一起改,写清新规则和上面的来历):

```python
def prep_range(last_opened: int, written: int, n: int) -> tuple[int, int]:
    """起点 = 正在读/听的那章;终点 = 已写好的最后一章再往后 n 章(n 一次最多 MAX_PREP)。
    written:已写好的章数(章号连续,从 1 起)。读者停在比已写好更靠后的地方(不该出现)时,从他停的那章往后数。"""
    start = max(1, last_opened)
    return start, max(written, start - 1) + max(1, min(n, MAX_PREP))
```

### 2. `huaben/api/routes_prep.py`

`prepare()` 里改成 `_, end = prep_range(book["last_opened"], repo.count_accepted(conn, book_id), body.count)`。别的不动。
文件开头说明里那句"从当前章起预备 count 章"改成"在已写好的基础上再往后备 count 章"。

### 3. 界面文字

- `web/js/views/prep.js`:两个按钮的文字 `备 10 章` → `再备 10 章`,`备 20 章` → `再备 20 章`。
- `android/app/src/main/java/com/huaben/app/BookActivity.kt`:两个按钮 `备 10 章` → `再备 10 章`、`备 20 章` → `再备 20 章`;
  `还没有备好的章:先点「备 10 章」` 里的按钮名同样改成 `再备 10 章`。别的文字不动。
- `android/app/build.gradle.kts`:`versionCode = 4`,`versionName = "0.4"`。

### 4. 测试(改 `tests/test_prep.py`)

`test_range_starts_at_current_chapter_and_is_capped` 改成:

```python
def test_range_adds_n_beyond_what_is_written():
    assert prep_range(1, 4, 10) == (1, 14)     # 用户实测的情形:写好 4 章,再备 10 章 → 备到第 14 章
    assert prep_range(5, 8, 10) == (5, 18)
    assert prep_range(0, 0, 10) == (1, 10)     # 还没写、还没读
    assert prep_range(1, 4, 999) == (1, 54)    # 一次最多再备 50 章
    assert prep_range(9, 4, 10) == (9, 18)     # 读者停在已写好之后(不该出现):从他停的那章往后数
```

同文件里其它用到"预备"的测试,断言里的章号若因新规则变了,按新规则改,并在报告"做了什么"里逐条写出改了哪个断言、旧值新值。
其它测试文件里若有因此失败的,同样处理。

## 验收标准

1. `python -m pytest -q` 全过;报告写清测试总数变化(现在 507)。
2. `tests/test_structure.py` 通过。
3. 安卓构建成功(命令见 T024 的验收标准 1),报告贴最后 15 行。
4. 不要部署,不要发布安装包。

## 这次不做

- 不改"平时只比读者多备 3 章"的规则,不改 `MAX_PREP`。

## 审核记录

通过 2026-10-04(执行:glm-5.3-flash,992 秒——这次比它做 T022 慢得多,时间花在安卓构建上)。
架构方重跑:`python -m pytest -q` 507 全过;主仓库安卓构建 BUILD SUCCESSFUL;diff 与方案一致,`test_prep.py` 里另一处断言(2~11 → 2~13)改得对并在报告里写了。已部署,安装包 0.4 已发布。
