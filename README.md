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
pip install git+https://github.com/Jasonin2099/hondana
```

## 用法

```python
from hondana import fold, to_isbn13, lookup

fold("圖書館") == fold("图书馆") == fold("図書館")   # True
fold("ﾊﾘｰ・ﾎﾟｯﾀｰ") == fold("はりー ぽったー")         # True
to_isbn13("4-00-310101-4")                           # '9784003101018'

book = lookup("9784003101018")    # 走网络；查不到返回 None
print(book.title, book.source)
```

命令行：

```bash
python -m hondana fold "ＡＢＣ　入門"
python -m hondana isbn 9784003101018
```

## `fold()` 做了什么

1. NFKC：全角英数→半角，半角片假名→全角
2. 旧字体 / 繁体 / 简体 → 新字体（小字表，见 `_tables.py`）
3. 片假名→平假名，去掉长音 `ー`（可选 `small_kana=True`：小写假名 ぁ→あ、っ→つ）
4. 小写，去掉空格、标点和书名号

每一步都能单独关掉，比如 `fold(s, kana=False)`。

有些简体字在日文里是另一个字（机 / 機、干、后、叶），故意没收进字表，免得把不同的书混在一起。

## ISBN 查询

`lookup()` 每个来源各自 try，一个超时不会连累后面。想换 HTTP 库、加缓存或写测试，传一个自己的 `fetch(url, params, timeout) -> (status, text)` 进去就行。

## 测试

```bash
pip install pytest && python -m pytest -q
```

## 计划

见 [ROADMAP.md](ROADMAP.md)。

MIT License
