# stock-skills — A股交易 Codex Skills 集合

中文 A 股实盘交易辅助的 Codex skills 集合，覆盖「分析 → 计划 → 建仓 → 持仓 → 清仓 → 复盘」完整交易生命周期。每个 skill 独立自包含（SKILL.md + references + scripts），基于真实行情与财报数据（腾讯行情接口、东方财富财报接口），无需密钥。

当前版本：1.1.0 · [查看发布记录](https://github.com/ddd-online/stock-skills/releases)

## Skills 一览

| Skill | 作用 |
|---|---|
| [stock-analysis](stock-analysis/) | 结合工作区账户/持仓/笔记，全面分析一只 A 股/ETF 是否值得买（已持仓时判断能否加仓）：证据先行、结论最后（基本面/技术面/支撑压力/风险），并生成支撑位/压力位、买点、止损、止盈锚点与盈亏比；仓位由 position-management 确认 |
| [watchlist-review](watchlist-review/) | 审视观察池：逐只调用 stock-analysis 分析池中标的，按结论更新状态（信号触发/等待/移除）并回写 WATCHLIST.md |
| [stock-review](stock-review/) | 持仓每日 5 分钟检查（价格位置/量能/新信息/买入理由/心态），结果写入 STOCK-REVIEW.md |
| [trade-rules-generate](trade-rules-generate/) | stock-analysis 判定值得买/值得加仓后自动调用，生成六格交易规则（选什么/何时买/买多少/错了怎么办/对了怎么办/交易后），持仓期间严格遵守；加仓时追加新规则，历史保留、以最新为准 |
| [position-management](position-management/) | 持仓生命周期管理与全部仓位处理：分批建仓/止盈、加仓数量确认、清仓执行、平仓复盘与总结（生成 TRADE-SUMMARY.md 并归档；清仓时计算胜率/平均盈亏/期望值/最大回撤四指标写入 TRADE-STATS.md） |
| [setup-stock-workspace](setup-stock-workspace/) | 一次性初始化股票交易工作区：创建目录与种子文件，收集交易费用设置，并把归档规则写入 AGENTS.md |

## 安装（Codex）

每个 skill 是一个独立文件夹，用 Codex 的 skill-installer 从本仓库安装（需网络，公开仓库默认直连下载）：

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo ddd-online/stock-skills \
  --path stock-analysis watchlist-review stock-review trade-rules-generate \
         position-management setup-stock-workspace
```

逐个安装示例：

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo ddd-online/stock-skills --path stock-analysis
```

安装位置：`$CODEX_HOME/skills/<skill-name>`（默认 `~/.codex/skills`）。安装后下一个会话即可用 `$skill-name` 调用（如 `使用 $stock-analysis 分析 510300 是否值得买`）。

也可以直接 clone 本仓库，把需要的 skill 文件夹复制到 `~/.codex/skills/`。

## 依赖

- Python 3（纯标准库，无第三方依赖）
- 网络连接（数据接口：腾讯行情 `qt.gtimg.cn` / `web.ifzq.gtimg.cn`，东方财富财报 `datacenter-web.eastmoney.com`）
- 数据接口免费、无需密钥；接口不可用时 skill 明确报错，不编造数据

## 交易流程

```
输入股票名称 → stock-analysis 分析（含支撑压力/买点/止损/止盈）→ 值得买/值得加仓？
  ├─ 否 → 终止流程
  └─ 是 → trade-rules-generate 生成/追加六格交易规则（持仓期间严格遵守）
          → position-management 确认仓位并建仓/加仓
          → stock-review 每日检查（更新 STOCK-REVIEW.md）
          → stock-review 触发平仓条件时给出平仓结论（不强制下单）
          → 用户清仓后告知 position-management 卖出价 → 平仓复盘与总结（TRADE-SUMMARY → TRADE-STATS 四指标 → history 归档）
```

trade-rules-generate 在 stock-analysis 判定「值得买/值得加仓」后自动调用，生成该股专属的六格交易规则；加仓时在文件末尾追加新规则，历史规则保留、以最新为准。持仓期间严格遵守，不临时修改。生成规则后由 position-management 确认仓位并执行建仓/加仓；持仓期间的每日检查由 stock-review 负责，清仓后的平仓复盘与总结（生成 TRADE-SUMMARY.md 并归档）由 position-management 负责。

每笔清仓后 position-management 把交易记录写入根目录 TRADE-STATS.md，每 5-10 笔结算胜率、平均盈亏、期望值、最大回撤，用统计判断系统是否有效、下一步该改哪一端（入场端/出场端），一次只改一条规则。

空仓期/等待期：$watchlist-review 审视观察池——逐只调用 $stock-analysis，按结论更新 WATCHLIST.md 状态；没有触发条件不买。

调用约束：
- 前置：所有 SKILL 依赖工作区文件（ACCOUNT.md / NOTES.md / POSITION.md / MUST.md / stocks/），未初始化先运行 $setup-stock-workspace
- 所有 SKILL 必须遵守工作区 MUST.md 中的个人交易风格与规则（默认只有一个标题，由用户编辑）
- stock-analysis 结论为值得买/值得加仓后，才依次调用 trade-rules-generate → position-management
- 仓位处理（批次、手数、单笔亏损预算）全部由 position-management 确认；stock-analysis 只输出结论、锚点与加仓建议
- watchlist-review 审视观察池时逐个自动调用 stock-analysis；观察池进出由 stock-analysis 结论决定（观察→进池等待、不买→移除）
- stock-review 只检查 POSITION.md 中的持仓；触发止损/止盈/时间止损时只给出平仓结论，不强制下单（可能不在交易时段）
- 用户卖出后调用 position-management 告知卖出价，由它按实际成交价结算并完成平仓总结与归档
- trade-rules-generate 加仓追加必须有「值得加仓」结论、POSITION.md 持仓与已有 TRADE-RULES.md，缺一不追加

工作区归档规则由 setup-stock-workspace 写入 AGENTS.md，首次交易前先运行它初始化。

## 项目结构

```
stock-skills/
├── <skill-name>/           # 每个 skill 一个文件夹
│   ├── SKILL.md            # 触发说明与工作流（必读）
│   ├── agents/openai.yaml  # 界面元数据
│   ├── references/         # 中文参考文档（按需加载）
│   └── scripts/            # 真实数据脚本（fetch_quote.py / fetch_fundamentals.py）
└── README.md
```

## 免责声明

所有 skill 输出不构成投资建议。股市有风险，投资需谨慎。
