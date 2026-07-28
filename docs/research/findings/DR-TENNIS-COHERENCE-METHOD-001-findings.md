# DR-TENNIS-COHERENCE-METHOD-001 findings — inverting the derivative complex

**Returned:** 2026-07-28, via founder's ChatGPT Deep Research. **Assessed:** 2026-07-28
(assessment follows the verbatim report). `citeturn...` markers are source-tool artifacts
preserved verbatim; load-bearing claims are SOURCE CLAIMS pending spot-check.

---

## Verbatim report

# Inverting Tennis Derivative Markets to Price Match Odds

## Bottom line

I did **not** find a peer-reviewed tennis paper that matches your exact pipeline: fit latent per-point serve probabilities from the **derivative complex only**, exclude Match Odds on purpose, push those probabilities through a Barnett–Clarke style recursion, and then use the implied Match Odds gap as a predictive feature. What I did find is that the **building blocks** are known separately: point-based tennis inversion exists in the modeling literature; cross-market mispricing between equivalent tennis markets is documented; and multi-market latent-parameter fitting exists in other sports under labels such as **implied scoring-rate estimation**, **implied volatility**, or **constrained probability identification**. The exact "derivatives-only tennis coherence layer against Match Odds" does **not** appear to be an established named method in the literature I could locate as of July 2026. citeturn35view0turn36view0turn14search9turn22search21turn30search1

The strongest documented warning is not a subtle modeling issue. It is **market microstructure**. In the closest peer-reviewed tennis evidence, Brown's Wimbledon study of win and set markets shows that mispricing between equivalent markets rises sharply in-play, the set market updates materially less often than the win market, and price discovery is overwhelmingly led by the win market. Brown also warns that using **transaction prices** in the thinner set market is problematic because they may be **substantially lagged**, which can create spurious cross-market mispricing. That warning lands directly on your archive choice: BASIC is last-traded-price data, not contemporaneous quotes. citeturn33view0turn34view1turn34view2turn34view3

On the modeling side, the literature rejects the strict i.i.d.-points assumption, but it also repeatedly finds that the deviation is **small enough that the i.i.d. approximation remains useful** for many forecasting tasks. Klaassen and Magnus show that points are neither independent nor identically distributed, yet the extra non-i.i.d. structure only improves fit **marginally** relative to an i.i.d. model. Newton and Aslam likewise find the usual analytical curves are "remarkably robust" even under fairly strong simulated non-i.i.d. effects. More modern tractable corrections exist, especially dynamic updating of serve ability; Kovalchik and Reid report a **28% reduction** in serve-prediction error and a **four-percentage-point** improvement in win-prediction accuracy relative to a constant-ability model. citeturn37view0turn38view0turn39view0turn43view0

If you want the shortest possible falsifier, the literature points to this: **test whether the coherence gap predicts final outcomes out of sample after conditioning on Match Odds, or whether it only predicts short-horizon convergence of stale derivative prices toward the match market.** If the signal lives mainly in lead–lag correction rather than in final-outcome forecasting, stop. Brown's one-minute Wimbledon evidence already tells you that the win market is usually the price-discovery leader, so a derivative-only gap that mainly forecasts the next minute of match-market movement is much more likely to be a stale-quote artifact than an informational edge. citeturn34view3

## What the literature actually establishes about the method

The **tennis modeling** literature absolutely knows how to move between latent serve-point probabilities and match-win probabilities. Klaassen and Magnus's *Forecasting the winner of a tennis match* (European Journal of Operational Research, 2003) is explicit about this: the model depends on two fixed parameters, the probability each player wins a point on serve, and their procedure literally says they obtain one unknown combination **"by inverting the program"** to recover the two serve probabilities. That is genuine structural inversion, but it is **not** inversion from derivative betting markets. It is inversion from estimated match- and point-level quantities. citeturn36view0

The **betting-market** literature also knows the nearby idea of equivalent-asset fitting and cross-market arbitrage. Brown's *Information Processing Constraints and Asset Mispricing* (Economic Journal, 2014) studies the win market and the set market as two ways of pricing the same underlying outcome. He defines mispricing as the absolute difference between the implied win probabilities in those two markets, finds that average mispricing is small overall but rises more than tenfold in-play, and studies price discovery between the two. That is not your proposed latent-\(p_a,p_b\) fit, but it is the closest tennis-market paper to the question "can derivative markets be inverted into a primary-market view, and what goes wrong when you try?" citeturn33view0turn34view3

