// --- Snapshot ---
export interface SnapshotResponse {
  api_contract_version: string;
  snapshot_id: string;
  raw_snapshot_id: string;
  status: string;
  generated_at: string;
  price_basis: string;
  shadow_validation: ShadowValidation;
  market_overview: MarketOverview;
  screener: ScreenerSection;
  backtest: BacktestSection;
  task_status: Record<string, TaskStatusEntry>;
  runtime: RuntimeInfo;
}

export interface MarketOverview {
  trade_date: string;
  summary: string;
  regime_label: string;
  indices: IndexData[];
  breadth: MarketBreadth;
  highlights: MarketHighlight[];
}

export interface IndexData {
  symbol: string;
  name: string;
  close: number;
  change_pct: number;
  is_up: boolean;
}

export interface MarketBreadth {
  up_count: number;
  down_count: number;
  flat_count: number;
  total: number;
}

export interface MarketHighlight {
  title: string;
  detail: string;
}

export interface ScreenerSection {
  strategy_name: string;
  as_of_date: string;
  signal_price_basis: string;
  top_candidates: ScreenerCandidate[];
}

export interface ScreenerCandidate {
  symbol: string;
  name: string;
  strategy_name: string;
  score: number;
  trend_score: number | null;
  price_volume_score: number | null;
  capital_score: number | null;
  fundamental_score: number | null;
  thesis: string;
  signals: SignalOrRisk[];
  risks: SignalOrRisk[];
}

export interface SignalOrRisk {
  code: string;
  label: string;
  direction?: string;
}

export interface BacktestSection {
  strategy_name: string;
  window: string;
  metrics: BacktestMetrics;
  notes: BacktestNote[];
}

export interface BacktestMetrics {
  cagr_pct: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  profit_factor: number;
}

export interface BacktestNote {
  text: string;
}

export interface TaskStatusEntry {
  status: string;
  last_run: string | null;
  next_window: string | null;
}

export interface ShadowValidation {
  status: string;
  providers: unknown[];
}

export interface RuntimeInfo {
  backend_origin: string;
  frontend_origin: string;
  source_symbol_count: number;
  source_universe: string;
  [key: string]: unknown;
}

// --- System ---
export interface SystemHealthResponse {
  snapshot_id: string;
  status: string;
  alert_summary: AlertSummary;
  table_counts: Record<string, number>;
  task_count: number;
  alert_count: number;
}

export interface AlertSummary {
  window_count: number;
  severity_counts: {
    INFO: number;
    WARNING: number;
    ERROR: number;
  };
}

export interface AlertsResponse {
  items: AlertItem[];
  summary: AlertSummary;
}

export interface AlertItem {
  severity: string;
  triggered_at: string;
  alert_type: string;
  message: string;
}

// --- Stock ---
export interface StockSnapshotResponse {
  symbol: string;
  display_name: string;
  exchange: string;
  board: string;
  industry: string;
  latest_daily_bar: DailyBar | null;
  latest_price_bar: PriceBar | null;
}

export interface DailyBar {
  trade_date: string;
  open_raw: number;
  high_raw: number;
  low_raw: number;
  close_raw: number;
  pre_close_raw: number;
  volume: number | null;
  amount: number | null;
  turnover_rate: number | null;
}

export interface PriceBar {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
}

export interface KlineResponse {
  symbol: string;
  display_name: string;
  dataset: string;
  items: KlineItem[];
}

