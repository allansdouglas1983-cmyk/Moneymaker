# DR-TENNIS-MICROSTRUCTURE-001 findings — LTP versus the crossable price, pre-off

**Returned:** 2026-07-28, via founder's ChatGPT Deep Research. **Assessed:** 2026-07-28
(assessment follows the verbatim report). This request was **BLOCKING for money claims**;
the assessment below converts its answer into the operating standard. `citeturn...`
markers are source-tool artifacts preserved verbatim; load-bearing claims are SOURCE CLAIMS
pending spot-check.

---

## Verbatim report

# DR-TENNIS-MICROSTRUCTURE-001 LTP versus crossable price pre-off

## Executive findings

I did **not** locate a peer-reviewed tennis study that directly tabulates the contemporaneous distribution of **Betfair last-traded price minus simultaneously available best back price** in the **pre-off** period. What the published literature does provide is a closely related set of microstructure measures: the **quoted spread** between best back and best lay, and the **effective spread** between a trade and the prior quote midpoint. In Wimbledon betting data, Brown's 2015 study defines those two quantities exactly this way; across the full Wimbledon sample, mean quoted spread was **1.8 implied-probability points** and mean effective spread was **1.56 implied-probability points**, which is evidence that transaction prices and displayed quotes are related but not interchangeable. In a well-evidenced practitioner study using Betfair order-book data on horse racing, average pre-race spreads were about **1 tick** even three hours before the start, while the same author found greyhound markets could still be about **5 ticks** wide two minutes before the off. That is not tennis, but it is strong evidence that the mapping from trade price to crossable quote is **market- and liquidity-dependent**, not a constant. citeturn12view1turn13view0turn13view1

For **money claims**, settling a backtest at LTP is not defensible as a claim of realised execution. The microstructure reason is straightforward: a trade print is not itself a standing offer, and whether *you* could have transacted depends on the **side of the trade, queue priority, displayed depth, hidden liquidity, stake size, and order-processing delay**. The literature on execution modelling treats these quantities as essential inputs; it does not treat last trade alone as a sufficient statistic for fill. citeturn29view0turn27view2turn29view2turn37view3

Your **traded-through survival test** *is* recognisable in execution/backtesting practice, but not—so far as I could establish under this search—as a named, standard estimator in the Betfair or prediction-market literature. In the wider execution literature it corresponds to a **trade-through fill assumption**, i.e. a conservative simulation rule under which merely *touching* your limit price is not enough; price must post or trade **through** it before a fill is credited. That is a real, known convention. But it is still only a **simulation rule**, not proof of your own fill, because fill probability also depends on the amount of liquidity **ahead of you** in the queue. citeturn25search0turn29view0turn37view3

I did **not** find an established method that reconstructs **true pre-off fill probabilities or depth from Betfair BASIC-style LTP traces alone**. What *is* established is narrower: transaction-only methods such as **Roll (1984)** and later extensions can estimate an **implicit effective spread / liquidity proxy** from transaction prices, and survival-analysis or deep-learning methods can estimate **fill probabilities**—but the latter require actual **order-book state and/or order history**, not just last trades. With BASIC only, the most defensible quantitative upgrade is therefore a **cost band or interval**, not a genuine queue-aware fill probability. citeturn27view4turn27view5turn28view0turn28view1turn27view2turn29view2

For **UK Betfair tennis commission as of 2026-07**, a flat **2%** is **not** the universal current rule. Betfair's current UK-facing Exchange terms say that, for customers opted into **My Betfair Rewards**, the commission rate is determined by the **chosen package**; the public example shown is the **Basic package at 2%** on **net winnings in a market**. Betfair also states that Betfair Points no longer affect commission rates for those customers **except for Australasian events**, where the old Market Base Rate / Discount Rate system still applies. Beyond ordinary commission, Betfair now also applies an **Expert Fee** to a very small number of highly profitable Exchange customers; the old **Premium Charge ended in January 2025**. citeturn35search1turn35search3turn31view2turn33view0turn31view3