Outside tennis, the **exact family resemblance** is clearer. In soccer, Feng, Polson, and Xu's EPL work estimates **expected scoring rates** from a **matrix of score-market odds**; Polson and coauthors also use spread and moneyline prices to construct **implied volatility** for sports games. More recently, Karimov et al. propose **domain-driven identification** of football probabilities by integrating estimates across **multiple groups of betting markets** in a constrained optimization problem, explicitly because odds are noisy and market structure matters. Those papers make it reasonable to describe your approach as belonging to the family of **multi-market latent-state or latent-parameter identification**, but they do not provide a recognized tennis-specific label for your exact implementation. citeturn14search9turn22search21turn30search1

A useful negative result comes from the broader tennis prediction literature. Wilkens's *Sports prediction and betting models in the machine learning age: The case of tennis* (Journal of Sports Analytics, 2021) describes the dominant tennis forecasting strands as **regression-based**, **point-based**, and **paired-comparison** models, with bookmaker odds used as benchmark or input. In that survey-sized paper, the empirical conclusion is that **most relevant information is already embedded in betting markets**, and adding player- and match-specific covariates typically does not materially improve on odds-implied forecasts. That does not disprove your derivative-only coherence layer, but it does raise the prior bar materially: a new market-derived signal has to beat a literature in which betting odds already absorb most of the observable information. citeturn35view0

## The documented failure modes

The literature does document failure modes, and for your setup they rank as follows.

**Stale or lagged transaction prices in thinner derivative markets.** This is the biggest red flag for your specific data regime. Brown explains that using transaction prices is problematic because volume in the set market is often lower than in the win market, so one can end up comparing a current win-market valuation with a **lagged** set-market valuation and "wrongly infer" large mispricings. Brown's solution was to use **quoted midpoints**, not transaction prices, precisely to avoid this confound. BASIC gives you last-traded prices, not quoted midpoints, so the best-documented tennis failure mode is present by construction. citeturn34view2

**Asynchronous updating and price-discovery dominance by Match Odds.** Brown finds that the set market changes price much less frequently during play, and that mispricing is substantially higher in-play than pre-match. In the same study, price discovery is led by the more frequently updated win market, with the win market contributing **82% to more than 100%** of price discovery across the sampled matches; values above 100% occur when the set market's occasional leads are more often wrong than right. Crucially for you, Brown reports this on **one-minute sampled** data, so your archive frequency does not neutralize the problem. If the most liquid primary market already leads the derivative market at one-minute resolution, a coherence gap can easily be a delayed-markets diagnostic rather than a forecasting edge. citeturn34view1turn34view3

**Misspecification from constant-ability i.i.d. points.** Klaassen and Magnus show that points are not i.i.d.: winning the previous point raises the chance of winning the current point, important points are harder for the server, and weaker players show stronger deviations. But their own empirical fit comparison also finds that adding the non-i.i.d. structure improves prediction only **marginally** relative to an i.i.d. model. So the failure is real, but the literature does not portray it as fatal at match level. It is a second-order modeling error, not the first-order killer that stale derivative prices appear to be. citeturn37view0turn38view0

**Identification and market-selection sensitivity.** Klaassen and Magnus explicitly note that the two unknown serve probabilities cannot be obtained from match data alone; they need an additional estimated quantity and then invert the program. That is an identification result in miniature: one coarse summary is not enough to pin down two latent serve parameters. Your version replaces point data with derivative prices, but the same logic applies. Unless the chosen derivative subset contributes genuinely distinct information, the fit can be weakly identified or highly sensitive to which markets are included. Recent football work on multi-market probability identification solves this by imposing market-structure-aware constraints, which is another indication that the raw inverse problem is not automatically well-posed. citeturn36view0turn30search1

**Extreme-price and normalization pathologies.** Brown observed that the implied win probability extracted from the set market can produce extreme values above 1 and excluded **7,520** out of **392,944** observations in a robustness check for exactly this reason. In fixed-odds tennis, Candila and Scognamillo argue that standard normalization methods are biased under favorite–longshot effects and propose a new procedure; a later comment argues that the new adjustment is costly and does not materially improve prediction. The exact exchange context differs, but the lesson is the same: the transformation from odds to probabilities is itself a material modeling choice, and at the tails it can become pathological. citeturn34view2turn42search0turn42search1

