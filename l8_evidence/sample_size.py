"""SPEC-094: pre-registered sample size, power assumptions and borrowed-constant hygiene.

SPECIFICATION.md §9.2 ("Sample size is derived, not asserted") and §9.3 ("No borrowed
thresholds"), plus ``.claude/rules/evidence.md``'s "No borrowed thresholds" section: every
experiment declares, BEFORE observation, its minimum economically meaningful effect (the
``delta`` in the formula below), power assumptions, primary endpoint and stopping rule.
Sample size is then DERIVED, never asserted:

    N ~ (z_alpha + z_beta)^2 * sigma_d^2 / delta^2

where ``d_r = L_r(market) - L_r(combined)`` (SPEC-090's race-level paired log-score
difference, ``.claude/rules/evidence.md``), ``sigma_d`` is its standard deviation, and
``delta`` is the smallest improvement that could produce meaningful executable value.
"2,000 races/bets" is a planning estimate, never a statistical law (§9.2) — this module
computes the real number from the experiment's own pre-registered assumptions instead of
letting anyone assert a round number.

This module owns the DERIVATION half of SPEC-094 (the power/sample-size arithmetic and
the static borrowed-constant scan). The DECLARATION half — recording ``hypothesis``,
``primary_endpoint``, ``stopping_rule`` and ``alpha_budget`` as an immutable
pre-registration, before any observation, with append-only enforcement — already lives in
``l8_evidence.trial_ledger.TrialRegistration`` (SPEC-091). This module is intentionally
NOT coupled to that one: it takes no dependency on ``trial_ledger`` and performs no I/O.
The intended flow (documented, not enforced by an import, so each module stays a single
concern) is:

    1. Before observing any race outcome, a human research pipeline calls
       :func:`plan_for_registration` with the experiment's declared
       :class:`PowerAssumptions` (minimum economically meaningful effect on the ``d_r``
       scale, and power assumptions chosen from prior data or a pre-registered pilot).
    2. The resulting :class:`SampleSizePlan`'s :meth:`SampleSizePlan.content_digest` is
       quoted inside the ``stopping_rule`` (or ``hypothesis``) text the caller passes to
       ``TrialRegistration`` — e.g. ``"anytime-valid confidence sequence; sample size plan
       sha256:<digest>"`` — so the ledger's immutable record carries verifiable evidence
       that a sample-size derivation existed BEFORE observation, without this module ever
       importing the ledger or the ledger importing this module.

``sigma_d`` is NOT invented by this module. It MUST come from prior data (an earlier
cohort's observed race-level paired difference) or a pre-registered pilot estimate,
exactly as ``alpha``/``power``/``delta`` must be chosen and declared before observation.
This module only validates shape (a positive ``Decimal``) and performs the deterministic
arithmetic; the honesty of *where the number came from* is the trial ledger's
pre-registration discipline (SPEC-091) and the human research process around it, not
something a validator can enforce by construction.

Every argument to :class:`PowerAssumptions` is explicit — there are no default values for
``alpha``, ``power``, ``sigma_d`` or ``delta``. A borrowed default would be exactly the
kind of un-declared assumption §9.3 rejects.

``Decimal`` is used for the assumptions themselves (house convention: money/statistical
boundary inputs are never float — see CLAUDE.md "Types"). The z-value inverse-CDF lookup
and the resulting ``n_required`` arithmetic use ``float`` intermediates deliberately: these
are STATISTICAL PLANNING DIAGNOSTICS (how many races a study needs), not a priced bet, a
stake or a settlement figure, so CLAUDE.md's no-float rule for money types does not apply
here — SPEC-094 itself names the formula with ``z`` values, which have no exact decimal
closed form.

No LLM computes, adjusts or approves any value in this module. Every number here is either
supplied directly by the caller (a human research pipeline declaring its own pre-registered
assumptions) or deterministic arithmetic performed in this file.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256
from json import dumps
from typing import Any, Final, Mapping

__all__ = [
    "SampleSizeError",
    "BorrowedConstantError",
    "PowerAssumptions",
    "SampleSizePlan",
    "standard_normal_inverse_cdf",
    "derive_sample_size",
    "plan_for_registration",
    "BORROWED_CONSTANTS",
    "assert_no_borrowed_gate_constants",
]

_ZERO = Decimal(0)
_ONE = Decimal(1)
_TWO = Decimal(2)

#: The exact formula string SPEC-094 and SPECIFICATION.md §9.2 name. Carried on every
#: :class:`SampleSizePlan` so a reader never has to trust that the arithmetic below matches
#: the spec's own notation.
FORMULA: Final[str] = "N = (z_alpha + z_beta)^2 * sigma_d^2 / delta^2"

#: The four thresholds SPECIFICATION.md §9.3 / ``.claude/rules/evidence.md`` name and
#: reject as universal gates. Recorded here (not just in prose) so
#: :func:`assert_no_borrowed_gate_constants` has a single, documented list to scan for.
BORROWED_CONSTANTS: Final[tuple[str, ...]] = (
    "dR2>=0.01",
    "t>=3",
    "ECE<=0.02",
    "2000 bets",
)

# The literal substrings/patterns scanned for in gate-spec YAML TEXT (not just its parsed
# values). This is deliberately a lexical, best-effort scan and is documented as such:
#
# * "dR2" / "ECE" are matched as bare substrings (case-sensitive) because both names are
#   distinctive enough in a gate-spec vocabulary that a false positive would itself be
#   worth a human's attention (e.g. someone drafting a new gate item that quotes the
#   forbidden ECE<=0.02 threshold in a comment, which a parsed-value-only check would
#   never see).
# * "t>=3" is matched with flexible whitespace around the operator (`t >= 3`, `t>=3`) via a
#   word-boundary regex, so it does not also fire on unrelated uses of the letter "t" or
#   the number 3 elsewhere in the document.
# * "2000" is matched as a standalone number token (word-boundary) so it does not fire on
#   substrings of unrelated numbers (dates, other IDs) — mirroring the spirit of the
#   frozen gate specs' own "2,000 races/bets is a planning estimate" caveat.
#
# This function is a SECONDARY defence. The PRIMARY defence for
# ``specs/gates/v1.yaml``/``specs/gates/predictor-p1.yaml`` is the no-numeric-leaves pin in
# ``tests/unit/l8/test_gate_spec_file.py`` (SPEC-093), which inspects the *parsed* YAML
# document and refuses any numeric leaf anywhere in the gate structure. That test cannot,
# by construction, see a borrowed constant hidden in a YAML *comment* (comments are
# discarded by the YAML parser) — this scan operates on the raw file text specifically to
# close that gap. Neither check is a substitute for the other.
_ECE_TOKEN: Final[str] = "ECE"
_DR2_TOKEN: Final[str] = "dR2"
_T_GE_3_PATTERN: Final[re.Pattern[str]] = re.compile(r"\bt\s*>=\s*3\b")
_STANDALONE_2000_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b2000\b")


class SampleSizeError(ValueError):
    """Base for every SPEC-094 validation error."""


class BorrowedConstantError(SampleSizeError):
    """Gate-spec text contains a banned borrowed constant (§9.3 / CLAUDE.md).

    Raised by :func:`assert_no_borrowed_gate_constants`. This is a static-hygiene refusal,
    not a numerical one: no arithmetic in this module ever produces or consumes these
    constants.
    """


def _require_decimal(value: Any, where: str) -> None:
    if not isinstance(value, Decimal):
        raise SampleSizeError(f"{where} must be a Decimal, got {type(value)!r}")


def _require_open_unit_interval(value: Decimal, where: str) -> None:
    _require_decimal(value, where)
    if not (_ZERO < value < _ONE):
        raise SampleSizeError(f"{where} must lie strictly inside (0, 1), got {value}")


def _require_positive(value: Decimal, where: str) -> None:
    _require_decimal(value, where)
    if value <= _ZERO:
        raise SampleSizeError(f"{where} must be positive, got {value}")


@dataclass(frozen=True)
class PowerAssumptions:
    """The pre-registered power assumptions behind a SPEC-094 sample-size derivation.

    Every field is declared BEFORE observation (§9.2/§9.3) and every argument is
    mandatory — there are no defaults, so a caller can never accidentally inherit a
    borrowed constant by omission.

    Attributes:
        alpha: The two-tailed-or-one-tailed (see ``two_sided``) significance level, a
            ``Decimal`` strictly inside ``(0, 1)``. E.g. ``Decimal("0.05")``.
        power: The desired statistical power, a ``Decimal`` strictly inside ``(0, 1)``.
            ``beta = 1 - power`` is the tolerated Type II error rate (see :attr:`beta`).
        sigma_d: The standard deviation of the race-level paired difference ``d_r =
            L_r(market) - L_r(combined)`` (SPEC-090's unit of analysis; see
            ``.claude/rules/evidence.md`` "The race is the unit of analysis"). MUST come
            from prior data or a pre-registered pilot estimate — this module validates
            only that it is a positive ``Decimal``; it does not and cannot verify
            provenance. A ``Decimal`` invented on the spot to make a target ``N`` look
            good is a violation of §9.2's discipline even though it will pass this
            module's shape check.
        delta: The minimum economically meaningful effect on the ``d_r`` scale (§9.2's
            "smallest improvement that could produce meaningful executable value").
            A positive ``Decimal``.
        two_sided: Whether the test is two-sided. When ``True``, the alpha tail used for
            ``z_alpha`` is ``alpha / 2`` on each side; when ``False``, the full ``alpha``
            is used as a single tail.
    """

    alpha: Decimal
    power: Decimal
    sigma_d: Decimal
    delta: Decimal
    two_sided: bool

    def __post_init__(self) -> None:
        _require_open_unit_interval(self.alpha, "alpha")
        _require_open_unit_interval(self.power, "power")
        _require_positive(self.sigma_d, "sigma_d")
        _require_positive(self.delta, "delta")
        if not isinstance(self.two_sided, bool):
            raise SampleSizeError(f"two_sided must be a bool, got {type(self.two_sided)!r}")

    @property
    def beta(self) -> Decimal:
        """The tolerated Type II error rate, ``1 - power``."""
        return _ONE - self.power


def standard_normal_inverse_cdf(p: float) -> float:
    """The standard normal inverse CDF (quantile function), ``Phi^-1(p)``.

    Implements Peter J. Acklam's rational (Chebyshev-fitted) approximation — "An algorithm
    for computing the inverse normal cumulative distribution function" (2003), the same
    algorithm underlying widely used statistical libraries' fast inverse-normal paths.
    Documented maximum RELATIVE error over the full open interval ``(0, 1)`` is
    ``1.15e-9`` (Acklam's own published bound); this implementation uses the base
    rational approximation without Acklam's optional Halley refinement step, which is more
    than sufficient precision for sample-size planning (the anchors below are exact to
    4 decimal places, far tighter than any planning decision needs).

    Anchors (also asserted in this module's test suite):
        ``standard_normal_inverse_cdf(0.975) ~ 1.959964``
        ``standard_normal_inverse_cdf(0.95)  ~ 1.644854``
        ``standard_normal_inverse_cdf(0.90)  ~ 1.281552``

    Args:
        p: A probability strictly inside ``(0, 1)``.

    Raises:
        SampleSizeError: if ``p`` is not strictly inside ``(0, 1)``.
    """
    if not 0.0 < p < 1.0:
        raise SampleSizeError(f"p must lie strictly inside (0, 1), got {p}")

    # Coefficients for the rational approximations, Acklam (2003).
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )

    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        numerator = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        denominator = (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        return numerator / denominator
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    )


def _jsonable(value: Any) -> Any:
    """Recursively convert a value into a JSON-serialisable, canonically-ordered form.

    House style (mirrors ``l8_evidence.trial_ledger._jsonable`` and
    ``l8_evidence.prediction_snapshots._jsonable``, duplicated here rather than imported
    to keep this module free of any dependency on the trial ledger): ``Decimal`` renders
    via ``str`` (never float ``repr``), mappings with sorted keys at every nesting level,
    dataclasses via their fields, everything else passed through unchanged (``float``,
    ``bool``, ``str``, ``int`` are all natively JSON-serialisable and already
    deterministic — ``repr(float)`` round-trips exactly since Python 3.1, and the ``json``
    module's default float formatter uses that same representation).
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    return value


def _content_digest(record: Any) -> str:
    payload = _jsonable(asdict(record))
    canonical = dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SampleSizePlan:
    """A derived SPEC-094 sample-size plan: the assumptions plus the arithmetic result.

    Attributes:
        assumptions: The :class:`PowerAssumptions` this plan was derived from.
        z_alpha: The standard-normal quantile for the (tail-adjusted, see
            :attr:`PowerAssumptions.two_sided`) significance level.
        z_beta: The standard-normal quantile for the desired power.
        n_required: ``ceil((z_alpha + z_beta)^2 * sigma_d^2 / delta^2)``, always ``>= 1``.
        formula: The exact formula string this plan implements (:data:`FORMULA`), carried
            on the record so a reader never has to trust prose describing the arithmetic.
    """

    assumptions: PowerAssumptions
    z_alpha: float
    z_beta: float
    n_required: int
    formula: str = FORMULA

    def __post_init__(self) -> None:
        if self.formula != FORMULA:
            raise SampleSizeError(f"formula must be {FORMULA!r}, got {self.formula!r}")
        if self.n_required < 1:
            raise SampleSizeError(f"n_required must be >= 1, got {self.n_required}")

    def content_digest(self) -> str:
        """A ``sha256:``-prefixed deterministic digest of this plan's full content.

        Intended to be quoted in a :class:`l8_evidence.trial_ledger.TrialRegistration`'s
        ``stopping_rule`` (or ``hypothesis``) text as evidence that a sample-size
        derivation existed BEFORE observation — see this module's docstring for the full
        intended flow. Two plans built from identical assumptions always produce an
        identical digest; changing any assumption changes it.
        """
        return _content_digest(self)


def derive_sample_size(assumptions: PowerAssumptions) -> SampleSizePlan:
    """Derive a :class:`SampleSizePlan` from pre-registered :class:`PowerAssumptions`.

    Implements ``N ~ (z_alpha + z_beta)^2 * sigma_d^2 / delta^2`` (SPEC-094,
    SPECIFICATION.md §9.2): ``z_alpha`` is the standard-normal quantile for the
    significance level (tail-adjusted for ``two_sided``); ``z_beta`` is the standard-normal
    quantile for the desired power. ``n_required`` is the ceiling of the resulting float,
    floored at 1 (a study can never require fewer than one observed race).

    This function performs arithmetic only. It does not check, and cannot check, whether
    ``sigma_d`` was honestly sourced from prior data or a pilot rather than invented to hit
    a target ``N`` — see :class:`PowerAssumptions`'s docstring.
    """
    tail = assumptions.alpha / _TWO if assumptions.two_sided else assumptions.alpha
    z_alpha = standard_normal_inverse_cdf(float(_ONE - tail))
    z_beta = standard_normal_inverse_cdf(float(assumptions.power))

    sigma_d = float(assumptions.sigma_d)
    delta = float(assumptions.delta)
    n_float = ((z_alpha + z_beta) ** 2) * (sigma_d**2) / (delta**2)
    n_required = max(1, math.ceil(n_float))

    return SampleSizePlan(
        assumptions=assumptions,
        z_alpha=z_alpha,
        z_beta=z_beta,
        n_required=n_required,
    )


def plan_for_registration(assumptions: PowerAssumptions) -> SampleSizePlan:
    """Alias of :func:`derive_sample_size`, named for the pre-registration call site.

    Identical behaviour to :func:`derive_sample_size` — a separate name so a caller
    building a :class:`l8_evidence.trial_ledger.TrialRegistration` can read, at the call
    site, that this plan is the one whose :meth:`SampleSizePlan.content_digest` is meant
    to be quoted in that registration's ``stopping_rule``/``hypothesis`` text (see this
    module's docstring for the full flow). This module does not import ``trial_ledger``;
    wiring the digest into a registration's text is the caller's responsibility.
    """
    return derive_sample_size(assumptions)


def assert_no_borrowed_gate_constants(yaml_text: str) -> None:
    """Raise :class:`BorrowedConstantError` if ``yaml_text`` contains a banned constant.

    Scans the RAW TEXT of a gate-spec YAML document (not its parsed value tree — see the
    module-level comment above :data:`BORROWED_CONSTANTS` for why both checks exist and
    neither substitutes for the other) for the four thresholds SPECIFICATION.md §9.3
    rejects as universal gates: ``dR2 >= 0.01``, ``t >= 3``, ``ECE <= 0.02``, and
    "2,000 bets". This is a lexical, best-effort scan, documented as such; it is not a
    substitute for the numeric-leaf pin test that inspects the parsed gate structure
    itself.

    Args:
        yaml_text: The raw file contents of a gate-spec YAML document.

    Raises:
        BorrowedConstantError: if any banned constant pattern is found.
    """
    hits: list[str] = []
    if _DR2_TOKEN in yaml_text:
        hits.append(_DR2_TOKEN)
    if _ECE_TOKEN in yaml_text:
        hits.append(_ECE_TOKEN)
    if _T_GE_3_PATTERN.search(yaml_text):
        hits.append("t>=3")
    if _STANDALONE_2000_PATTERN.search(yaml_text):
        hits.append("2000")
    if hits:
        raise BorrowedConstantError(
            "borrowed gate constant(s) detected: "
            f"{sorted(set(hits))}; SPECIFICATION.md §9.3 rejects these as gates"
        )