The minimum defensible external standard I can support from the literature is therefore: **do not present BASIC-trace returns as realised returns**. Present them as **hypothetical** unless and until you have quote/depth evidence sufficient to model execution. If you report them at all, attach the three-way **SUPPORTED / UNSUPPORTED / NO_EVIDENCE** split, keep **NO_EVIDENCE in the denominator**, and add an explicit execution-cost sensitivity band rather than a single point estimate. That conclusion is an inference from the execution literature's emphasis on quotes, queue position, censored non-fills, and order-book state. citeturn27view2turn29view0turn29view2turn37view3

## What is actually established about LTP and the crossable quote

Betfair's own streaming/API documentation distinguishes **last traded price** from quote fields. In the stream, `EX_LTP` is explicitly "**last traded price**"; quote subscriptions such as `EX_BEST_OFFERS` / `EX_BEST_OFFERS_DISP` are separate, and market-definition messages separately expose fields such as `inPlay`, `turnInPlayEnabled`, `crossMatching`, and `betDelay`. In other words, Betfair itself models **trade prints**, **quotes**, and **mechanics** as different data objects; that is the right starting point for your research question. citeturn1view1

The cleanest academic tennis-adjacent evidence I found is Andrew Brown's **2015** working paper on Betfair's Wimbledon market data. Brown defines **quoted spread** as the gap between the best back and best lay in implied-probability space, and **effective spread** as the absolute difference between the last transaction price and the previous quote midpoint, multiplied by two to make it comparable to quoted spread. He explicitly notes that effective spread can exceed quoted spread when trades are large enough to **walk down the book**, which is exactly the microstructure reason LTP is not a fill proxy. In the Wimbledon data, Brown reports mean quoted spread **1.8** and mean effective spread **1.56**, again in implied-probability points. citeturn12view1

That same paper also shows that **pre-match and in-play are materially different regimes**. In Brown's Wimbledon placebo test, the in-play indicator adds **3.55 implied-probability points** to quoted spread and **1.16** to effective spread, which is a large widening relative to pre-match. So even within one sport, the relationship between print and quote is regime-dependent; pre-off and in-play should not be pooled. citeturn12view1

For practitioner evidence, the most concrete public work I located is mildbyte's **2017** Betfair order-book analysis. Using Stream API order-book captures, he reports that average pre-race horse-racing spreads were effectively as tight as they could be—about **1 tick** on average even three hours before the race—while greyhound markets could still sit around **5 ticks** wide even two minutes before the start. That is not a statistical bound for tennis, but it strongly reinforces the point that the print-to-quote mapping depends on **market thickness and sport**, not on any universal Betfair rule. citeturn13view0turn13view1

A second useful benchmark comes from Croxson and Reade's **2011** in-play football study and Ozgit's **2005** pre-match NBA study. Both look at Betfair through the lens of **best available exchange prices**, not last trade. Croxson and Reade report an average exchange overround of about **0.9%** on best-back prices for small immediate bets in liquid football markets, and cite Ozgit's **1.09%** figure for pre-match NBA on Betfair. That shows that in sufficiently liquid markets, the crossable inside quote can be very tight. But it still does **not** identify LTP, because they are measuring **quotes available to customers**, not the most recent print. citeturn16view0turn17search0

The bottom line for question 1 is therefore narrow but usable: **the literature supports a close relationship between LTP and the quote midpoint in liquid markets, but I did not locate a published tennis-specific distribution of LTP versus simultaneous best back pre-off**. The strongest externally sourced quantitative substitutes are tennis quoted/effective spread measures and non-tennis practitioner tick-spread studies. citeturn12view1turn13view0turn13view1

## Whether LTP is biased as an estimator of a takeable price

For an **immediate backer**, the takeable price is the **best lay**, not the best back, and certainly not the undifferentiated last trade. For a **passive backer** trying to rest at price \(P\), a later trade at \(P\) does not by itself prove your own order would have matched, because Betfair is a **price-time priority** book. Those two observations already imply that LTP is not an unbiased estimator of "what a backer would have got." citeturn29view0turn27view2

Brown's microstructure definitions make the same point from a different angle. His **effective spread** is built precisely because transaction prices and displayed quotes are not the same object; he notes that large trades can execute at prices worse than the inside quote because they consume multiple levels of book depth. That is direct evidence that any LTP settlement rule hides an unmodelled execution-cost term. citeturn12view1

