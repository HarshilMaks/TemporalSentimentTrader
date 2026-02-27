# TFT Trader — Trading Strategy V5

**Last Updated:** 2026-02-27  
**Version:** 5.0 (Triangulation / Information Arbitrage)  
**Strategy Type:** Swing Trading (3-7 day holds)  
**Processing:** EOD Batch (after market close, zero-cost)  
**Source of Truth:** `Stock Prediction/Global Algorithmic Trading Blueprint.pdf`

---

## Philosophy

The stock market is a Level 2 Chaotic System — predicting it changes it. Elite quant funds with supercomputers operate at 51-55% win rates. We don't chase accuracy. We enforce risk math that makes even a 45% win rate profitable.

The edge comes from three places:
1. **Information synthesis** — combining data sources most retail traders don't look at together
2. **Triangulation filtering** — only trading when 3 independent layers agree (kills 90% of noise)
3. **Risk management math** — 1:2 risk/reward makes the system profitable regardless of prediction accuracy

---

## The Triangulation Method

A BUY signal is generated ONLY when three completely independent data dimensions align simultaneously. This is not traditional technical analysis — it's information arbitrage.

### Layer 1: Legal Insider Conviction (0-30 points)

Corporate insiders sell stock for many reasons. They only BUY with their own money for one reason: they expect significant growth.

- **Data Source:** SEC EDGAR Form 4 filings (daily, free, public)
- **Signal:** CEO/CFO/Director open-market purchases
- **Scoring:**
  - CEO or CFO bought in last 7 days → 30 points
  - Director bought in last 7 days → 20 points
  - Multiple insiders buying → bonus points (cluster buying)
  - No insider activity → 0 points

### Layer 2: Institutional Flow (0-20 points)

Retail traders can't move markets. Institutional funds accumulate positions over weeks, but they can't hide their volume footprint.

- **Data Source:** EOD volume data from yfinance
- **Signal:** Unusual volume relative to 20-day average
- **Scoring:**
  - Volume > 2x 20-day average → 20 points
  - Volume > 1.5x 20-day average → 10 points
  - Normal volume → 0 points

### Layer 3: Retail Sentiment Breakout (0-20 points)

Retail sentiment acts as the match that ignites the fuel accumulated by insiders and institutions. Social hype drives the momentum needed for a 3-7 day swing.

- **Data Source:** Reddit (r/wallstreetbets, r/stocks, r/investing) via PRAW
- **Signal:** Positive sentiment + high mention count
- **Scoring:**
  - Sentiment > 0.3 AND mentions > 20 → 20 points
  - Sentiment > 0.3 OR mentions > 20 → 10 points
  - Negative or low activity → 0 points

### Technical Confirmation (0-30 points)

Technical indicators confirm the setup is actionable, not just interesting.

- RSI < 35 (oversold with reversal potential) → 10 points
- MACD > Signal line (bullish crossover) → 10 points
- Price > SMA 50 (above key support) → 10 points

### Total Score

```
Triangulation Score = Insider + Flow + Sentiment + Technical
Range: 0-100

Score > 60  → candidate for ML validation
Score ≤ 60  → skip, not enough convergence
```

---

## Entry Criteria (BUY Signal)

ALL of the following must pass in sequence:

```
Step 1: REGIME CHECK
  └─ SPY close > SMA 200? 
     ├─ NO  → STOP. Market is bearish. No buys.
     └─ YES → continue

Step 2: TRIANGULATION SCORE
  └─ Score > 60?
     ├─ NO  → SKIP. Not enough signal convergence.
     └─ YES → continue

Step 3: ML ENSEMBLE VALIDATION
  └─ Ensemble prediction = BUY with confidence > 0.7?
     ├─ NO  → HOLD. Models don't confirm.
     └─ YES → continue

Step 4: RISK MANAGER APPROVAL
  └─ All 6 risk rules pass?
     ├─ NO  → REJECT. Log rejection reason.
     └─ YES → CREATE TRADING SIGNAL

Signal created with:
  entry_price  = current close
  target_price = entry × 1.07 to 1.10  (+7-10%)
  stop_loss    = entry × 0.95           (-5%)
```

---

## Exit Criteria

Positions are monitored daily. Exit on the FIRST condition that triggers:

### 1. Take Profit (Target Hit)
```
current_price ≥ target_price → CLOSE
exit_reason = "target"
Expected: +7-10% gain
```

### 2. Stop Loss (Risk Control)
```
current_price ≤ stop_loss → CLOSE
exit_reason = "stop_loss"
Expected: -5% loss (hard limit, non-negotiable)
```

### 3. Signal Flip (Momentum Reversal)
```
Technical reversal:
  RSI > 70 AND MACD < signal AND price < SMA 50 → CLOSE
  
Sentiment reversal:
  sentiment_score < -0.2 AND sentiment_trend < -0.1 → CLOSE

exit_reason = "signal_flip"
```