**Liquidity and attention are confounded and raw volume is not a clean monotone quality signal.** Abinzano, Muga, and Santamaría show that in tennis exchanges, odds mispricing is positively associated with trading volume but negatively associated with institutional-bettor presence, while information is incorporated more quickly in the more attended market. That matters because it means "thicker market = better market" is too simple. A raw liquidity threshold chosen after the fact is not strongly grounded by the literature. What the literature does support is that attention, trader composition, and market type all matter to pricing quality. citeturn11view0turn28search19

## What the literature says about the i.i.d. points assumption

The classical empirical answer remains the anchor. Klaassen and Magnus's JASA paper (2001) uses nearly **90,000 Wimbledon points** and rejects the strict i.i.d. hypothesis. The deviations run in intuitive directions: positive dependence from the previous point, pressure effects on important points, and larger deviations for weaker players. But the same paper says the deviations are **small**, and their fit diagnostics show that the non-i.i.d. model is only **marginally** better than the i.i.d. model once ranking-based strength variables are already included. That is the best direct answer to your question about match-level error size: the assumption is false, but the forecasting damage at match level is usually presented as limited rather than disastrous. citeturn37view0turn38view0

Klaassen and Magnus's 2003 follow-up carries that judgment into operational forecasting. Their TENNISPROB framework assumes fixed serve-point probabilities within the match and says this assumption provides a "sufficiently good approximation" for applications such as forecasting, while explicitly leaving open whether a Bayesian updating rule for \(p_a\) and \(p_b\) would reduce forecast error further. citeturn36view0

Newton and Aslam's *Monte Carlo Tennis* (SIAM Review, 2006) is even more reassuring about robustness. They allow serve probabilities to vary point to point, game to game, and match to match; they simulate hot-hand and back-to-the-wall effects; and they still conclude that the standard i.i.d.-based analytical curves remain **remarkably robust and accurate**, even under relatively strong non-i.i.d. perturbations. citeturn43view0

There are also tractable corrections if you decide the baseline survives. Kovalchik and Reid (International Journal of Forecasting, 2019) combine a pre-match calibration with dynamic empirical-Bayes updates and show a **28% reduction** in serve-prediction error and a **four-point increase** in win-prediction accuracy versus a constant-ability model. Ferrante, Carrari, and Fonseca (Electronic Journal of Applied Statistical Analysis, 2017) propose a generalized Markov tennis model with one probability regime for the first six points of a game and another after first deuce, specifically to relax the basic i.i.d. setup without abandoning tractability. citeturn39view0turn20search5

## Whether the derivative complex appears to add useful information

This is where the literature is weakest for your exact design. I did **not** locate a published peer-reviewed tennis paper that directly measures the predictive value of
\[
\logit(p_{\text{coherence}}) - \logit(p_{\text{match-odds}})
\]
when \(p_{\text{coherence}}\) is obtained from derivative markets only. That absence is itself useful: this is **not** a settled, validated signal class in the public tennis literature as of July 2026. The closest published papers study either model-vs-market comparisons or equivalent-market mispricing, not your exact delta. citeturn35view0turn8search2turn24search0

What the closest evidence suggests is not encouraging. Easton and Uylangco's within-match study (International Journal of Forecasting, 2010) finds that the probabilities implied by betting odds match a structural tennis model **very closely**, with extremely high correlation. Wilkens's broader 2021 study finds that bookmaker odds already carry most of the predictive information for tennis outcome models. Brown's 2014 paper then adds the cross-market point: when win and set markets differ, the win market is usually the price-discovery leader. Put together, the existing evidence tilts toward the view that cross-market differences are more likely to be **timing, microstructure, and market-attention effects** than a stable source of extra match-outcome information. citeturn4view1turn35view0turn34view3

There is one nuance worth keeping. Easton and Uylangco also report that betting odds appear to anticipate the significance of service breaks up to four points before the break actually occurs, while not fully capturing one specific post-break weakness immediately. That suggests live markets can incorporate **anticipatory** or behavioral information beyond a purely score-state Markov model. So if a derivative-only coherence layer ever works, one possible route is not "markets are independent," but "some derivatives encode anticipatory information differently from Match Odds." I found no peer-reviewed paper showing that this survives into a reusable out-of-sample feature in tennis, but the possibility is not logically excluded. citeturn4view1

