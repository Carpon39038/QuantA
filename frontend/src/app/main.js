const snapshotRefNode = document.querySelector("#snapshot-ref");
const loadStatusNode = document.querySelector("#load-status");
const marketSummaryNode = document.querySelector("#market-summary");
const statusStripNode = document.querySelector("#status-strip");
const indexGridNode = document.querySelector("#index-grid");
const breadthGridNode = document.querySelector("#breadth-grid");
const highlightsListNode = document.querySelector("#highlights-list");
const candidateListNode = document.querySelector("#candidate-list");
const strategyNameNode = document.querySelector("#strategy-name");
const metricGridNode = document.querySelector("#metric-grid");
const backtestNotesNode = document.querySelector("#backtest-notes");
const taskGridNode = document.querySelector("#task-grid");

function formatPercent(value) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
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

function renderStatusStrip(payload) {
  const cards = [
    {
      label: "发布快照",
      value: payload.snapshot_id,
      detail: payload.status
    },
    {
      label: "原始快照",
      value: payload.raw_snapshot_id,
      detail: payload.price_basis.toUpperCase()
    },
    {
      label: "市场状态",
      value: payload.market_overview.regime_label,
      detail: payload.market_overview.trade_date
    },
    {
      label: "策略窗口",
      value: payload.backtest.window,
      detail: payload.screener.strategy_name
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

function renderMarketOverview(payload) {
  marketSummaryNode.textContent = payload.market_overview.summary;
  indexGridNode.innerHTML = "";
  for (const index of payload.market_overview.indices) {
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
  for (const [label, value] of Object.entries(payload.market_overview.breadth)) {
    const card = document.createElement("article");
    card.className = "breadth-card";
    card.innerHTML = `
      <p class="panel-kicker">${label}</p>
      <strong>${value}</strong>
    `;
    breadthGridNode.appendChild(card);
  }

  highlightsListNode.innerHTML = "";
  for (const item of payload.market_overview.highlights) {
    const li = document.createElement("li");
    li.textContent = item;
    highlightsListNode.appendChild(li);
  }
}

function renderCandidates(payload) {
  candidateListNode.innerHTML = "";
  for (const candidate of payload.screener.top_candidates) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="candidate-headline">
        <div>
          <strong>${candidate.name}</strong>
          <div class="candidate-symbol">${candidate.symbol}</div>
        </div>
        <div class="candidate-score">Score ${candidate.score}</div>
      </div>
      <div class="candidate-copy">
        <p>${candidate.thesis}</p>
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

function renderBacktest(payload) {
  strategyNameNode.textContent = payload.backtest.strategy_name;
  metricGridNode.innerHTML = "";

  const metrics = [
    ["年化收益", `${payload.backtest.metrics.cagr_pct.toFixed(1)}%`],
    ["最大回撤", `${payload.backtest.metrics.max_drawdown_pct.toFixed(1)}%`],
    ["胜率", `${payload.backtest.metrics.win_rate_pct.toFixed(1)}%`],
    ["盈亏比", payload.backtest.metrics.profit_factor.toFixed(2)]
  ];

  for (const [label, value] of metrics) {
    const card = document.createElement("article");
    card.className = "metric-card";
    card.innerHTML = `
      <p class="panel-kicker">${label}</p>
      <strong>${value}</strong>
    `;
    metricGridNode.appendChild(card);
  }

  backtestNotesNode.innerHTML = "";
  for (const note of payload.backtest.notes) {
    const li = document.createElement("li");
    li.textContent = note;
    backtestNotesNode.appendChild(li);
  }
}

function renderTaskStatus(payload) {
  taskGridNode.innerHTML = "";
  const taskEntries = [
    ["数据更新", payload.task_status.data_update],
    ["分析计算", payload.task_status.analysis],
    ["选股运行", payload.task_status.screener],
    ["回测摘要", payload.task_status.backtest],
    ["上次完成", payload.task_status.last_run],
    ["下一窗口", payload.task_status.next_window]
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

async function fetchLatestSnapshot() {
  const response = await fetch("/api/v1/snapshot/latest", {
    headers: {
      Accept: "application/json"
    }
  });

  if (!response.ok) {
    throw new Error(`snapshot request failed with status ${response.status}`);
  }

  return response.json();
}

async function main() {
  try {
    const payload = await fetchLatestSnapshot();
    loadStatusNode.textContent = "已读取 READY 快照";
    snapshotRefNode.textContent = `${payload.snapshot_id} / ${payload.raw_snapshot_id}`;
    renderStatusStrip(payload);
    renderMarketOverview(payload);
    renderCandidates(payload);
    renderBacktest(payload);
    renderTaskStatus(payload);
  } catch (error) {
    console.error(error);
    setError("前端未能读取快照，请先确认 backend/frontend dev server 都已启动。");
  }
}

main();
