const snapshotRefNode = document.querySelector("#snapshot-ref");
const loadStatusNode = document.querySelector("#load-status");
const marketSummaryNode = document.querySelector("#market-summary");
const statusStripNode = document.querySelector("#status-strip");
const indexGridNode = document.querySelector("#index-grid");
const breadthGridNode = document.querySelector("#breadth-grid");
const highlightsListNode = document.querySelector("#highlights-list");
const screenerSummaryNode = document.querySelector("#screener-summary");
const candidateListNode = document.querySelector("#candidate-list");
const focusSymbolNode = document.querySelector("#focus-symbol");
const focusNameNode = document.querySelector("#focus-name");
const focusContextNode = document.querySelector("#focus-context");
const quoteGridNode = document.querySelector("#quote-grid");
const priceSeriesMetaNode = document.querySelector("#price-series-meta");
const priceChartNode = document.querySelector("#price-chart");
const priceGridNode = document.querySelector("#price-grid");
const indicatorGridNode = document.querySelector("#indicator-grid");
const patternListNode = document.querySelector("#pattern-list");
const capitalGridNode = document.querySelector("#capital-grid");
const strategyNameNode = document.querySelector("#strategy-name");
const metricGridNode = document.querySelector("#metric-grid");
const backtestRequestNode = document.querySelector("#backtest-request");
const equityChartNode = document.querySelector("#equity-chart");
const backtestNotesNode = document.querySelector("#backtest-notes");
const tradeTableBodyNode = document.querySelector("#trade-table-body");
const taskGridNode = document.querySelector("#task-grid");

