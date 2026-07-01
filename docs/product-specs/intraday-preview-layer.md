# 盘中预览层

## 背景

QuantA 当前的产品定位是“盘后研究驱动盘中监控”。

盘后 `READY snapshot` 不是终点，而是盘中监控的计划来源：它提供观察名单、策略、买点、止盈位、风控线、止损位和解释。盘中预览层负责消费这些计划，并用当天行情判断是否触发。

1. 前端默认只读最新 `READY snapshot`。
2. `READY snapshot` 只承载“可复现、可回测、可发布”的盘后结果。
3. 盘中未收盘的数据，不应直接混入 `daily_sync -> daily_screener -> daily_backtest` 的正式发布链，但应该用于监控已发布计划的执行状态。

因此，在交易日白天，正式研究口径仍来自最近一个已完成盘后发布的 `biz_date`；盘中状态则来自独立预览行情，并且必须明确标记为 `预览 / 非 READY / 不用于回测`。

## 需求

需要维护一层独立于 `READY snapshot` 的“盘中监控/预览层”，满足以下目标：

1. 用户可以在交易日白天看到“昨天盘后计划在今天是否触发”。
2. 盘中预览不得污染盘后 canonical 数据、研究结果和回测语义。
3. UI 必须明确标注这是 `预览 / 非 READY / 不用于回测` 的数据视图，不能伪装成正式发布快照。
4. 当盘中源不可用、延迟或降级时，系统要明确展示“数据暂不可用”或“延迟预览”，而不是静默回退成昨天快照冒充今天。

## 非目标

当前文档只定义方向，不在本阶段实现以下内容：

1. 把分钟级或实时数据纳入正式 `READY snapshot` 发布链。
2. 用盘中预览结果反向驱动正式 screener、backtest 或盘后研究结论。
3. 定义最终商业实时行情供应商的采购与授权流程。
4. 扩展到 Level-2、逐笔成交或高频研究场景。

## 方案概述

### 1. 分层原则

盘中预览层必须与正式发布层完全分开：

1. `READY snapshot` 继续作为盘后系统事实来源。
2. 盘中预览走单独的 read path、缓存和 API，不写入 `artifact_publish(status=READY)`。
3. 盘中预览只服务监控、触发提醒和辅助判断，不参与回测复现。

### 2. 数据源原则

盘中预览层优先使用“有明确授权和 SLA 的未来实时层”，而不是直接改写现有 canonical source 定义。

推荐口径：

1. `future licensed realtime source` 作为正式目标源。
2. 在正式实时源未落地前，如果需要试验，可允许接入单独的 preview adapter，但必须标记为 `experimental/degraded`。
3. 试验性 preview adapter 的失败，不应阻断盘后 `daily_sync`、`history_backfill` 或 `READY snapshot` 发布。

### 3. 读写与存储原则

盘中预览层建议采用轻量缓存，而不是直接复用盘后发布表。

建议的最小结构：

1. `preview_quote` 或等价缓存：个股最新价、涨跌幅、成交额、更新时间。
2. `preview_index_quote` 或等价缓存：上证/深证/创业板等指数快照。
3. `preview_source_status`：记录 provider、freshness、延迟、降级原因和最后成功刷新时间。

这些数据可以落本地缓存，但不应被解释为正式 snapshot 历史事实。

### 4. API 与前端原则

盘中预览应走单独 API 和显式 UI 标识。

建议的最小能力：

1. 单独 API，例如 `/api/v1/preview/market`、`/api/v1/preview/stocks/{symbol}`。
2. 页面顶部显式显示：
   `盘中预览`
   `非 READY`
   `不用于回测`
   `最后更新时间`
3. 当预览源不可用时，显示空态与原因，不自动把昨天的 `READY snapshot` 伪装成今天盘中视图。

### 5. 与现有 workbench 的关系

盘中预览层是现有 workbench 的执行层：盘后 `READY snapshot` 产出计划，盘中预览负责盯计划是否触发。

推荐交互：

1. 默认突出监控队列和盘中触发状态，同时保留盘后 `READY snapshot` 作为解释来源。
2. 增加一个显式切换入口，例如“监控执行 / 盘后研究依据”。
3. 两个视图共享部分 UI 组件，但数据标签和语义必须严格区分。

## 第一版实现建议

如果后续开始实现，建议按以下顺序推进：

1. 先落最小 preview API 和 source status。
2. 先只做指数 + 研究池重点标的，不一开始覆盖全市场。
3. 先保证 UI 标签和降级空态正确，再扩更复杂的数据刷新策略。
4. 等正式实时源明确后，再决定是否把分钟 K、异动和盘中候选池也接进预览层。

## Done When

未来开始实现时，可以用以下标准验收：

1. 交易日白天可以看到监控计划的盘中触发状态，而不影响最新 `READY snapshot`。
2. 盘中预览与盘后正式视图在 UI 和 API 上明确分层。
3. 预览源失败时，页面显示“预览不可用/延迟”而不是错误冒充正式数据。
4. 盘后 `daily_sync`、`daily_screener`、`daily_backtest` 的语义和结果不因盘中预览层而改变。

## 当前状态

当前状态：已进入最小 experimental 实现阶段，但仍未达到正式商业实时层标准。

当前仓库已落地的 v0.1 范围：

1. `GET /api/v1/preview/watchlist`
   返回手动监控池的盘中预览报价、买点/止盈/风控/止损触发状态，以及 preview source status。
2. `POST /api/v1/preview/watchlist/run-check`
   允许手动触发一次盘中检查，并在命中时写入 alerts。
3. resident scheduler
   常驻 loop 现在会顺带跑盘中监控 tick，把命中的实盘提醒写到本地 alerts JSONL。
4. workbench
   watchlist 区块会自动轮询盘中预览层，展示盘中价和当前信号阶段，并通过浏览器通知尝试提醒新的盘中告警。

当前仍然明确保持的边界：

1. 盘中预览仍然不写入 `READY snapshot`，也不参与回测。
2. 当前只覆盖手动监控池，不覆盖全市场实时扫描。
3. 当前默认 realtime provider 仍是 `experimental`，不应被误认为最终授权商业实时源。