## The cheapest falsifying diagnostic

The single cheapest diagnostic is a **lead–lag freshness test**, not a full betting backtest. Compute your coherence-implied match probability from derivatives at time \(t\), form the gap against Match Odds at the same timestamp, and then separate two questions: does the gap improve prediction of the **final match outcome** after conditioning on contemporaneous Match Odds, and does it predict the **next movement in Match Odds** or next-minute convergence much more strongly than it predicts the final outcome? Brown's one-minute Wimbledon evidence strongly suggests the second is the baseline expectation when derivative markets are slower-moving than the win market. citeturn34view3

Concretely, the stop rule should be plain. If the gap has little or no out-of-sample incremental value for final outcomes once Match Odds is included, but it **does** predict short-horizon catch-up of Match Odds or disappears when you restrict to the freshest derivative snapshots, then you have learned the cheapest important truth: the layer is mostly a detector of stale derivative pricing. At that point, under your BASIC-only constraint, the rational advisory conclusion is **stop**. citeturn34view1turn34view2turn34view3

If you want the falsifier stated in one sentence: **test whether the coherence gap forecasts outcomes, or merely forecasts that the derivatives will catch up to Match Odds.** If it is the latter, the method is not discovering a new probability; it is replaying a microstructure lag, and your archive design makes that lag especially hard to distinguish from "signal." citeturn34view2turn34view3

## Advisory conclusion

The most defensible advisory judgment, from the literature available as of July 2026, is this. The **conceptual ingredients** of your method are known. Structural inversion in tennis models is known; cross-market equivalent-asset mispricing in tennis is known; and multi-market latent-parameter fitting is known in other sports. But the **exact method you care about is not established in the literature**, and the most directly relevant published tennis evidence identifies a failure mode that bears directly on your dataset: **lagged last-trade prices in thinner derivatives can manufacture apparent mispricing, while Match Odds usually leads price discovery even at one-minute sampling frequency**. citeturn36view0turn34view2turn34view3turn14search9turn22search21

So the ranked answer to your deliverables is straightforward. The method is **not established as a named tennis literature method**, though it sits near published families of structural inversion and cross-market probability identification. The top documented failure mode is **staleness/asynchronous updating under thin derivative trading**, followed by **Match-Odds price-discovery dominance**, then **i.i.d.-points misspecification**, then **identification and market-selection sensitivity**, and then **extreme-price/normalization pathologies**. On the i.i.d. question, the literature says the assumption is **false but often good enough at match level**, with dynamic corrections available and modest-to-material incremental gains if you need them. And the single cheapest falsifier is the **lead–lag freshness test** above. citeturn34view2turn34view3turn37view0turn38view0turn39view0turn43view0

---

## Assessment (2026-07-28)

**The decisive point:** the best-documented failure mode — stale last-trade prices in thin
derivative markets manufacturing apparent mispricing — is present in our data **by
construction** (BASIC is last-trade only; Brown's remedy was quoted midpoints, which we
cannot have). And Match Odds leads price discovery 82–100%+ *at the same one-minute sampling
our archive has*, so frequency does not save us.

**Decisions taken:**
1. **The coherence layer is demoted from "next layer to build" to "probe with a stop
   rule".** The first and possibly only computation is the lead–lag freshness test exactly
   as specified: does the gap predict final outcomes conditioned on Match Odds, or merely
   predict derivative catch-up? If the latter, stop, record the negative result, and the
   solver stays what it is today — built, tested, unused.
2. **Priority order after all three findings:** cross-book dispersion, then intransitivity,
   then (if ever) the coherence probe. The coherence layer had been the flagship of the
   layer roadmap; the literature says its realistic prior is death by staleness.
3. **The i.i.d.-points concern is retired as a blocker.** False but adequate at match
   level (Klaassen–Magnus marginal-fit result; Newton–Aslam robustness). No correction
   is built unless the probe survives.
4. Companion blocker `EXT-XMARKET-002` (independence) stands unchanged — this finding
   *reinforces* it: observed cross-market differences tilt toward timing/attention effects,
   not independent information.

**Impact on claims:** none published change. Development time is redirected before being
spent — which is exactly what the request was for.
