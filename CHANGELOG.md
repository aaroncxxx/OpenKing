# CHANGELOG

## v2.9.6 (Open-Meteo 毫米级降雨量)

### 新增

- **Open-Meteo API 接入**: 免费、无需 API Key，逐小时降水量（mm）
- **广东省 21 地级市精确坐标**: 覆盖全省所有地级市，自动识别广东任务
- **`fetch_guangdong_precipitation()`**: 过去 24h + 未来 6h 逐小时降雨量，按累计量排序
- **`fetch_city_precipitation(city)`**: 单城市精确降雨数据，含温度/湿度/风速
- **丞相智能路由**: 识别广东相关关键词，自动调用精确数据接口（降水量、广东、粤、阳江等）

### 优化

- `core/weather.py` v2.9.6: 从 wttr.in 升级到 Open-Meteo API
- `chancellor.py`: 天气任务分支，广东专项 vs 通用天气
- 兼容旧 `fetch_all_weather()` 接口，全国城市坐标保留

### 数据源

- Open-Meteo API: `api.open-meteo.com/v1/forecast`
- 逐小时: precipitation(mm), precipitation_probability, temperature_2m, humidity, wind_speed

## v2.9.5 (天气数据修复版)

### 修复

- **天气任务数据链断裂**: 接入 wttr.in 免费天气 API，实时注入全国 34 城天气数据
- **Agent 标签粒度不足**: 11 个执行类 Agent 标签从 `['执行']` 细化为具体子标签（检索/爬取/数据/接口/编码等）
- **关键词筛选误选**: 天气/预报/降雨/气温专属标签映射，避免驿传接口被误选为数据抓取节点
- **知识库污染**: 天气任务自动注入实时数据，不再依赖量子内容兜底

### 实战验证

- **任务三（大后天天气预报）**: 修复前 ❌ 数据链断裂 → 修复后 ✅ 206s 完成，实时数据注入
- **天气数据覆盖**: 北京/上海/广州/深圳/成都/重庆/武汉/杭州/西安/南京等 34 城

### 技术细节

- 新增 `core/weather.py` — wttr.in 天气数据工具
- `chancellor.py` — 天气任务自动识别 + 实时数据注入
- `config.json` — 11 个 Agent 标签细化

## v2.9.2 (ClawScan 修复版)

### 修复

- **模型路由器**: 统一 small 模型为 `mimo-v2.5-pro`，修复执行类 Agent 因 `mimo-v2.5-flash` 不可用导致的 400 错误
- **ClawScan 误判**: 消除 `community.py` 和 `mount.py` 中 hardcoded secret 模式，扫描标记从 suspicious → clean

### 实战验证

- **案例一（降雨分析）**: 3 节点调度，92.1s 完成，10,064 token
- **案例二（全国天气预报）**: 7 节点调度，246.6s 完成，35,021 token
- 两次任务锦衣卫审计均通过

## v2.9 (全面增强版)

### 核心优化

- **Agent 标签系统**: 每个 Agent 带标签（参谋/执行/安全/地方等），丞相规划时按标签筛选相关节点，减少 prompt 长度 60%+
- **模型路由器**: 按角色和任务复杂度自动选择大小模型。丞相/参谋用 pro，执行/监察用 flash，节省 token 成本
- **Agent 记忆系统**: 短期记忆（滑动窗口 20 条）+ 长期记忆（持久化 JSON），高重要性自动存入长期。记忆注入 prompt，Agent 越用越聪明
- **对话历史**: 每个 Agent 保留最近 10 轮对话，LLM 调用时自动注入上下文
- **性能评分**: 追踪每个 Agent 的平均响应时间、失败率、任务完成数

### 速度优化

- **任务队列**: 优先级队列 + 最大并发控制（16）+ 超时（90s）+ 自动重试（2次）+ 指数退避
- **熔断器**: 连续 5 次失败自动熔断，300s 后半开重试，防止单节点拖垮全局
- **SQLite WAL**: 写入不再阻塞读取，并发性能提升
- **Token 追踪线程安全**: threading.Lock 保护，256 节点并发写入不冲突

### 知识层优化

- **中文分词**: 纯 Python 实现正向最大匹配 + 量子/技术术语词典，替代粗暴 bigram，检索精度提升
- **LRU 缓存**: 查询结果 5 分钟 TTL 缓存，命中率追踪，相同查询直接返回
- **增量索引**: 支持单文档添加，无需全量重建

### 架构优化

- **消息总线增强**: deque(maxlen=2000) 防 OOM，Agent 间直接通信（send_direct），消息统计
- **事前安全检查**: 检测敏感操作关键词（网络请求/删除/密钥等），任务执行前预警
- **配置热加载**: 检测 config.json mtime 变更，自动重载，无需重启
- **结构化日志**: RotatingFileHandler，10MB 轮转，按模块分文件，存储在 data/logs/

### CLI 新增命令

- `queue` — 查看任务队列状态
- `bus` — 查看消息总线统计
- `memory <agent_id>` — 查看指定 Agent 记忆
- `--queue`, `--bus`, `--memory` 启动参数

### 概念映射

| 量子概念 | 帝国架构对应 |
|---------|-------------|
| 叠加态 | Agent 同时持有多个观点 |
| 纠缠 | Agent 间深度协作关联 |
| 测量坍缩 | 确定立场/选择方案 |
| 时空复用 | 同一 Agent 多角色轮转 |
| 量子行走 | 决策空间多路径探索 |
| Bell 不等式 | 协作有效性验证 |

### 灵感来源

- 九章四号光量子计算原型机
- 帝国架构三公九卿制

---

## v2.1.2 优化

- **QComm 二进制协议**: 替代 JSON，32 字节/态 vs 73-121 字节，2-4x 压缩
- **GHZ 态制备**: 3/4-qubit GHZ 态，完整状态向量模拟
- **W 态制备**: 3-qubit W 态
- **多比特纠缠对比**: GHZ vs W 特性对比

## v2.1.1 优化

- **拉丁超立方抽样 (LHS)**: 替代蒙特卡罗，收敛速度 O(1/n) vs O(1/√n)
- **响应式 UI**: 根据终端宽度自适应布局
- **WebGL 可视化**: 生成 HTML+WebGL 3D 概率幅图

## v2.1.0 (量子版)

- **量子计算思维模拟器**: qubit, gates, entanglement, timeslice, quantum_agent, quantum_cli

## v2.0.1 (优化版)

- JSON 解析器重写、知识层集成、Token 计数修复、智能 fallback

## v2.0.0 (归一版)

- 版本号收敛、文件结构重组、SKILL.md 重写

---

历史变更记录见 `docs/CHANGELOG-legacy.md`