export interface KlineItem {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface IndicatorsResponse {
  symbol: string;
  display_name: string;
  latest_indicator: IndicatorData | null;
  latest_patterns: PatternSignal[];
}

export interface IndicatorData {
  trade_date: string;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
  macd_dif: number | null;
  macd_dea: number | null;
  macd_hist: number | null;
  rsi6: number | null;
  volume_ratio: number | null;
}

export interface PatternSignal {
  signal_code: string;
  signal_type: string;
  direction: string;
  is_triggered: boolean;
  signal_score: number;
}

export interface CapitalFlowResponse {
  symbol: string;
  display_name: string;
  latest_capital_feature: CapitalFeature | null;
}

export interface CapitalFeature {
  trade_date: string;
  main_net_inflow: number | null;
  main_net_inflow_ratio: number | null;
  northbound_net_inflow: number | null;
  has_dragon_tiger: boolean;
}

export interface FundamentalsResponse {
  symbol: string;
  display_name: string;
  latest_fundamental_feature: FundamentalFeature | null;
}

export interface FundamentalFeature {
  trade_date: string;
  report_period: string | null;
  roe_dt: number | null;
  debt_to_assets: number | null;
  total_revenue: number | null;
  net_profit_attr_p: number | null;
  cash_to_profit: number | null;
  fundamental_score: number | null;
}

export interface DisclosuresResponse {
  api_contract_version: string;
  symbol: string;
  display_name: string;
  as_of: DisclosureAsOf;
  range: DisclosureRange;
  latest_disclosure: DisclosureItem | null;
  items: DisclosureItem[];
}

export interface DisclosureAsOf {
  snapshot_id: string;
  publish_seq: number;
  raw_snapshot_id: string;
}

export interface DisclosureRange {
  row_count: number;
  date_from: string | null;
  date_to: string | null;
}

export interface DisclosureItem {
  trade_date: string;
  announcement_id: string;
  disclosure_event_id: string;
  disclosure_event_type: string;
  title: string;
  announcement_type_name: string | null;
  classification_explanation: string | null;
  body_summary: string | null;
  inquiry_status: string | null;
  reply_status: string | null;
  related_announcement_id: string | null;
  announcement_time: string | null;
  detail_url: string | null;
  source: string;
  effective_snapshot_id: string;
  effective_publish_seq: number;
}

export interface PriceVolumeAnalysisResponse {
  api_contract_version: string;
  symbol: string;
  display_name: string;
  as_of: PriceVolumeAsOf;
  price_state: PriceVolumePriceState;
  volume_state: PriceVolumeVolumeState;
  signals: PriceVolumeSignal[];
  decision: PriceVolumeDecision;
  capital_confirmation: PriceVolumeCapitalConfirmation;
}

export interface PriceVolumeAsOf {
  snapshot_id: string | null;
  raw_snapshot_id: string | null;
  trade_date: string | null;
  price_basis: string | null;
}

export interface PriceVolumePriceState {
  close: number | null;
  change_pct: number | null;
  ma5_gap_pct: number | null;
  ma20_gap_pct: number | null;
  return_5d_pct: number | null;
  return_20d_pct: number | null;
  ma_alignment: 'BULLISH' | 'BEARISH' | 'MIXED' | 'INSUFFICIENT';
  trend_state: 'STRENGTHENING' | 'REPAIRING' | 'WEAKENING' | 'NEUTRAL' | 'UNKNOWN';
  above_ma5: boolean;
  above_ma20: boolean;
}

export interface PriceVolumeVolumeState {
  volume: number | null;
  amount: number | null;
  volume_ratio: number | null;
  state: 'EXPANDING' | 'OVER_EXPANDED' | 'CONTRACTING' | 'NORMAL' | 'UNKNOWN';
  label: string;
}

export interface PriceVolumeSignal {
  signal_code: string;
  signal_type: string;
  direction: string;
  signal_score: number | null;
}

export interface PriceVolumeDecision {
  action: 'BUY' | 'WATCH' | 'AVOID' | 'UNAVAILABLE';
  title: string;
  summary: string;
  confidence_score: number;
  next_trigger_price: number | null;
  invalidation_price: number | null;
  reasons: string[];
  risks: string[];
}

export interface PriceVolumeCapitalConfirmation {
  main_net_inflow_ratio: number | null;
  northbound_net_inflow: number | null;
}

// --- Backtest detail ---
export interface BacktestRunResponse {
  backtest_id: string;
  strategy_name: string;
  metrics: BacktestMetrics;
  start_date: string;
  end_date: string;
  notes: BacktestNote[];
}

export interface EquityCurveResponse {
  equity_curve: EquityPoint[];
}

export interface EquityPoint {
  trade_date: string;
  equity: number;
  drawdown: number | null;
}

export interface TradesResponse {
  trades: TradeRecord[];
}

export interface TradeRecord {
  symbol: string;
  trade_date: string;
  side: string;
  trade_price: number;
  quantity: number;
  pnl: number | null;
}

// --- Tasks ---
export interface TaskRunsResponse {
  items: TaskRun[];
}

export interface TaskRun {
  task_id: string;
  task_name: string;
  biz_date: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
}

export interface StrategyWatchlistResponse {
  snapshot_id: string;
  raw_snapshot_id: string;
  as_of_date: string;
  price_basis: string;
  supported_strategies: string[];
  items: StrategyWatchlistItem[];
}

export interface StrategyWatchlistMutationResponse {
  status: string;
  item: StrategyWatchlistItem;
}

export interface StrategyWatchlistRemoveResponse {
  symbol: string;
  status: string;
}

export interface StrategyWatchlistItem {
  symbol: string;
  display_name: string;
  exchange: string | null;
  industry: string | null;
  preferred_strategy_name: string;
  strategy_name: string;
  trade_date: string | null;
  current_price: number | null;
  score: number | null;
  monitoring_status: 'BUY' | 'SELL' | 'WATCH' | 'AVOID' | 'UNAVAILABLE';
  entry_status: string;
  exit_status: string;
  buy_trigger_price: number | null;
  sell_trigger_price: number | null;
  defensive_exit_price: number | null;
  stop_loss_price: number | null;
  entry_reason: string;
  exit_reason: string;
  thesis: string;
  matched_rules: string[];
  risk_flags: string[];
  strategy_scores: Record<string, number>;
  report_period: string | null;
  snapshot_id: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface IntradayPreviewSourceStatus {
  provider: string;
  mode: string;
  status: string;
  message: string;
  market_phase: string;
  session_active: boolean;
  poll_interval_seconds: number;
  last_updated_at: string | null;
  quote_count?: number;
  watchlist_count?: number;
}

export interface IntradayThresholdFlags {
  buy_triggered: boolean;
  take_profit_triggered: boolean;
  risk_warning_triggered: boolean;
  stop_loss_triggered: boolean;
}

export interface IntradayPreviewItem extends StrategyWatchlistItem {
  realtime_price: number | null;
  realtime_pct_chg: number | null;
  realtime_trade_date: string | null;
  realtime_trade_time: string | null;
  realtime_updated_at: string | null;
  realtime_source: string | null;
  realtime_status: string;
  signal_stage:
    | 'BUY_TRIGGERED'
    | 'TAKE_PROFIT_TRIGGERED'
    | 'RISK_WARNING'
    | 'STOP_LOSS_TRIGGERED'
    | 'WATCHING'
    | 'UNAVAILABLE';
  signal_message: string;
  threshold_flags: IntradayThresholdFlags;
}

export interface IntradayPreviewWatchlistResponse {
  snapshot_id: string;
  raw_snapshot_id: string;
  as_of_date: string;
  items: IntradayPreviewItem[];
  source_status: IntradayPreviewSourceStatus;
  emitted_alerts?: string[];
}
