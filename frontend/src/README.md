# Frontend Src

这里是 QuantA 前端主代码目录。

首版页面目标：

1. 市场概览
2. 个股详情
3. 选股结果
4. 回测报告

展示层只消费稳定的已发布快照视图。

当前已落的最小骨架：

1. `app/index.html`
2. `app/main.css`
3. `app/main.js`
4. `python3 scripts/run_frontend.py`

当前页面仍是 fixture-backed shell，但已经能通过前端 dev server 代理后端快照接口并完成 app-level smoke。