function formatPercent(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) {
    return "--";
  }
  const numeric = Number(value);
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(digits)}%`;
}

function formatNumber(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) {
    return "--";
  }
  return Number(value).toFixed(digits);
}

function formatAmount(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "--";
  }
  const numeric = Number(value);
  if (Math.abs(numeric) >= 100000000) {
    return `${(numeric / 100000000).toFixed(2)}亿`;
  }
  if (Math.abs(numeric) >= 10000) {
    return `${(numeric / 10000).toFixed(2)}万`;
  }
  return numeric.toFixed(0);
}

function createTag(text, isRisk = false) {
  const span = document.createElement("span");
  span.className = isRisk ? "pill pill-risk" : "pill";
  span.textContent = text;
  return span;
}

function setError(message) {
  loadStatusNode.textContent = "加载失败";
  const banner = document.createElement("div");
  banner.className = "error-banner";
  banner.textContent = message;
  document.querySelector(".hero-panel").appendChild(banner);
}

function renderMiniCards(node, items) {
  node.innerHTML = "";
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "mini-card";
    card.innerHTML = `
      <p class="panel-kicker">${item.label}</p>
      <strong>${item.value}</strong>
      <p>${item.detail ?? ""}</p>
    `;
    node.appendChild(card);
  }
}

function buildLineChart(items, valueKey, accentClass) {
  if (!items.length) {
    return "<div class=\"chart-empty\">暂无数据</div>";
  }

  const values = items.map((item) => Number(item[valueKey]));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const width = 360;
  const height = 170;
  const padding = 18;
  const stepX = items.length === 1 ? 0 : (width - padding * 2) / (items.length - 1);
  const scaleY = (value) => {
    if (maxValue === minValue) {
      return height / 2;
    }
    const ratio = (value - minValue) / (maxValue - minValue);
    return height - padding - ratio * (height - padding * 2);
  };
  const points = values
    .map((value, index) => `${padding + stepX * index},${scaleY(value)}`)
    .join(" ");
  const areaPoints = `${padding},${height - padding} ${points} ${width - padding},${height - padding}`;

  return `
    <svg viewBox="0 0 ${width} ${height}" class="chart-svg ${accentClass}" aria-hidden="true">
      <polyline class="chart-area" points="${areaPoints}" />
      <polyline class="chart-line" points="${points}" />
      ${values
        .map(
          (value, index) =>
            `<circle class="chart-dot" cx="${padding + stepX * index}" cy="${scaleY(value)}" r="4" />`
        )
        .join("")}
    </svg>
  `;
}

function renderStatusStrip(snapshotPayload, screenerPayload, backtestPayload, focusSymbol) {
  const cards = [
    {
      label: "发布快照",
      value: snapshotPayload.snapshot_id,
      detail: snapshotPayload.status
    },
    {
      label: "选股运行",
      value: screenerPayload.run_id,
      detail: `${screenerPayload.result_count} 个结果`
    },
    {
      label: "回测窗口",
      value: backtestPayload.window,
      detail: backtestPayload.strategy_name
    },
    {
      label: "跟踪标的",
      value: focusSymbol,
      detail: snapshotPayload.market_overview.trade_date
    }
  ];

  statusStripNode.innerHTML = "";
  for (const card of cards) {
    const element = document.createElement("article");
    element.className = "status-card";
    element.innerHTML = `
      <p class="panel-kicker">${card.label}</p>
      <strong>${card.value}</strong>
      <p>${card.detail}</p>
    `;
    statusStripNode.appendChild(element);
  }
}

function renderMarketOverview(snapshotPayload) {
  marketSummaryNode.textContent = snapshotPayload.market_overview.summary;
  indexGridNode.innerHTML = "";
  for (const index of snapshotPayload.market_overview.indices) {
    const card = document.createElement("article");
    const deltaClass = index.change_pct >= 0 ? "delta-positive" : "delta-negative";
    card.className = "index-card";
    card.innerHTML = `
      <p class="panel-kicker">${index.name}</p>
      <strong>${index.close.toFixed(2)}</strong>
      <p class="${deltaClass}">${formatPercent(index.change_pct)}</p>
      <p>${index.commentary}</p>
    `;
    indexGridNode.appendChild(card);
  }

  breadthGridNode.innerHTML = "";
  for (const [label, value] of Object.entries(snapshotPayload.market_overview.breadth)) {
    const card = document.createElement("article");
    card.className = "breadth-card";
    card.innerHTML = `
      <p class="panel-kicker">${label}</p>
      <strong>${value}</strong>
    `;
    breadthGridNode.appendChild(card);
  }

  highlightsListNode.innerHTML = "";
  for (const item of snapshotPayload.market_overview.highlights) {
    const li = document.createElement("li");
    li.textContent = item;
    highlightsListNode.appendChild(li);
  }
}

function renderCandidates(screenerPayload) {
  screenerSummaryNode.textContent = `${screenerPayload.strategy_name} · ${screenerPayload.result_count} 个结果 · as-of ${screenerPayload.as_of_date}`;
  candidateListNode.innerHTML = "";

  for (const candidate of screenerPayload.results) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="candidate-headline">
        <div>
          <strong>${candidate.display_name}</strong>
          <div class="candidate-symbol">${candidate.symbol}</div>
        </div>
        <div class="candidate-score">Score ${candidate.score}</div>
      </div>
      <div class="candidate-copy">
        <p>${candidate.thesis}</p>
      </div>
      <div class="score-breakdown">
        <span>趋势 ${formatNumber(candidate.trend_score, 1)}</span>
        <span>量价 ${formatNumber(candidate.price_volume_score, 1)}</span>
        <span>资金 ${formatNumber(candidate.capital_score, 1)}</span>
      </div>
    `;

    const signals = document.createElement("div");
    signals.className = "pill-row";
    candidate.signals.forEach((signal) => signals.appendChild(createTag(signal)));
    candidate.risks.forEach((risk) => signals.appendChild(createTag(risk, true)));
    li.appendChild(signals);
    candidateListNode.appendChild(li);
  }
}

