// Tipos compartidos que reflejan las respuestas del backend.

export interface RiskConfig {
  risk_per_trade_pct: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  use_atr_stops: boolean;
  atr_multiplier: number;
  trailing_stop_pct: number | null;
  max_open_positions: number;
  max_daily_loss_pct: number;
  max_drawdown_pct: number;
}

export interface LLMConfig {
  enabled: boolean;
  provider: "ollama" | "groq" | "gemini";
  model: string;
  veto_threshold: number;
  temperature: number;
  use_news: boolean;
}

export interface BotConfig {
  mode: "paper" | "live";
  base_currency: string;
  starting_capital: number;
  pairs: string[];
  timeframe: string;
  active_strategy: string;
  strategy_params: Record<string, number>;
  risk: RiskConfig;
  llm: LLMConfig;
  fee_pct: number;
  slippage_pct: number;
}

export interface ParamSpec {
  key: string;
  label: string;
  type: "int" | "float";
  default: number;
  min: number;
  max: number;
  step: number;
  description: string;
}

export interface StrategyInfo {
  id: string;
  name: string;
  description: string;
  params: ParamSpec[];
  default_params: Record<string, number>;
}

export interface Position {
  id: number;
  symbol: string;
  side: string;
  status: string;
  quantity: number;
  entry_price: number;
  exit_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  strategy: string | null;
  open_reason: string | null;
  close_reason: string | null;
  llm_explanation: string | null;
  llm_confidence: number | null;
  opened_at: string | null;
  closed_at: string | null;
  current_price?: number;
  market_value?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
}

export interface Signal {
  id: number;
  timestamp: string;
  symbol: string;
  action: string;
  strategy: string | null;
  indicators: Record<string, unknown>;
  llm_used: boolean;
  llm_decision: string | null;
  llm_confidence: number | null;
  llm_explanation: string | null;
  executed: boolean;
  position_id: number | null;
}

export interface DashboardPayload {
  type?: string;
  account: { base_currency: string; cash: number; initial_capital: number; realized_pnl: number; peak_equity: number };
  bot: { status: string; mode: string; kill_switch: boolean; started_at: string | null; last_cycle_at: string | null; last_error: string | null };
  portfolio: {
    equity: number; cash: number; positions_value: number; unrealized_pnl: number;
    realized_pnl: number; total_pnl: number; total_pnl_pct: number; drawdown_pct: number;
  };
  prices: Record<string, number>;
  open_positions: Position[];
  recent_trades: Position[];
  recent_signals: Signal[];
  equity_curve: { timestamp: string; equity: number }[];
  logs: { id: number; timestamp: string; level: string; message: string; context: Record<string, unknown> }[];
}

export interface BacktestResult {
  metrics: Record<string, number | null | string>;
  equity_curve: { timestamp: string; equity: number }[];
  trades: {
    entry_time: string; exit_time: string; entry_price: number; exit_price: number;
    quantity: number; pnl: number; pnl_pct: number; reason: string;
  }[];
}

export interface OptResultItem {
  rank: number;
  strategy_id: string;
  strategy_name: string;
  params: Record<string, number>;
  risk_config: Partial<RiskConfig>;
  metrics: Record<string, number | null | string>;
  score: number;
}

export interface OptJob {
  id: string;
  status: "running" | "done" | "error";
  total: number;
  done: number;
  objective: string;
  objective_label: string;
  symbol: string;
  timeframe: string;
  error: string | null;
  results: OptResultItem[];
}

export interface SavedConfig {
  id: number;
  name: string;
  note: string | null;
  source: string | null;
  created_at: string | null;
  config: BotConfig;
}
