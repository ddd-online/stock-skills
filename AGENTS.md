# 仓库指南

自包含的 A 股实盘交易 Codex skills 集合。每个 skill 覆盖交易生命周期中的一个环节：分析（含持仓每日检查）、查找、计划、建仓与持仓、复盘、一次性初始化。

## 仓库结构与模块组织

每个 skill 都是仓库根目录下的一个 kebab-case 目录：

```
stock-skills/
├── <skill-name>/
│   ├── SKILL.md            # 必需：frontmatter（name、description）+ 工作流
│   ├── agents/openai.yaml  # 界面元数据：display_name、short_description、default_prompt
│   ├── references/         # 中文参考文档，按需加载
│   ├── scripts/            # 仅专属脚本（只用标准库）；真实取数集中在 market-data/scripts/
│   └── assets/             # 种子模板（setup-stock-workspace 的工作区种子、position-management 的个股模板）
├── README.md
└── AGENTS.md
```

现有 skills（10 个）：market-data（数据层）、stock-analysis（个股分析与持仓检查）、leader-find（龙头扫描）、limit-find（涨停板查找）、limit-lifecycle（题材生命周期）、limit-judge（打板竞价评估）、simmer-find（蓄力票发现）、stock-report（每日复盘）、position-management（资金与持仓档案）、setup-stock-workspace（一次性初始化）。

约定：

- SKILL.md 是唯一入口；references/ 与 scripts/ 一律相对 SKILL.md 解析路径。新增 skill 必须同时提供 SKILL.md 与 agents/openai.yaml。
- 元数据与篇幅：frontmatter description 只写「做什么 + 什么时候用 + 边界」，不罗列全部能力与触发词；agents/openai.yaml 的 short_description 控制在 25–64 字、default_prompt 一句话并点明 $skill-name。详细规格与示例放 references，SKILL.md 只留不可省略的硬性要求与指针，同一内容不在两处重复；报告类 skill 的硬性规则必须含「输出可视化」一条（数字进表格、趋势用箭头、状态用固定标记、不写散文式数字段、不用表情符号）。
- 真实取数统一放在 market-data，其他 skill 调用 $market-data，不自行实现取数脚本。
- 查找类 skill（leader-find、limit-find、simmer-find）不依赖工作区文件，可在任意目录运行；simmer-find 只读取 ACCOUNT.md「板块权限」用于排除无法买入的股票；limit-judge 不读工作区文件，但依赖 limit-find 落盘的上一份 report/涨停板复盘/YYYY-MM-DD.md 作为样本来源；limit-lifecycle 依赖 limit-find 落盘的当日 report/涨停板复盘/YYYY-MM-DD.md 作为输入（没有当日报告先执行 limit-find，报告写入 report/题材生命周期/YYYY-MM-DD.md），并只读取 ACCOUNT.md「板块权限」用于排除无法买入的股票。
- 不使用观察池，也不创建 WATCHLIST.md 等状态文件：stock-analysis 的分析模式只分析并输出报告，不落盘、不维护任何池或状态；「观察」只是报告里的等待中间态（触发条件与预案写在报告里，由用户自行盯）。同一 skill 的持仓检查模式只允许两处落盘——向既有 STOCK-REVIEW.md 追加每日检查行、回写 POSITION.md 现价与浮动盈亏（不建档、不改写交易计划）。
- 报告一律写入 report/<报告类型>/YYYY-MM-DD.md（如 report/龙头扫描/、report/涨停板复盘/、report/题材生命周期/、report/涨停板评估/、report/蓄力票扫描/）；中间产物不留残留，例如 limit-judge 的竞价清单（YYYY-MM-DD-竞价清单.txt）运行结束必须清理，其数据全部并进当日报告。
- 新增或移除 skill 时，同步更新本文件的 skill 清单与 README 的技能表、安装清单、示例提示词、调用约束。

## 常用命令

没有构建步骤，也不需要包管理器；脚本用 Python 3 直接运行，需联网：

```bash
python market-data/scripts/fetch_quote.py sh600410 --days 60
python market-data/scripts/fetch_fundamentals.py sz002491
python market-data/scripts/fetch_news.py sh600410 --news 3 --ann 3
python market-data/scripts/fetch_capital_flow.py sh600410
python market-data/scripts/fetch_strong_stocks.py --top 20
python market-data/scripts/fetch_limit_up.py --date 20260908
python market-data/scripts/fetch_auction.py --codes sh600410,sz002970 --top-board sz002790
```

数据来自腾讯与东方财富公开接口（无需密钥），只打印报告、不写缓存文件。脚本约定：

- 文本输出面向阅读，做精简（例如日K只列最近 15 根）；
- --json 输出全量字段供其他 skill 解析（例如日K返回全部请求根数，形态核验取 120/60 根时不截断）；
- --help 必须可用，参数错误给出明确提示；
- 改动脚本后至少跑一次真实数据，文本与 --json 两条分支都要验证。

只验证语法、不联网：

```bash
python -m py_compile market-data/scripts/fetch_quote.py
```

## 代码风格与命名约定

- Python：4 空格缩进，函数与变量 snake_case，UTF-8 编码，模块 docstring。
- 只用标准库，禁止引入第三方依赖。
- skill 目录用 kebab-case（如 stock-report）；脚本用 snake_case.py（如 fetch_quote.py）；工作区个股文件夹用「股票名称-股票代码」（如 华胜天成-600410）。
- 所有文件 UTF-8；脚本把 stdout 重新配置为 UTF-8，兼容非中文终端。
- 文档与注释一律中文，不出现课程、第 X 课、教学、作业、lesson 等字样——本仓库是知识集合，不是课程材料。
- Markdown 文档不使用 emoji。
- 阈值与规则写成「默认值 + 用户可覆盖」，不写死某个人的参数；个人参数放在运行时的用户请求或工作区文件中。

## 测试指引

仓库目前没有自动化测试。提交前用真实标的（如 sh600410）冒烟测试脚本并确认输出可解析；新增测试放在 tests/ 下，文件名 test_<module>.py。不要提交缓存产物——.gitignore 已覆盖 __pycache__/、*.pyc、.DS_Store、.vmark/。

## 数据真实性与安全

- 绝不编造行情数据；接口失败要明确报错或标「未获取」，不脑补数字。
- 不使用任何密钥，保持现状。
- skill 输出必须带「不构成投资建议」。
- 真实数据只经 market-data 获取，skill 文档不复制取数实现。

## 提交与发布约定

提交信息用简短中文并点名改动的 skill（如 `simmer-find: 调整回踩蓄力口径`），也可用 conventional commits（feat:/fix:/docs:）。

发布流程（每次发版按序执行）：

1. README「当前版本」改为新版本号：新增 skill 或功能升 minor，修复升 patch；
2. 提交改动并推送 main；
3. 打带注释的 tag（`git tag -a vX.Y.Z -m "版本 X.Y.Z"`）并推送 tag；
4. 建 Release（`gh release create vX.Y.Z --title "版本 X.Y.Z" --notes "..."`）。

PR 要求：

- 说明改了哪些 skill、为什么改。
- 关联相关 issue（如有）。
- 行为变化时附示例命令与输出。
- 确认脚本已用真实数据跑过，没有编造数字。

交流规则

* **必须**使用中文与用户对话
