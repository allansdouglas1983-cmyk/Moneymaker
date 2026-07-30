"""Replay staking rules over a real settled bet sequence, and measure what happened.

Expected terminal wealth is ``W0 + sum(S_i * ev_i)``. A staking rule chooses the weights
``S_i``; it can never change any ``ev_i``. So no rule creates an edge, every rule is
optimal for some objective, the objectives conflict, and the only way to choose one is to
trade them all over the same real sequence and compare the paths.

This package is the measuring instrument, not a strategy. It contains no staking rule.
"""
