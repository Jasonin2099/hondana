# hondana 本棚

[![stars](https://img.shields.io/github/stars/Jasonin2099/hondana?style=flat&label=stars&color=1D1D1F&logo=github)](https://github.com/Jasonin2099/hondana/stargazers)
[![last commit](https://img.shields.io/github/last-commit/Jasonin2099/hondana?style=flat&label=last%20commit&color=1A7F37)](https://github.com/Jasonin2099/hondana/commits/main)
[![license](https://img.shields.io/github/license/Jasonin2099/hondana?style=flat&label=license&color=6E6E73)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3C3C43?style=flat&logo=python&logoColor=white)](https://www.python.org/)

[English](README.en.md) · [日本語](README.ja.md)

给日文 / 中日文书目做「搜得到、对得上」的小工具。零依赖，纯 Python。

做搜书的东西时总会碰到这种事：用户输入 `图书馆`，数据里写的是 `圖書館`；有人敲 `ﾊﾘｰ ﾎﾟｯﾀｰ`，书名是 `ハリー・ポッター`。hondana 把这些折叠成同一个比较用的 key，顺便带了一个 ISBN 查询，按 openBD → 国立国会図書館 → Google Books → Open Library 依次兜底。

> 现在是早期骨架版，字表只放了一小批常用字，够演示思路，不够覆盖所有情况。欢迎补字。

## 安装

```bash
pip install hondana-ja
# 或：pip install git+https://github.com/Jasonin2099/hondana
```

## 用法

```python
from hondana import fold, to_isbn13, hyphenate, lookup, lookup_many

fold("圖書館") == fold("图书馆") == fold("図書館")   # True
fold("ﾊﾘｰ・ﾎﾟｯﾀｰ") == fold("はりー ぽったー")         # True
to_isbn13("4-00-310101-4")                           # '9784003101018'
hyphenate("9784003101018")                           # '978-4-00-310101-8'（支持日本 978-4、英语区 978-0 / 978-1、中国 978-7、台湾 978-957 / 978-986）

book = lookup("9784003101018")                 # 走网络；查不到返回 None
book = lookup("9784003101018", merge=True)     # 多源合并，缺字段由后面的源补上
books = lookup_many(["978…", "978…"], rate=0.5)  # 批量查询，rate=每次间隔秒数
print(book.title, book.source)
```

命令行：

```bash
python -m hondana fold "ＡＢＣ　入門"
python -m hondana fold --explain "ﾊﾘｰ・ﾎﾟｯﾀｰ"   # 打印每一步的结果
python -m hondana isbn 9784003101018            # 校验并加连字符（不联网）
python -m hondana isbn "文中 ISBN 978-4-00-310101-8 …"  # 从文本里找出 ISBN
python -m hondana lookup 9784003101018          # 联网查询（JSON）
python -m hondana lookup --merge --format table 978… 978…
python -m hondana isbn --find < paper.txt | python -m hondana lookup   # 从 stdin 读 ISBN，默认每次间隔 0.5 秒（--rate 可改）
```

## `fold()` 做了什么

1. NFKC：全角英数→半角，半角片假名→全角
2. 旧字体 / 繁体 / 简体 → 新字体（小字表，见 `_tables.py`）
3. 片假名→平假名，去掉长音 `ー`（可选 `small_kana=True`：小写假名 ぁ→あ、っ→つ；`iteration_marks="expand"`/`"drop"`：处理 々 ゝ ゞ；`itaiji=True`：人名常见异体字 髙→高、﨑→崎；`dashes=True`：统一长音符、波浪号和各种破折号，コ─ヒ─→コーヒー）
4. 小写，去掉空格、标点和书名号

每一步都能单独关掉，比如 `fold(s, kana=False)`；`kana="kata"` 则反过来把平假名统一成片假名。

有些简体字在日文里是另一个字（机 / 機、干、后、叶），故意没收进字表，免得把不同的书混在一起。

为什么不直接用 NFKC：见 [docs/why-not-nfkc.md](docs/why-not-nfkc.md)（英文，附对照表）。

常见用法（整理去重书单、按用户输入搜索目录、检查论文参考文献里的 ISBN、批量补全书目信息、命令行管道）：见 [docs/recipes.md](docs/recipes.md)（英文，示例代码都在测试里跑过）。

## ISBN 查询

`lookup()` 每个来源各自 try，一个超时不会连累后面。`merge=True` 会查完 `order` 里的每个源，按字段取第一个非空值并拼接 `source`（如 `openBD+NDL`）。`lookup_many()` 按输入顺序批量查询，`rate` 控制两次之间的最短间隔秒数。想换 HTTP 库、加缓存或写测试，传一个自己的 `fetch(url, params, timeout) -> (status, text)` 进去就行。要简单的内存缓存可以用 `lookup(isbn, fetch=cached(ttl=3600))`。CiNii Books 是可选来源，默认不查，用 `order=(..., "cinii")` 打开（可设 `HONDANA_CINII_APPID`）。

## 测试

```bash
pip install pytest && python -m pytest -q
```

## 计划

见 [ROADMAP.md](ROADMAP.md)。

MIT License