function renderFocusStock({
  focusCandidate,
  stockSnapshot,
  indicators,
  capitalFlow,
  priceSeries
}) {
  focusSymbolNode.textContent = focusCandidate.symbol;
  focusNameNode.textContent = stockSnapshot.display_name;
  focusContextNode.textContent = `${stockSnapshot.exchange} · ${stockSnapshot.board} · ${stockSnapshot.industry} · ${focusCandidate.strategy_name}`;

  renderMiniCards(quoteGridNode, [
    {
      label: "最新复权收盘",
      value: formatNumber(stockSnapshot.latest_price_bar?.close),
      detail: stockSnapshot.latest_price_bar?.trade_date ?? "--"
    },
    {
      label: "原始收盘",
      value: formatNumber(stockSnapshot.latest_daily_bar?.close_raw),
      detail: stockSnapshot.available_series.daily_bar.row_count + " 个原始日线"
    },
    {
      label: "候选得分",
      value: String(focusCandidate.score),
      detail: focusCandidate.strategy_name
    }
  ]);

  priceSeriesMetaNode.textContent = `${priceSeries.range.row_count} 个交易日 · ${priceSeries.as_of.price_basis.toUpperCase()}`;
  priceChartNode.innerHTML = buildLineChart(priceSeries.items, "close", "chart-accent");
  renderMiniCards(
    priceGridNode,
    priceSeries.items.map((item) => ({
      label: item.trade_date,
      value: formatNumber(item.close),
      detail: `成交额 ${formatAmount(item.amount)}`
    }))
  );

  const latestIndicator = indicators.latest_indicator ?? {};
  renderMiniCards(indicatorGridNode, [
    {
      label: "MA5",
      value: formatNumber(latestIndicator.ma5),
      detail: latestIndicator.trade_date ?? "--"
    },
    {
      label: "MACD Hist",
      value: formatNumber(latestIndicator.macd_hist, 3),
      detail: "趋势动量"
    },
    {
      label: "RSI6",
      value: formatNumber(latestIndicator.rsi6, 1),
      detail: "短线热度"
    },
    {
      label: "量比",
      value: formatNumber(latestIndicator.volume_ratio, 2),
      detail: "放量强度"
    }
  ]);

  patternListNode.innerHTML = "";
  for (const pattern of indicators.latest_patterns) {
    patternListNode.appendChild(createTag(pattern.signal_code));
  }
  if (focusCandidate.risks.length) {
    focusCandidate.risks.forEach((risk) => patternListNode.appendChild(createTag(risk, true)));
  }

  const latestCapital = capitalFlow.latest_capital_feature ?? {};
  renderMiniCards(capitalGridNode, [
    {
      label: "主力净流入占比",
      value: formatPercent((latestCapital.main_net_inflow_ratio ?? 0) * 100, 1),
      detail: `净流入 ${formatAmount(latestCapital.main_net_inflow)}`
    },
    {
      label: "北向净流入",
      value: formatAmount(latestCapital.northbound_net_inflow),
      detail: latestCapital.trade_date ?? "--"
    },
    {
      label: "龙虎榜标签",
      value: latestCapital.has_dragon_tiger ? "命中" : "无",
      detail: "波动提醒"
    }
  ]);
}

