"""Tests de la matemática de riesgo (funciones puras)."""

from app.schemas.config import RiskConfig
from app.trading.risk import compute_stops, position_size


def test_compute_stops_percent():
    risk = RiskConfig(stop_loss_pct=2.0, take_profit_pct=4.0, use_atr_stops=False)
    stops = compute_stops(entry_price=100.0, risk=risk)
    assert stops.stop_loss == 98.0
    assert stops.take_profit == 104.0


def test_compute_stops_atr():
    risk = RiskConfig(use_atr_stops=True, atr_multiplier=2.0, stop_loss_pct=2.0, take_profit_pct=4.0)
    stops = compute_stops(entry_price=100.0, risk=risk, atr_value=1.5)
    # distancia stop = 1.5 * 2 = 3 -> SL = 97; RR = 4/2 = 2 -> TP dist = 6 -> TP = 106
    assert stops.stop_loss == 97.0
    assert stops.take_profit == 106.0


def test_position_size_respects_risk_pct():
    risk = RiskConfig(risk_per_trade_pct=1.0)
    # equity 10000, riesgo 1% = 100. Stop a 2 de distancia -> qty = 100/2 = 50
    qty = position_size(equity=10_000, entry_price=100.0, stop_loss=98.0, risk=risk, cash=1_000_000)
    assert abs(qty - 50.0) < 1e-9


def test_position_size_capped_by_cash():
    risk = RiskConfig(risk_per_trade_pct=50.0)
    # El riesgo pediría una cantidad enorme, pero solo hay 500 de efectivo.
    qty = position_size(equity=10_000, entry_price=100.0, stop_loss=99.0, risk=risk, cash=500.0)
    assert abs(qty - 5.0) < 1e-9  # 500 / 100


def test_position_size_zero_when_no_stop_distance():
    risk = RiskConfig()
    assert position_size(equity=10_000, entry_price=100.0, stop_loss=100.0, risk=risk, cash=1000) == 0.0
