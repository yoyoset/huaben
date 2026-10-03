# T024 安卓 App:阅读的三处小修

依赖:无(T020 已通过)。只动 `android/`。

## 为什么

T020 验收时发现的小毛病,以及它"这次不做"里留下的一项:

1. 阅读页现场取到一章并存下后,"上一章/下一章"按钮的可用状态不刷新。
2. 从阅读页返回书页,书页的章列表不刷新(阅读页新存下的章不出现)。
3. 只下了正文、没下音频的书,离线时书架上不列。

## 已定的方案

### 1. `ReadActivity.kt`

把 `show()` 开头"算上一章/下一章按钮可不可用"的那三行抽成一个私有函数 `updateNav()`;`show()` 里照旧调用它;
`fetch()` 里 `texts.save(...)` 成功之后,在 `runOnUiThread { ... }` 里(`render` 之前)也调用一次 `updateNav()`。

### 2. `BookActivity.kt`

`onStart()` 里 `super.onStart()` 之后加一行 `renderList()`。

### 3. 离线书架

- `Store.kt` 的 `Texts` 加两个方法:

  ```kotlin
  /** 存书名:离线书架要用。存在 filesDir/text/<书>/book.json = {"title": 书名}。 */
  fun saveBookTitle(book: Int, title: String)
  /** 下过正文的书:(书号, 书名),按书号排序。读不到书名的用 "第 $id 本书"。 */
  fun books(): List<Pair<Int, String>>
  ```

  `Texts.list(book)` 现在按"文件名是数字.json"认章,`book.json` 不是数字,不会被当成一章——加完后确认这一点没变。
- `BookActivity.download()`:存正文的那个循环之前加 `texts.saveBookTitle(book, bookTitle)`。
- `MainActivity.shelf()` 连不上服务器的那个分支:把 `downloads.books()` 换成"音频的书 + 正文的书"的并集(同一个书号只出现一次,书名优先用音频那边的),按书号排序;
  为此在 `MainActivity` 里加成员 `texts`(照 `downloads` 的初始化方式)。提示文字不变。

### 4. 其它

- `android/app/build.gradle.kts`:`versionCode = 3`,`versionName = "0.3"`。
- `android/README.md`"没做的"里删掉"只下了正文、没下音频的书,离线时书架上不列……"那一条。

## 验收标准

1. 构建成功(在 Windows 的 cmd 里;副本里没有 `android/local.properties` 时,照主仓库 `F:\my_ai\huaben\android\local.properties` 的内容建一份,它不进 git):

   ```
   cd /d <本仓库>\android
   set JAVA_HOME=F:\dev\jdk-17
   set GRADLE_USER_HOME=F:\dev\gradle-home
   F:\dev\gradle-8.10.2\bin\gradle.bat assembleDebug
   ```

   报告贴最后 15 行,要有 `BUILD SUCCESSFUL`。
2. `python -m pytest -q` 仍然全过(现在 497)。
3. 不要运行 `scripts/publish_apk.sh`。报告"没有实测的部分"照实写(没有真机)。

## 这次不做

- 不记一章之内读到哪、不做配色切换、不改服务器。

## 审核记录

通过 2026-10-04(执行:muse-spark-1.3,259 秒)。架构方在主仓库构建 BUILD SUCCESSFUL,507 全过;读了 diff,与方案一致。安装包 0.3 已发布。没有真机测试。
