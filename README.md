# stock-skills — A股交易 Codex Skills 集合

中文 A 股实盘交易辅助的 Codex skills 集合：核心闭环覆盖「个股分析 → 交易计划 → 建仓/持仓 → 清仓复盘 → 统计归档」，涨停板查找（limit-find）、题材生命周期（limit-lifecycle）、打板竞价评估（limit-judge）、蓄力票发现（simmer-find）是四个可选查找与评估入口。每个 skill 独立自包含（SKILL.md + references + scripts），真实数据统一由 market-data 拉取（腾讯行情 + 东方财富行情/板块/财报/新闻/资金流公开接口）并输出数据报告，无需密钥。

当前版本：7.2.1 · [查看发布记录](https://github.com/ddd-online/stock-skills/releases)

## Skills 一览

| Skill | 定位 | 作用 |
|---|---|---|
| [market-data](market-data/) | 数据层 | 统一拉取 A 股真实行情、财报、新闻公告、资金流向、强势股榜单、板块行情榜/成分股榜/板块财务排名、涨停板数据并输出数据报告，供其他 skill 调用 |
| [stock-analysis](stock-analysis/) | 个股分析与持仓检查 | 两种模式：①分析模式（不落盘）——结合工作区账户/持仓/笔记，全面分析一只 A 股并输出建仓/加仓/减仓/空仓信号（观察为等待中间态）：证据先行、结论最后（基本面/技术面/支撑压力/事件与资金面/风险），检查近期新闻/公告（逻辑证伪）与资金流向；附支撑位/压力位、买点、止损、止盈锚点与盈亏比；建仓/加仓信号输出六格清单分析（不落盘，交接给 position-management 汇总进 STOCK-REVIEW.md 交易计划）。②持仓检查模式——对已买入的持仓做每日检查，按收盘复盘规范输出该股第 3–5 步（个股触发判断/量价四句/明日预案行），结果与明日预案追加 STOCK-REVIEW.md 并回写 POSITION.md 现价浮动盈亏，供 stock-report 收盘版汇总 |
| [limit-find](limit-find/) | 涨停数据查找 | 查找当日涨停/跌停/炸板家数与封板率、连板高度与最高板（一字核对）、昨日涨停今日晋级表现与炸板潮；把昨日涨停股按今日高开/平开/低开与尾盘涨停/上涨/平/下跌/跌停分类，按板块给出强弱与内部分化判定；把当日涨停股按板数（一板/二板/三板/四板及以上）分档，按板块统计晋级率与炸板率给出板块活跃度；再把当日主线板块与板块行情榜（板块行）合并，并在末步把当日与之前四次报告共五份汇总定出阵型四态（高度打开/轮动期/分歧期/崩塌·退潮期），阵型标签必须跟一行结构说明（崩在哪 + 抬在哪），并对上一份报告的阵型做次日确认（延续/切换/失效，判据跟着昨日标签走，只有高度打开与崩塌·退潮期记对错），写入 report/涨停板复盘/YYYY-MM-DD.md；只查找数据并出判定，不下单不预测 |
| [limit-lifecycle](limit-lifecycle/) | 题材生命周期 | 读 $limit-find 的当日报告（没有当日报告先执行 $limit-find），给今日主线板块（含上一份本技能报告里仍在跟踪的板块）标注题材生命周期四阶段——点火/扩散/加速/收缩（标签只有这四个），每条阶段判断都跟数字理由与本轮第几天；再认定板块里有没有龙头：按阶段看（点火档全是首板＝一般无龙头，只标「先动股」；扩散档出现 2–3 板晋级股＝龙头候选；加速档龙头领涨且板块跟涨＝龙头已确认；收缩档写龙头断板后的四种走法），龙头候选按板块内五字段纵向比较排序（首封时间 → 连板高度 → 换手与量能 → 资金 → 炸板后的回封速度），跟风板/尾盘偷袭板/高位高换手板/独涨板降级为伪龙头；再用主线健康度三检查点（龙头还在不在、涨停家数是增是减、资金是进还是退）判定这条线还活着、有收缩迹象还是已移出跟踪——每格按 正/弱/负/未知 记，正负都必须指向两个时点的可比数字，未知不计入正负（单日的资金只是状态，方向要今日 vs 基准日）；只有三格全正才算还活着，且推荐只限扩散阶段（点火只列观察、连续跟踪 3 天，加速与收缩不参与），两正一弱写「继续跟踪但不作为主线」；最后总结推荐的题材板块与板块内候选股票（角色/数字理由/观察条件，按 ACCOUNT.md 板块权限过滤无法买入的股票），写入 report/题材生命周期/YYYY-MM-DD.md；只做阶段判定、龙头认定与候选筛选，不给买点止损仓位、不下单不预测 |
| [limit-judge](limit-judge/) | 打板竞价评估 | 读 $limit-find 落盘的上一份涨停板复盘报告（涨停全名单/昨日最高板/晋级率与炸板率/主线板块），经 $market-data 批量取昨日涨停股今天的集合竞价：高开幅度、竞价成交额 ÷ 昨日全天成交额、集体分布，输出昨日涨停股集体竞价表与板块竞价表，写入 report/涨停板评估/YYYY-MM-DD.md（竞价清单为临时文件，运行结束即清理）；两条硬规则照写：竞价量占比一律用「竞价成交额 ÷ 昨日全天成交额」；出现「昨日最高板今天天地板或跌停」时当天不做任何打板动作，只观察 |
| [simmer-find](simmer-find/) | 蓄力票发现 | 先用 $market-data 的板块行情榜取强势板块定出板块池，再在板块内发现“1周到本月缓慢上涨”的蓄力票——A 型回踩蓄力（冲高后大跌转横盘）/ B 型缓涨蓄力（沿均线慢涨抗跌），按大盘环境适配、并按 ACCOUNT.md 板块权限排除无法买入的股票后写入 report/蓄力票扫描/YYYY-MM-DD.md；只做发现筛选，不输出买卖信号 |
| [stock-report](stock-report/) | 每日复盘 | 午间 11:45 精简版 / 收盘 15:15 完整版：收盘版按 大盘→板块→个股→量价→预案 五步做收盘复盘（大盘/板块由本 SKILL 分析，个股/量价/预案来自 $stock-analysis 持仓检查模式）+ 生成复盘报告写入 report/股票午间复盘/ 或 report/股票每日复盘/，配置邮箱时经 agently-mail 同步发送 |
| [position-management](position-management/) | 资金与持仓档案 | 每次动作前输出资金调度卡（现金储备≥实际可用资产30%、单笔预算≤实际可用资产2%降档1%；实际可用资产=本金+总盈亏−累计支取），处理建仓/加仓/减仓/空仓/清仓（建仓时创建 STOCK-REVIEW.md 写入交易计划、创建 TRADE-SUMMARY.md）、平仓复盘与总结并归档；清仓时计算胜率/平均盈亏/期望值/最大回撤四指标写入 TRADE-STATS.md |
| [setup-stock-workspace](setup-stock-workspace/) | 一次性初始化 | 创建工作区目录与种子文件，收集交易费用设置与板块权限（主板/创业板/科创板/北交所/ST，未开通板块不交易），并把目录/文件规则、SKILL 版本与升级约束、条件单规则与状态更新规则写入 AGENTS.md |

## 安装（Codex）

在 Codex 中粘贴下面的提示词，Codex 会用 $skill-installer 从本仓库下载并安装全部 skill（需网络，公开仓库默认直连下载）：

```
使用 $skill-installer 从 GitHub 仓库 ddd-online/stock-skills 安装以下 skills：market-data、stock-analysis、limit-find、limit-lifecycle、limit-judge、simmer-find、stock-report、position-management、setup-stock-workspace
```

安装位置：`$CODEX_HOME/skills/<skill-name>`（默认 `~/.codex/skills`）。安装后下一个会话即可用 `$skill-name` 调用：

```
使用 $limit-find 查找今日涨停板数据：涨停跌停家数、最高几板、晋级率与炸板潮、当日主线板块
使用 $limit-lifecycle 看今日主线板块处在题材生命周期哪一阶段、还活着吗、推荐哪个题材板块与板块内哪些股票
使用 $limit-judge 做今日竞价评估：昨天涨停的票今天怎么开（集体竞价表、板块竞价表）
使用 $simmer-find 用今日板块行情榜定强势板块，再在板块里找蓄力票
使用 $stock-analysis 分析 sh600410 该建仓还是空仓
使用 $stock-analysis 检查我的持仓，该不该卖
使用 $stock-report 做今天的收盘复盘
```

也可以直接 clone 本仓库，把需要的 skill 文件夹复制到 `~/.codex/skills/`。

## 依赖

- Python 3（纯标准库，无第三方依赖）
- 网络连接（数据接口：腾讯行情 `qt.gtimg.cn` / `web.ifzq.gtimg.cn`；东方财富行情/板块/资金流 `push2.eastmoney.com` / `push2delay.eastmoney.com`、财报 `datacenter-web.eastmoney.com`、新闻/公告 `search-api-web.eastmoney.com` / `np-anotice-stock.eastmoney.com`）
- 数据接口免费、无需密钥；接口不可用时 skill 明确报错，不编造数据

## 交易流程

交易线含义：setup-stock-workspace 只执行一次；之后每个交易日从“入口”进入分析线——入口有三个：用户直接要求分析个股、$limit-find 涨停板数据查找、$simmer-find 蓄力票发现；stock-analysis 的分析模式只分析并输出报告（不落盘、不维护观察池），“买入结论”经 position-management 落到股票持仓；已持仓由 stock-analysis 的持仓检查模式每日检查，stock-report 把检查结果汇总为复盘报告与明日预案，形成“当日复盘 → 次日 9:25 执行”的循环。

stock-analysis 在输出「建仓/加仓」信号时完成六格清单分析（选什么/何时买/买多少/错了怎么办/对了怎么办/交易后，不落盘），交接给 position-management；STOCK-REVIEW.md「交易计划」是该股唯一落盘的规则来源（六格要素 + 资金调度结果：金额/手数/费用/最大亏损/盈亏比），持仓期间遵守、不临时修改。position-management 做资金调度确认并执行建仓/加仓——建仓执行时创建 STOCK-REVIEW.md（写入交易计划）与 TRADE-SUMMARY.md（追加买入记录）；「减仓/空仓」信号直接由 position-management 做资金调度（减仓/清仓）。持仓期间的每日检查由 stock-analysis 的持仓检查模式负责（只向既有 STOCK-REVIEW.md 追加每日检查行，并回写 POSITION.md 现价与浮动盈亏），清仓后的平仓复盘与总结（只写 TRADE-SUMMARY.md——四层复盘总结——随后归档）由 position-management 负责。

limit-find 是可选的“涨停板数据查找”入口（不属于每日闭环）：用涨停/跌停/炸板家数、连板高度、晋级率与炸板率描述当日情绪与主线，并在最后一步把当日加之前四次报告共五份汇总出阵型四态、对上一份报告的阵型做次日确认（四张检验卡跟着昨日标签走，结论为延续/切换/失效；只有高度打开与崩塌·退潮期记对错、统计强标签延续率）；报告写入 report/涨停板复盘/YYYY-MM-DD.md，只做数据查找与判定，买卖判断仍走 stock-analysis → position-management。

limit-lifecycle 是可选的“题材生命周期”入口（不属于每日闭环）：先拿到 limit-find 的当日报告（没有当日报告就先执行 limit-find），把「今天钱在哪」升级成「这条线现在第几天、有没有龙头」——给今日主线板块与上一份报告里仍在跟踪的板块标注点火/扩散/加速/收缩阶段与数字依据（含本轮第几天），按阶段认定龙头（点火＝无龙头、扩散＝龙头候选、加速＝龙头已确认、收缩＝断板后四走法），用五字段做板块内纵向排序并把四种伪龙头降级，再跑主线健康度三检查点（龙头、涨停家数、资金），最后给出推荐的题材板块与板块内候选股票（角色、数字理由、观察条件）；报告写入 report/题材生命周期/YYYY-MM-DD.md，只做阶段判定、龙头认定与候选筛选，买卖判断仍走 stock-analysis → position-management。

limit-judge 是可选的“打板竞价评估”入口（不属于每日闭环）：9:25–9:30 读 $limit-find 的昨日涨停板复盘报告，输出昨日涨停股集体竞价表与板块竞价表（阵型沿用报告里的判定，本入口不重复判定），并按两条硬规则给结论——竞价量占比按「竞价成交额 ÷ 昨日全天成交额」计算；最高板今天天地板或跌停则当天只观察。没有昨日报告先跑 $limit-find，本入口只出观察结论，买卖仍走 stock-analysis → position-management。

simmer-find 是可选的“蓄力票发现”入口（不属于每日闭环）：必须先用 $market-data 的板块行情榜（fetch_sector_boards）取强势板块、定出板块池（口径：当日与近 5 日涨幅为正、上涨家数≥下跌家数、主力净流入不明显流出，用户说明优先），再在板块内筛 A/B 型蓄力票并写 report/蓄力票扫描/YYYY-MM-DD.md；没有板块满足口径就写明「今日无强势板块，蓄力票扫描不成立」并结束；发现结果只作候选，是否值得买仍走 stock-analysis → position-management。

每笔清仓后 position-management 把交易记录写入根目录 TRADE-STATS.md，每 5-10 笔结算胜率、平均盈亏、期望值、最大回撤，用统计判断系统是否有效、下一步该改哪一端（入场端/出场端），一次只改一条规则。

空仓期/等待期：stock-analysis 的「观察」只是报告里的等待中间态（触发条件与预案写在报告里、由用户自行盯，不落盘、不维护观察池）；没有触发条件不建仓。空仓期间 $stock-report 收盘复盘照常执行（只做大盘/板块），不产生个股预案。

调用约束：
- 前置：limit-find、limit-judge 为纯数据技能，不读取工作区文件、可在任意目录运行（limit-judge 读取 report/涨停板复盘/ 下 $limit-find 的上一份报告作为样本来源，没有报告就说明原因结束）；limit-lifecycle 读取 report/涨停板复盘/ 下 $limit-find 的当日报告（没有当日报告先执行 $limit-find），并仅读取 ACCOUNT.md 的「板块权限」用于排除无法买入的股票；simmer-find 先用 $market-data 板块行情榜取强势板块，仅读取 ACCOUNT.md 的「板块权限」用于排除无法买入的股票；其余 SKILL 依赖工作区文件（ACCOUNT.md / NOTES.md / POSITION.md / MUST.md / stocks/），未初始化先运行 $setup-stock-workspace
- limit-find、limit-judge 不读取 MUST.md；limit-lifecycle 与 simmer-find 仅按 ACCOUNT.md 板块权限过滤、不读取 MUST.md；其余 SKILL 必须遵守工作区 MUST.md 中的个人交易风格与规则（默认只有一个标题，由用户编辑）
- limit-judge 的硬规则不可绕过：竞价量占比一律按「竞价成交额 ÷ 昨日全天成交额」，出现「昨日最高板今天天地板或跌停」时当天只观察、不做任何打板动作；9:30 后运行必须标注“非竞价口径”，不得用全天成交额冒充竞价成交额
- stock-analysis 输出建仓/加仓信号（含六格清单分析）后，才调用 position-management；减仓/空仓信号直接调用 position-management；用户直接请求建仓而 position-management 未收到 stock-analysis 的支撑位/压力位（买点/止损/止盈）分析时，先调用 stock-analysis 获取后再做资金调度
- 资金调度（现金储备、单笔预算、批次、手数）全部由 position-management 确认；stock-analysis 只输出信号、锚点与建议
- STOCK-REVIEW.md 与其交易计划由 position-management 建仓时创建/写入（涉及资金调度）；stock-analysis 的持仓检查模式只追加每日检查行，并回写 POSITION.md 现价与浮动盈亏
- stock-analysis 的持仓检查模式只检查 POSITION.md 中的持仓，且只在该模式下落盘（且只追加，不建档）；触发止损/止盈/时间止损时只给出平仓结论，不强制下单（可能不在交易时段）
- stock-report 每日复盘汇总一条检查线：收盘版按 大盘→板块→个股→量价→预案 组装 $stock-analysis 持仓检查模式（已持仓检查）的输出；复盘报告先写入 report/ 对应子目录，有邮箱时经 $agently-mail 同步发送
- 用户卖出后调用 position-management 告知卖出价，由它按实际成交价结算并完成平仓总结与归档
- stock-analysis 的加仓六格清单分析必须有「加仓」信号、POSITION.md 持仓与既有交易计划（STOCK-REVIEW.md / history 归档），缺一不输出
- 工作区没有 TRADE-RULES.md：六格清单分析由 stock-analysis 输出（不落盘）；交易计划写在 STOCK-REVIEW.md（建仓时），平仓复盘只写 TRADE-SUMMARY.md（均由 position-management 维护）

工作区归档规则由 setup-stock-workspace 写入 AGENTS.md，首次交易前先运行它初始化。

## 项目结构

```
stock-skills/
├── <skill-name>/           # 每个 skill 一个文件夹
│   ├── SKILL.md            # 触发说明与工作流（必读）
│   ├── agents/openai.yaml  # 界面元数据
│   ├── references/         # 中文参考文档（按需加载）
│   └── scripts/            # 各 skill 专属脚本；真实数据脚本集中在 market-data/scripts/（fetch_quote / fetch_fundamentals / fetch_news / fetch_capital_flow / fetch_strong_stocks / fetch_sector_boards / fetch_sector_leaders / fetch_sector_fundamentals / fetch_limit_up）
└── README.md
```

## 免责声明

所有 skill 输出不构成投资建议。股市有风险，投资需谨慎。
