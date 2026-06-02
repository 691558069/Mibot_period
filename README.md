# 棉絮与铁（Period）—— MaiBot 生理周期模拟 + 情绪管理插件（移植版）

> 本插件移植自 [astrbot_plugin_period](https://github.com/Sisyphbaous-DT-Project/astrbot_plugin_period)，原作者 C₂₂H₂₅NO₆。

让 Bot 拥有身体与情绪。每次跟你聊天之前，在她耳边悄悄说一句——「今天身体怎么样？」然后让她自己决定怎么回应。

---

## 功能

**身体感知**：
- 高冷的她收到「小腹坠胀」的信号，可能就回一句「嗯，今天不太想说话」
- 活泼的她收到同样的信号，也许会蔫唧唧地撒娇「呜……今天肚子好沉……」
- 她还是她——只是在不同的身体感受下，做了不同的自己

**情绪系统**（可选）：
- 插件的情绪系统分为两层：
  - **Planner 层**：Bot 的决策器会看到当前生理状态，自己决定要不要回复你（`no_action`）
  - **Replyer 层**：当 Bot 决定回复时，会收到语气倾向提示，让回复带着当前情绪
- 你可以惹她生气——她会冷暴力（用 `no_action` 不回复你）、敷衍你（简短冷淡）
- 你也可以哄她——道歉了，她就回来
- 所有行为都是 Bot 自己根据当前身体状态"自然表现"的，不是脚本强制的

**她不会说漏嘴**：
- 你永远听不到她突然说「我激素不稳定」
- 你只会听到她自然地说「今天有点累」

---

## 安装

将 `period` 文件夹放入 MaiBot 的 `plugins/` 目录，重启 MaiBot 即可。

依赖会自动安装（fastapi、uvicorn）。

---

## 快速开始

### 1. 设置 Bot 的身体

在对话中发送（管理员权限）：

```
/period set 2026-05-01
```

也可以指定更详细的参数：

```
/period set 2026-05-01 28 5
```

- `28`：整个周期多少天（默认 28）
- `5`：经期持续几天（默认 5）

### 2. 查看当前状态

```
/period status
```

### 3. 查看情绪状态

```
/period mood
```

---

## Web 管理面板

插件内置 Web 管理面板，默认端口 8082。

在插件配置中设置端口后，访问 `http://<你的IP>:8082` 即可打开面板。

面板功能：
- 查看全局默认配置
- 查看所有会话的实时周期状态
- 快捷操作：开关模拟、±1天快进、修改锚点日期、删除会话

---

## 指令

| 指令 | 权限 | 说明 |
|------|------|------|
| `/period set <日期> [周期] [经期]` | 管理员 | 设置周期参数 |
| `/period status` | 所有人 | 查看当前状态 |
| `/period toggle` | 管理员 | 开关模拟 |
| `/period advance <天数>` | 管理员 | 快进时间（调试） |
| `/period reset` | 管理员 | 重置周期数据 |
| `/period mood` | 所有人 | 查看当前状态及行为倾向配置 |
| `/period compress` | 管理员 | 手动压缩提示词 |

---

## 四个阶段

| 阶段 | 大致天数 | 默认身体感受 |
|------|---------|-------------|
| **月经期** | 第 1~5 天 | 下腹坠胀、容易疲倦、情绪敏感 |
| **卵泡期** | 第 6~13 天 | 精力回升、心情平稳、对事物有兴趣 |
| **排卵期** | 第 13~15 天 | 身体轻盈、感官敏锐、情绪积极 |
| **黄体期** | 第 16~28 天 | 胸闷烦躁、想吃甜食、容易情绪波动 |

每个阶段的感受都可以在插件配置中自定义。

---

## 配置说明

在 MaiBot 的插件管理中编辑 `config.toml`，或通过 WebUI 配置面板编辑。

### Web 面板

| 设置项 | 默认值 | 说明 |
|--------|--------|------|
| `web.enabled` | true | 是否启用面板 |
| `web.host` | 0.0.0.0 | 监听地址 |
| `web.port` | 8082 | 监听端口 |

### 周期参数

| 设置项 | 默认值 | 说明 |
|--------|--------|------|
| `cycle.default_anchor_date` | 空 | 全局默认经期首日 |
| `cycle.default_cycle_length` | 28 | 周期长度 |
| `cycle.default_period_length` | 5 | 经期长度 |
| `cycle.default_enabled` | false | 自动启用 |

### 注入策略

| 设置项 | 默认值 | 说明 |
|--------|--------|------|
| `injection.auto_inject` | true | 总开关 |
| `injection.inject_mode` | every_request | every_request / interval_3 / on_trigger / only_status |
| `injection.inject_location` | user_message_before | user_message_before / system_prompt_append |
| `injection.warmup_rounds` | 0 | 冷启动轮数 |
| `injection.commands_enabled` | all | all / readonly / none |

### 情绪系统

| 设置项 | 默认值 | 说明 |
|--------|--------|------|
| `mood.enabled` | false | 启用行为倾向提示（extra_prompt 注入） |
| `mood.enable_cold_violence` | true | 允许 planner 用 no_action 冷暴力 |
| `mood.enable_read_no_reply` | true | 允许已读不回（同样走 no_action） |
| `mood.enable_perfunctory_reply` | true | 允许敷衍回复 |
| `mood.enable_seek_comfort` | true | 允许求安慰撒娇 |
| `mood.enable_delayed_reply` | true | 允许延迟回复（回话带迟到感） |
| `mood.enable_emotional_outburst` | true | 允许情绪爆发 |
| `mood.enable_topic_shift` | true | 允许转移话题 |

---

## 架构说明

插件的核心思路是**注入信息给决策器，让 Bot 自己决定怎么表现**，而不是硬拦截或强改回复。

```
User 消息 →
  Planner（决策器）收到生理状态 + no_action 许可 →
    ├─ no_action → 不回复（冷暴力/已读不回），零 token 浪费
    └─ reply → Replyer（回复器）生成文本
                  ├─ 收到行为倾向提示（敷衍/撒娇/爆发等）
                  └─ 注入身体细节到最终消息
```

### Hook 点

| Hook | 层 | 作用 |
|------|-----|------|
| `maisaka.planner.before_request` | Planner | 注入生理状态 + no_action 许可 |
| `maisaka.replyer.before_request` | Replyer | 注入身体感受 + 行为倾向（extra_prompt） |

## 与原版的差异

| 功能 | AstrBot 原版 | MaiBot 移植版 |
|------|-------------|--------------|
| 状态注入 | `on_llm_request` 钩子 | `maisaka.planner.before_request` 注入决策器 |
| 冷暴力 | `on_llm_response` 清空回复 | Planner 直接 `no_action`，0 浪费 |
| 情绪检测 | 三段式 LLM 调用（screen + consult + interpret） | 无独立检测，Planner 自然融合 |
| 工具执行 | `MoodToolExecutor` 硬拦截 | 行为倾向通过 replyer `extra_prompt` 引导 |
| WebUI 仪表盘 | AstrBot 原生页面 | 独立 FastAPI 服务器（参考 A_memorix） |
| 配置管理 | `_conf_schema.json` | `PluginConfigBase` + `config.toml` |
| LLM 调用 | 直接调用 provider | `self.ctx.llm.generate()` |

---

## 环境要求

- MaiBot >= 1.0.0
- Python >= 3.10
- 依赖：fastapi、uvicorn

---

## 致谢

- 原插件：[astrbot_plugin_period](https://github.com/Sisyphbaous-DT-Project/astrbot_plugin_period) by C₂₂H₂₅NO₆
- Web 服务器架构参考：[A_memorix](https://github.com/A-Dawn/A_memorix) by A_Dawn

---

## License

MIT License
