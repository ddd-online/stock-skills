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

现有 skills（9 个）：market-data（数据层）、stock-analysis（个股分析与持仓检查）、leader-find（板块龙头查找）、limit-find（涨停板查找）、limit-lifecycle（题材生命周期）、limit-judge（打板竞价评估）、stock-report（每日复盘）、position-management（资金与持仓档案）、setup-stock-workspace（一次性初始化）。

约定：

- SKILL.md 是唯一入口；references/ 与 scripts/ 一律相对 SKILL.md 解析路径。新增 skill 必须同时提供 SKILL.md 与 agents/openai.yaml。
- 元数据与篇幅：frontmatter description 只写「做什么 + 什么时候用 + 边界」，不罗列全部能力与触发词；agents/openai.yaml 的 short_description 控制在 25–64 字、default_prompt 一句话并点明 $skill-name。详细规格与示例放 references，SKILL.md 只留不可省略的硬性要求与指针，同一内容不在两处重复；报告类 skill 的硬性规则必须含「输出可视化」一条（数字进表格、趋势用箭头、状态用固定标记、不写散文式数字段、不用表情符号）。
- 真实取数统一放在 market-data，其他 skill 调用 $market-data，不自行实现取数脚本。
- 东财行情中心接口（push2 clist / stock 系列）可能不可用：market-data/scripts/fallback_sources.py 汇总腾讯行情与日K、新浪行情榜与个股资金流、东财数据中心 F10「所属板块」（按 BK 代码）与一级行业，供板块行情榜/板块成分股榜/板块财务排名/强势股榜/资金流向五个脚本自动切源；新增或改动取数脚本时沿用同一模块，输出必须标注实际数据源与口径差异（跨源数值不可混比）。
- 取数脚本的网络层约定：market-data/scripts 的网络层统一走同目录的 http_util.py（`_open = http_util.open_url`），一律「直连优先、系统代理兜底」——Windows 注册表代理（如 127.0.0.1:7890）会被 Python urllib 自动采用，实测该代理转发东财 push2 接口时连接被立即关闭（RemoteDisconnected），故先走无代理直连（ProxyHandler({})）、连续失败 3 次后再回退系统代理，回退后每 20 次请求重试一次直连；东财节点列表除 push2 / push2delay 外还带镜像 push2test.eastmoney.com（主节点被限流时的可用节点，覆盖 clist / ulist.np / stock / fflow / kline 路径；注意该镜像的 kline 路径返回空数据，取日K的脚本需保留腾讯日K兜底并标 ≈）。新增或改动取数脚本时保留这两层，否则会在代理环境或东财限流时整体取不到数；另注意 fetch_sector_boards.py --search 会翻完整板块列表，单次会话连续调用超过 5–6 次易触发东财限流，取多个板块代码时优先复用已有 BK 代码或分批间隔调用。
- 取数脚本的「未获取」约定：接口没返回或取不到时，字段一律 None/「-」并在输出里标「未获取」，不得填 0 或改用本机时间/最近一根K线冒充；「接口没数据」与「当日确实为 0」必须区分（如 fetch_limit_up 在非交易日/超出接口覆盖时输出 data_available=false 并以退出码 1 报错）；板块类脚本在东财字段整列缺失（如 f109/f160/f10 返回 "-"）时必须在输出里写明该列未获取，不得静默留空。
- 板块字段的口径陷阱（实测记录）：东财镜像节点的 f160（近10日）与 f109（近5日）逐行同值，10 日维度不可用；个股的 f109/f160/f10（量比）在该节点返回 "-"；资金流老字段 f178（近5日主力序列）在三节点均返回空串，故近5日主力改用 fflow/kline?lmt=5 自算。取这些字段时按上述实测行为处理，不要假设字段可用。
- 查找类 skill（leader-find、limit-find）不依赖工作区文件，可在任意目录运行；leader-find 必须传入一个板块参数（板块名或 BK 代码），未给板块时不运行、先向用户索取，也不做全市场扫描；limit-judge 不读工作区文件，但依赖 limit-find 落盘的上一份 report/涨停板复盘/YYYY-MM-DD.md 作为样本来源；limit-lifecycle 依赖 limit-find 落盘的当日 report/涨停板复盘/YYYY-MM-DD.md 作为输入（没有当日报告先执行 limit-find，报告写入 report/题材生命周期/YYYY-MM-DD.md），并只读取 ACCOUNT.md「板块权限」用于排除无法买入的股票。
- 不使用观察池，也不创建 WATCHLIST.md 等状态文件：stock-analysis 的分析模式只分析并输出报告，不落盘、不维护任何池或状态；「观察」只是报告里的等待中间态（触发条件与预案写在报告里，由用户自行盯）。同一 skill 的持仓检查模式只允许两处落盘——向既有 STOCK-REVIEW.md 追加每日检查行、回写 POSITION.md 现价与浮动盈亏（不建档、不改写交易计划）。
- 报告一律写入 report/<报告类型>/YYYY-MM-DD.md（如 report/涨停板复盘/、report/题材生命周期/、report/涨停板评估/、report/股票每日复盘/）；一次只分析一个板块的 skill 在日期后加板块名区分，如 leader-find 写 report/龙头扫描/YYYY-MM-DD-<板块名>.md（同一天多个板块各写一份）；中间产物不留残留，例如 limit-judge 的竞价清单（YYYY-MM-DD-竞价清单.txt）运行结束必须清理，其数据全部并进当日报告。
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
- 所有文件 UTF-8；脚本把 stdout 与 stderr 都重新配置为 UTF-8，兼容非中文终端。
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

提交信息用简短中文并点名改动的 skill（如 `limit-find: 调整晋级率口径`），也可用 conventional commits（feat:/fix:/docs:）。

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