There is also strong evidence that **stake size matters materially**. Croxson and Reade show that in big, liquid football markets the exchange remains better than major bookmakers for fairly substantial stakes, but their estimated "switching point" for average winning odds is around **$450–$480**, beyond which a punter can become worse off if they must walk down the exchange book. They also warn—drawing on Ozgit—that inside prices can fail to provide sufficient liquidity for larger orders. That supports a practical reading: for **small** size, LTP may be "near" a crossable price in liquid markets; for larger size, using LTP as though it were your achieved price becomes increasingly optimistic. citeturn16view0

For **passive order claims**, the optimism is stronger. The execution literature emphasises that fill probability is governed by **price**, **time priority**, **queue ahead**, **queue behind**, **opposite-side depth**, and **market conditions**. A later trade print at your target price only proves that *someone* transacted there, not that *your* queue position would have reached the front. citeturn29view0turn37view3

So the directional answer to question 2 is: **settling at LTP is generally optimistic for a money claim**. It tends to **overstate** what a backer could *guarantee* as a taker, because immediate execution occurs at the best lay, not at LTP; and it also tends to **overstate** passive fills, because LTP contains no queue information. The literature I found does **not** provide a clean side-specific, pre-off tennis distribution of that bias in ticks or basis points. What it does establish is that the omitted term is real, can be of the same order as the quoted/effective spread, and increases with stake size and market thinness. citeturn12view1turn16view0turn29view0turn37view3

## What can and cannot be inferred from a BASIC trace

There *is* a well-established literature on extracting **liquidity-cost proxies from transaction prices without quotes**. The classic example is **Roll (1984)**, which infers an **effective bid-ask spread** from the serial covariance of transaction-price changes. Later work, including **Corwin and Schultz (2012)** and **Ardia, Guidotti, and Kroencke (2024)**, extends or improves spread estimation when quotes are unavailable. **Zhang and Hodges (2012)** further extend transaction-only models to allow trades to occur inside or outside the quoted spread. These methods are real, published, and adoptable—but what they estimate is a **spread/liquidity proxy**, not queue depth or a personal fill probability. citeturn27view4turn27view5turn28view0turn28view1

The literature on **actual fill probabilities** looks very different. **Lo, MacKinlay, and Zhang (2002)** model **limit-order execution times** using survival analysis with actual limit-order data and current market conditions, and they stress that ignoring **censored observations**—orders that do not execute—can materially bias inference. **Maglaras et al. (2022)** frame fill probability as a prediction problem over the evolving **limit order book**, and show that better fill-probability models improve execution decisions. In short: the established fill-probability literature uses **order data plus order-book state**, not just prints. citeturn27view2turn29view2

The strongest recent evidence on what drives maker fills comes from **Albers et al. (2025)**. They show that fill probability is strongly explained by **near-side queue size**, **opposite-side queue size**, and imbalance; in their data, fill probability can be below **30%** when the near-side queue is large and opposite-side queue small, and above **90%** in the opposite configuration. They also show why aggregated data are not enough for exact execution inference over time: to know the true liquidity **ahead** of your order and **behind** it, you really want **L3 order data**, not just aggregated levels. citeturn37view3

That gives a very clear answer to question 3. With **BASIC LTP plus market definition only**, you can plausibly estimate a **transaction-cost band** or a **liquidity proxy** from print dynamics. You cannot, using an established method, reconstruct **available depth** or your own **queue-aware fill probability** with the same status as the published fill-probability literature. The identification problem is too severe: you do not observe side, depth, cancellations, hidden liquidity, or queue position. citeturn27view4turn28view0turn27view2turn29view2turn37view3

If you still want a quantitative layer beyond SUPPORTED / UNSUPPORTED / NO_EVIDENCE, the most defensible externally grounded option is this: use a **transaction-only spread estimator** as a cost proxy, then report a **range** around the hypothetical return, not a personal fill probability. That is, treat the missing book as an execution-cost uncertainty, not as something you can reconstruct exactly from prints. This is an inference from the literature rather than a standard norm stated in one paper, but it is the closest fit to what the literature actually supports. citeturn27view4turn27view5turn28view0turn28view1

## The traded-through test and its likely bias

Your proposed test—"a claimed back at price \(P\) is supported if the market later trades at \(P\) or better before the off"—maps closely onto what execution/backtesting practitioners call a **trade-through fill assumption**. Levant and Oh's futures backtesting study states the rule very plainly: **touching** the limit price is not enough; the best bid-offer must post prices **through** the limit before they credit a fill. That is a recognised conservative simulation convention. citeturn25search0