### 4. Time Decay (Max Hold Period)
```
days_held > 7 → CLOSE
exit_reason = "time_decay"
Swing trades should resolve within a week. If not, the thesis is broken.
```

### 5. Regime Shift
```
SPY drops below SMA 200 → CLOSE ALL POSITIONS
exit_reason = "regime_shift"
Don't fight a bear market.
```

---

## Risk Management

### Position Sizing Formula

```python
risk_amount    = portfolio_value × 0.02      # max 2% at risk per trade
stop_distance  = entry_price × 0.05          # 5% stop loss distance
shares         = risk_amount / stop_distance
position_value = shares × entry_price
position_value = min(position_value, portfolio_value × 0.20)  # cap at 20%
```

### Example

```
Portfolio: $10,000
Entry: $100
Stop: $95 (5% below)

Risk amount: $10,000 × 0.02 = $200
Stop distance: $5
Shares: $200 / $5 = 40 shares
Position value: 40 × $100 = $4,000 (40%)
Capped at 20%: $2,000 → 20 shares
```

### Hard Rules (Non-Negotiable)

| Rule | Value | Consequence of Violation |
|------|-------|--------------------------|
| Min confidence | 70% | Signal rejected |
| Max position size | 20% of portfolio | Position capped |
| Max risk per trade | 2% of portfolio | Position sized down |
| Stop loss | -5% from entry | Auto-exit |
| Take profit | +7-10% from entry | Auto-exit |
| Min risk/reward | 1:2 | Signal rejected |
| Max concurrent positions | 5 | New signals queued |
| Max portfolio drawdown | 15% | ALL positions closed, trading paused |

---

## Mathematical Expectancy

This is why the system works even with mediocre prediction accuracy.

### At 45% Win Rate (Conservative)
```
100 trades:
  55 losses × -5%  = -275%
  45 wins   × +10% = +450%
  NET = +175%
```

### At 55% Win Rate (Realistic Target)
```
100 trades:
  45 losses × -5%  = -225%
  55 wins   × +10% = +550%
  NET = +325%
```

### At 35% Win Rate (Worst Case)
```
100 trades:
  65 losses × -5%  = -325%
  35 wins   × +10% = +350%
  NET = +25% (still profitable)
```

The breakeven win rate with 1:2 risk/reward is 33.3%. Anything above that is profit. The ML models and triangulation exist to push the win rate above 45%, but the risk manager guarantees survival even if they underperform.

---

## ML Ensemble Validation

The ensemble doesn't generate signals — it validates candidates that already passed triangulation scoring.

| Model | Weight | Input | Role |
|-------|--------|-------|------|
| XGBoost | 40% | 25-d feature vector | Hard thresholds, feature importance |
| LightGBM | 30% | 25-d feature vector | Fast inference, generalization |
| TFT/LSTM | 30% | 30-day sequences | Temporal patterns, sentiment buildup |

```
final_confidence = 0.40 × xgb + 0.30 × lgb + 0.30 × tft
signal = argmax(probabilities)
if confidence < 0.7 → HOLD (not confident enough, skip)
```

---

## Regime Filter

The market regime gate prevents the system from generating BUY signals during bear markets. This single rule eliminates the biggest source of losses in algorithmic trading: catching falling knives.

```
SPY daily close > SMA 200 → BULL → BUY signals allowed
SPY daily close < SMA 200 → BEAR → ALL BUY signals disabled
```

This is checked BEFORE any triangulation scoring. If the market is bearish, the entire pipeline short-circuits.

---

## Target Market

- **Asset Class:** US Equities only (India market support planned later)
- **Universe:** Stocks appearing in Reddit discussions + stocks with recent insider buying
- **Liquidity Filter:** $1B+ market cap (ensures clean exits)
- **Hold Period:** 3-7 days
- **Trade Frequency:** 2-5 signals per week (quality over quantity)

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Win rate | 45-55% | Realistic for swing trading with triangulation |
| Average gain | +7-10% | Per winning trade |
| Average loss | -5% | Hard stop, no exceptions |
| Risk/reward | 1:2 minimum | Enforced by risk manager |
| Max drawdown | 15% | Circuit breaker |
| Sharpe ratio | > 1.5 | Risk-adjusted returns |
| Trade frequency | 2-5/week | Only high-conviction setups |
| Avg hold period | 3-7 days | Swing trading window |

---

## What This Strategy Is NOT

- **Not day trading.** No intraday data, no tick-level analysis, no sub-minute decisions.
- **Not buy-and-hold.** Positions are closed within 7 days, win or lose.
- **Not a prediction engine.** It's a signal filter. Most tickers are skipped every day.
- **Not autonomous.** Human reviews every signal before execution.
- **Not high-frequency.** EOD batch processing, once per day, after market close.
- **Not guaranteed profit.** It's a probabilistic edge, not a crystal ball.

---

*Version 5.0 — Triangulation / Information Arbitrage Strategy*  
*Bible: `Stock Prediction/Global Algorithmic Trading Blueprint.pdf`*