function renderBacktest(backtestPayload) {
  strategyNameNode.textContent = backtestPayload.strategy_name;
  backtestRequestNode.textContent = `请求 ${backtestPayload.request?.requested_at ?? "--"} · Top ${backtestPayload.request?.payload?.top_n ?? "--"} 等权 · ${backtestPayload.execution_price_basis.toUpperCase()} 成交`;

  renderMiniCards(metricGridNode, [
    ["年化收益", formatPercent(backtestPayload.metrics.annual_return_pct, 1)],
    ["总收益", formatPercent(backtestPayload.metrics.total_return_pct, 1)],
    ["最大回撤", formatPercent(backtestPayload.metrics.max_drawdown_pct, 2)],
    ["胜率", formatPercent(backtestPayload.metrics.win_rate_pct, 1)],
    ["盈亏比", formatNumber(backtestPayload.metrics.profit_factor, 2)]
  ].map(([label, value]) => ({ label, value, detail: backtestPayload.window })));

  equityChartNode.innerHTML = buildLineChart(backtestPayload.equity_curve, "equity", "chart-danger");

  backtestNotesNode.innerHTML = "";
  for (const note of backtestPayload.notes) {
    const li = document.createElement("li");
    li.textContent = note;
    backtestNotesNode.appendChild(li);
  }

  tradeTableBodyNode.innerHTML = "";
  for (const trade of backtestPayload.trades) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${trade.trade_date}</td>
      <td>${trade.side}</td>
      <td>${trade.symbol}</td>
      <td>${formatNumber(trade.trade_price)}</td>
      <td>${trade.quantity}</td>
      <td>${trade.pnl == null ? "--" : formatNumber(trade.pnl, 2)}</td>
    `;
    tradeTableBodyNode.appendChild(row);
  }
}

function renderTaskStatus(snapshotPayload) {
  taskGridNode.innerHTML = "";
  const taskEntries = [
    ["数据更新", snapshotPayload.task_status.data_update],
    ["分析计算", snapshotPayload.task_status.analysis],
    ["选股运行", snapshotPayload.task_status.screener],
    ["回测摘要", snapshotPayload.task_status.backtest],
    ["上次完成", snapshotPayload.task_status.last_run],
    ["下一窗口", snapshotPayload.task_status.next_window]
  ];

  for (const [label, value] of taskEntries) {
    const card = document.createElement("article");
    const status = value === "SUCCESS" ? "SUCCESS" : "WARN";
    card.className = "task-card";
    card.dataset.status = status;
    card.innerHTML = `
      <p class="panel-kicker">${label}</p>
      <strong>${value}</strong>
    `;
    taskGridNode.appendChild(card);
  }
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: {
      Accept: "application/json"
    }
  });

  if (!response.ok) {
    throw new Error(`${url} failed with status ${response.status}`);
  }

  return response.json();
}

async function fetchLatestSnapshot() {
  return fetchJson("/api/v1/snapshot/latest");
}

async function fetchWorkbenchData() {
  const snapshot = await fetchLatestSnapshot();
  const screener = await fetchJson("/api/v1/screener/runs/latest");
  const backtest = await fetchJson("/api/v1/backtests/runs/latest");
  const focusCandidate = screener.results[0];

  if (!focusCandidate) {
    throw new Error("latest screener returned no focus candidate");
  }

  const [stockSnapshot, indicators, capitalFlow, priceSeries] = await Promise.all([
    fetchJson(`/api/v1/stocks/${focusCandidate.symbol}/snapshot`),
    fetchJson(`/api/v1/stocks/${focusCandidate.symbol}/indicators`),
    fetchJson(`/api/v1/stocks/${focusCandidate.symbol}/capital-flow`),
    fetchJson(`/api/v1/stocks/${focusCandidate.symbol}/kline?dataset=price_series`)
  ]);

  return {
    snapshot,
    screener,
    backtest,
    focusCandidate,
    stockSnapshot,
    indicators,
    capitalFlow,
    priceSeries
  };
}

async function main() {
  try {
    const data = await fetchWorkbenchData();
    loadStatusNode.textContent = "已读取 READY 快照与详情";
    snapshotRefNode.textContent = `${data.snapshot.snapshot_id} / ${data.snapshot.raw_snapshot_id}`;
    renderStatusStrip(data.snapshot, data.screener, data.backtest, data.focusCandidate.symbol);
    renderMarketOverview(data.snapshot);
    renderCandidates(data.screener);
    renderFocusStock(data);
    renderBacktest(data.backtest);
    renderTaskStatus(data.snapshot);
  } catch (error) {
    console.error(error);
    setError("前端未能读取研究工作台数据，请先确认 backend/frontend dev server 都已启动。");
  }
}

main();