Why is it conservative? Because in a price-time priority book, if you assume your order is effectively **last in queue** at the advertised price, then the market must consume all earlier liquidity before it reaches you. That logic is standard microstructure: older orders at a price execute before newer ones, so merely seeing the market touch your price does not prove that your order, placed later, would fill. citeturn29view0

However, the literature also shows why the rule is **not sufficient** for a realised-return claim. Fill depends not just on price reaching your level, but on the amount of **liquidity ahead of you**. Albers et al. show that an order is "certain to fill" only when a taker order size exceeds the **liquidity ahead** at the price level, and their fill-probability surface depends heavily on queue sizes. If you do not observe traded volume or queue depth—as in BASIC—you cannot know whether a brief trade at your level was enough to reach *your* order. So a trade-through test with no volume is conservative relative to *touch*, but it still remains an **upper-bound style simulation**, not direct evidence of personal execution. citeturn37view3

On bias, I did **not** find a published betting-exchange paper that analyses your exact survival test by name. But the likely bias is inferable from standard microstructure. On **shortening** markets, the test is conservative, because a resting back order may plausibly have filled at or just before the market moved below your target, even if no later trade occurs at your target or better. On **volatile / mean-reverting** markets, the test can be permissive, because later revisits or trade-throughs may support a hypothetical fill even though your original order may never have reached the front of the queue. That bias direction is an inference from price-time priority plus omitted queue size, not something directly estimated in the literature I found. citeturn25search0turn29view0turn37view3

So the verdict for question 4 is precise: **yes, the underlying idea is recognised as a trade-through-style conservative fill rule in execution backtesting; no, I did not find it as a named or validated estimator in the betting-exchange literature; and yes, its remaining bias is largely driven by omitted queue and size information**. citeturn25search0turn29view0turn37view3

## Betfair-specific mechanics and current UK charges

Several Betfair-specific mechanics materially affect how a BASIC trace should be read. First, Betfair's own rules say bets may be matched using **cross-matching** if that produces a better price for the customer than matching against an opposing bet on the same selection, and that in some circumstances this creates a **small amount of additional revenue** for Betfair because cross-matching must respect the exchange's valid odds increments. Cross-matching therefore means that an observed transaction price need not correspond in a naive one-for-one way to visible same-selection resting interest. citeturn42search0turn42search1

Second, Betfair's stream/API market definition exposes **`crossMatching`**, **`inPlay`**, **`turnInPlayEnabled`**, and **`betDelay`** as explicit state variables. That matters because the execution environment changes as a market approaches the off and enters in-play. Even if your analysis is strictly pre-off, the cut-over into suspension / in-play is part of the microstructure boundary condition, and a one-minute BASIC archive can miss the final high-activity transition. citeturn1view1

Third, Betfair's Exchange rules state that if a market that is **not** supposed to turn in-play is suspended too late, bets placed after the scheduled off can be voided. For markets that do turn in-play, the transition itself is a structural break in mechanics. More generally, any trace-only reading that ignores market state changes around the off risks treating very different execution regimes as though they were one. citeturn1view5

On **current UK charges**, the official Betfair position as of your requested date is no longer the old blanket "UK MBR minus discount" model for ordinary non-Australasian exchange betting. Betfair's terms say that ordinary Exchange commission is charged on **net winnings on a market**, and for customers using **My Betfair Rewards**, the **package choice** determines the commission rate. The public example on Betfair's own charges page is the **Basic package at 2%**. Betfair also states that Betfair Points **do not affect commission rates** for those customers, **except for events based in Australia**. citeturn31view1turn35search1turn31view2

That means your current model of **flat 2% on net winnings** is **correct only conditionally**: it is correct if the UK-resident account is on the **Basic My Betfair Rewards package** and the tennis event is **not Australasian**. It is **not** a universal statement about all UK tennis exchange betting. If the event is Australian-based, or if the account is on a different rewards package, the current charge can differ. Betfair's own support text further says the applicable Market Base Rate should be checked via **emails/web messages** from Betfair, and warns that some older UI pages display **5%** incorrectly. So I cannot responsibly confirm a universal UK tennis "base rate" number from the crawlable public text alone. citeturn35search1turn31view1turn31view2

