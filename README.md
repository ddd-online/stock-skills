# stock-skills — A股交易 Codex Skills 集合

中文 A 股交易教学与实战的 Codex skills 集合，覆盖「分析 → 计划 → 建仓 → 持仓 → 清仓 → 复盘」完整交易生命周期。每个 skill 独立自包含（SKILL.md + references + scripts），基于真实行情与财报数据（腾讯行情接口、东方财富财报接口），无需密钥。

## Skills 一览

| Skill | 作用 |
|---|---|
| [stock-analysis](stock-analysis/) | 全面分析一只 A 股/ETF 是否值得买：证据先行、结论最后（基本面/技术面/支撑压力/风险/仓位匹配） |
| [stock-support-resistance-analysis](stock-support-resistance-analysis/) | 生成近期支撑位/压力位，给出买点、止损、止盈锚点与盈亏比参考 |
| [stock-review](stock-review/) | 持仓每日 5 分钟检查与平仓复盘（盈亏计算 + 复盘三问） |
| [trade-rules-generate](trade-rules-generate/) | 生成六格个人交易规则清单（选什么/何时买/买多少/错了怎么办/对了怎么办/交易后） |
| [position-management](position-management/) | 持仓生命周期管理：建仓执行、加仓决策、清仓执行、平仓总结 |
| [setup-stock-workspace](setup-stock-workspace/) | 一次性初始化股票交易工作区：创建目录与种子文件，并把归档规则写入 AGENTS.md |

## 安装（Codex）

每个 skill 是一个独立文件夹，用 Codex 的 skill-installer 从本仓库安装（需网络，公开仓库默认直连下载）：

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo ddd-online/stock-skills \
  --path stock-analysis stock-review stock-support-resistance-analysis \
         trade-rules-generate position-management setup-stock-workspace
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
输入股票名称 → stock-analysis 分析 → 是否值得买？
  ├─ 否 → 终止流程
  └─ 是 → stock-support-resistance-analysis 确认买点/止损/止盈
          → position-management 建仓
          → stock-review 每日复盘
          → 清仓 → 平仓总结（TRADE-SUMMARY → history 归档）
```

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

所有 skill 输出均为教学演示，不构成投资建议。股市有风险，投资需谨慎。
