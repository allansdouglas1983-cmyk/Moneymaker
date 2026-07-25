"""tennis_edge — a private automated tennis betting/tipping system.

Built around one honest question: can we beat the closing line? Everything here is
measured against a de-vigged sharp market price, walk-forward, with no lookahead. A model
that cannot beat that benchmark does not get promoted, however elegant it is.

Layout:
  devig      margin removal — proportional, multiplicative, power, Shin
  corpus     the typed match corpus (Tennis-Data), odds included for evaluation only
  metrics    log loss, Brier with calibration/resolution decomposition, calibration slope
  backtest   expanding-window walk-forward harness with day-clustered uncertainty
  ratings    Elo, surface Elo, games-weighted Elo, Glicko-2 — feature producers
  money      commission-aware break-even, EV, Kelly with estimation-error shrinkage
"""
from __future__ import annotations

PACKAGE_VERSION = "tennis-edge-v1"

__all__ = ["PACKAGE_VERSION"]