Finally, there **is** now a charge beyond ordinary commission for a small subset of users. Betfair's **Expert Fee** page says the fee is a weekly top-up, on top of standard commission, applied to a **very small number of the most profitable customers**. Qualification requires, among other things, more than **£25,000** of gross profit in the last **52 active weeks**, positive lifetime gross P&L, and more than **100** lifetime markets bet. The fee is capped at **40%**, and Betfair states that the old **Premium Charge** ended in the week ending **2025-01-05**, with final payments on **2025-01-08**. citeturn33view0turn31view3

## Minimum defensible standard for money claims from BASIC-only data

I did **not** locate a published external standard written specifically for "money claims from Betfair Historical BASIC traces." So the best answer to question 7 has to be an **inference from execution literature**, not a citation to a formally adopted betting-industry protocol. That inference is still strong enough to be useful. The common thread across the literature is that credible execution measurement needs **quotes**, **queue logic**, and **censored non-fills**; transaction-only data can support liquidity-cost proxies, but not personal realised execution. citeturn27view2turn29view0turn29view2turn37view3

On that basis, the **minimum defensible standard** with BASIC only is: **do not state a return as realised**. State it as a **hypothetical return under a specified execution rule**. The rule should be explicitly conservative—your present **SUPPORTED / UNSUPPORTED / NO_EVIDENCE** framework is substantially better than silent LTP settlement because it separates observed later-trade support from unsupported cases and preserves the no-evidence mass instead of hiding it. citeturn25search0turn27view2turn29view0

If you must publish a money number from BASIC, the minimum defensible presentation would be: a hypothetical return, your three-way split, **NO_EVIDENCE retained in the denominator**, a statement that the result is based on **trade-through-style support rather than guaranteed fill**, and an explicit **execution-cost sensitivity band** derived from transaction-only spread proxies or externally sourced spread priors. What you should **not** do is collapse the trace into a single LTP-settled P&L and present it as though it had been earned. citeturn27view4turn27view5turn28view0turn27view2turn29view2

So the practical gate is simple. With **BASIC only**, you can support **forecast-quality claims** and **hypothetical money claims with explicit execution caveats**. You cannot, to an externally defensible execution standard, support a **realised-return claim**. For that, you need at least quote/depth information sufficient to model queue and fill, or real order-level execution records of your own. citeturn29view0turn29view2turn37view3

---

## Assessment (2026-07-28) — this resolves the BLOCKING scope

**The gate, now external rather than self-set.** With BASIC only: forecast-quality claims
are supportable; money claims are supportable **only as hypothetical returns under a stated
execution rule**, with the three-way split shown, NO_EVIDENCE kept in the denominator,
trade-through language used, and an **execution-cost sensitivity band** attached. A
realised-return claim is not supportable from this data, full stop. This is adopted as the
operating standard; TE-0014 already meets everything except the sensitivity band.

**Validation received:** the traded-through test is a recognised trade-through fill
convention (conservative relative to touch-fill; still an upper-bound simulation because
queue depth is unobserved). Its bias directions — conservative on shortening markets,
permissive on volatile ones — match what `fill_evidence.py`'s docstring conjectured.

**New work item (money reporting):** add a transaction-only spread proxy (Roll 1984 family)
computed from each market's own print series, and report money results as a band rather
than a point. Until built, TE-0014's numbers stand with their existing caveats plus an
explicit note that the band is pending.

**Commission correction — action for the founder:** flat 2% is correct **only** for a
UK account on the My Betfair Rewards *Basic* package, and **not** for Australian-based
events (Australian Open!), where the old Market Base Rate system still applies. Two
consequences: (1) our settlement applied 2% to Australian Open matches — a known,
labelled approximation until the correct AU rate for the founder's account is known;
(2) **the founder should check which Rewards package their account is on** — the correct
commission for the site's break-even maths depends on it. Premium Charge ended 2025-01;
the Expert Fee (>£25k gross profit/52wk) is not relevant at this project's scale.

**Impact on claims:** TE-0014's hypothetical framing survives review unchanged; the
sensitivity band and the AU-commission caveat are added as required improvements rather
than retractions.
