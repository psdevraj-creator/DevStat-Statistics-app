"""Teaching-mode scenario content.

Each scenario is authored as data (a dict with a title, blurb, price, dataset
file, and an ordered list of *steps*). Steps come in a few kinds the frontend
knows how to render:

  - kind: "question"  -> a multiple-choice prompt with a correct answer and
                         per-option explanations + a hint.
  - kind: "info"      -> a short teaching message.
  - kind: "run"       -> actually executes an analysis (endpoint + payload) and
                         explains what it shows.
  - kind: "summary"   -> a takeaway card.

Scenario 1 is free (price_cents = 0). Paid scenarios (price_cents > 0) are
gated by whether the user owns them; the £1 purchase flow is wired later.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _scenario(
    sid: str,
    title: str,
    blurb: str,
    emoji: str,
    price_cents: int,
    dataset_file: str,
    steps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "id": sid,
        "title": title,
        "blurb": blurb,
        "emoji": emoji,
        "price_cents": price_cents,
        "free": price_cents == 0,
        "dataset_file": dataset_file,
        "steps": steps,
    }


SCENARIOS: Dict[str, Dict[str, Any]] = {}


def register(scenario: Dict[str, Any]) -> None:
    SCENARIOS[scenario["id"]] = scenario


# ---------------------------------------------------------------------------
# Scenario 1 — a new antihypertensive (synthetic RCT)
# ---------------------------------------------------------------------------
register(_scenario(
    sid="rct-bp",
    title="A new blood-pressure drug: does it work?",
    blurb="An RCT of a new antihypertensive. Walk the whole path — hypothesis, data, the right test, results, meaning.",
    emoji="🫀",
    price_cents=0,
    dataset_file="scenario1_rct.csv",
    steps=[
        {
            "kind": "info",
            "title": "The study",
            "body": (
                "A pharmaceutical company has developed a new antihypertensive, 'Drug X'. They ran a "
                "randomised controlled trial (RCT): 240 adults with raised blood pressure were randomly "
                "allocated to either Drug X or a placebo for 12 weeks. We've loaded the (synthetic) trial "
                "data for you.\n\nThe question: does Drug X reduce systolic blood pressure (SBP) compared "
                "with placebo?"
            ),
            "emoji": "📋",
        },
        {
            "kind": "question",
            "title": "1. State the hypotheses",
            "prompt": "What is the most appropriate pair of hypotheses for this study?",
            "options": [
                "H0: Drug X and placebo have equal mean SBP at 12 weeks. H1: the means differ.",
                "H0: the mean SBP in the placebo arm is higher. H1: it is lower.",
                "H0: Drug X causes no adverse events. H1: it causes more.",
                "No hypothesis is needed — just describe the data.",
            ],
            "correct": 0,
            "why_correct": (
                "The null (H0) is always the 'no effect' baseline: Drug X and placebo have equal average "
                "SBP. The alternative (H1) is the research claim we want evidence for: the averages differ. "
                "We do NOT assume the direction in the null, and adverse events are a separate safety question."
            ),
            "why_wrong": {
                "1": "This puts the research claim (placebo higher) into the null, which is backwards — the null must be the no-difference baseline.",
                "2": "That's a different (safety) outcome, not the primary efficacy question about SBP.",
                "3": "Hypothesis testing underpins the whole analysis; guessing first is what statistics is for.",
            },
            "hint": "The null is the boring 'no difference' statement; the alternative is what you suspect.",
        },
        {
            "kind": "question",
            "title": "2. Know your outcome variable",
            "prompt": "The primary outcome is systolic blood pressure at 12 weeks (sbp_12wk). What type of variable is it?",
            "options": [
                "Continuous (scale / numeric)",
                "Categorical (nominal)",
                "Binary",
                "Time-to-event",
            ],
            "correct": 0,
            "why_correct": (
                "SBP is measured on a continuous scale and can take any value in a range — it's a continuous "
                "(interval) variable. That decides which family of tests is even eligible."
            ),
            "why_wrong": {
                "1": "sbp_12wk is a number, not categories like 'mild/moderate'.",
                "2": "Not binary — it isn't a yes/no or 0/1 outcome.",
                "3": "Time-to-event applies to when something happens (e.g. an event), not a measured value.",
            },
            "hint": "Look at whether the variable is a measurement (continuous) or a label (category).",
        },
        {
            "kind": "question",
            "title": "3. Know your grouping variable",
            "prompt": "Which variable splits the participants into the two groups being compared?",
            "options": [
                "arm",
                "sex",
                "age",
                "responder",
            ],
            "correct": 0,
            "why_correct": (
                "The trial randomised participants into 'arm' (placebo vs treatment). This is the group "
                "variable that defines who got what — the whole point of randomisation."
            ),
            "why_wrong": {
                "1": "sex is a baseline characteristic, not the randomised allocation — could be used for a subgroup analysis, not the primary comparison.",
                "2": "age is a continuous confounder, not an allocation group.",
                "3": "responder is an OUTCOME based on SBP change — it's the result, not the grouping.",
            },
            "hint": "Which variable says 'which group was a participant randomised to'?",
        },
        {
            "kind": "question",
            "title": "4. Choose the right test",
            "prompt": "We're comparing the MEAN of a continuous outcome (SBP at 12 weeks) between TWO independent groups. What is the primary test?",
            "options": [
                "Independent-samples (unpaired) t-test",
                "Paired t-test",
                "Chi-square test",
                "One-way ANOVA",
            ],
            "correct": 0,
            "why_correct": (
                "Continuous outcome + 2 INDEPENDENT groups = independent-samples t-test (Student's t if "
                "variances are equal, Welch's otherwise). That's the textbook choice for this design."
            ),
            "why_wrong": {
                "1": "A paired t-test is for the SAME participants measured twice (e.g. before/after in one person). Here the two arms are separate people — independent.",
                "2": "Chi-square is for two CATEGORICAL variables; SBP is continuous.",
                "3": "ANOVA compares means across THREE OR MORE groups; with exactly two groups it reduces to the t-test (and would be the choice only if you had 3+ arms).",
            },
            "hint": "Think: independent vs paired (same people?), and continuous vs categorical outcome.",
        },
        {
            "kind": "run",
            "title": "5. Run the t-test",
            "prompt": "Let's actually run it. The test compares mean SBP at 12 weeks (sbp_12wk) between the two arms.",
            "endpoint": "/api/analysis/ttest",
            "payload": {"test_type": "independent", "dependent": ["sbp_12wk"], "group": "arm"},
            "explain": (
                "Look at the mean difference between the arms, the p-value, and the 95% confidence interval. "
                "A small p (usually < 0.05) means the difference we see would be rare if there really were no "
                "difference. The confidence interval tells you how big the effect plausibly is."
            ),
        },
        {
            "kind": "question",
            "title": "6. Check the assumptions",
            "prompt": "A t-test assumes (among other things) that the outcome is roughly normally distributed. What could you do if it is clearly NOT normal or the samples are small?",
            "options": [
                "Use a non-parametric alternative (Mann–Whitney U)",
                "Ignore it — the t-test is always valid",
                "Use a chi-square test instead",
                "Delete the outliers",
            ],
            "correct": 0,
            "why_correct": (
                "If normality (or equal variance) fails, the robust choice is the Mann–Whitney U (rank-sum) "
                "test — the non-parametric equivalent for two independent groups. It compares the whole "
                "distribution, not the mean, and doesn't require normality."
            ),
            "why_wrong": {
                "1": "The t-test is not 'always valid' — it can be biased with skewed data or small samples.",
                "2": "Chi-square handles categorical outcomes; SBP is continuous.",
                "3": "Deleting outliers is a bad idea without justification — I'd rather use a distribution-free test.",
            },
            "hint": "When a parametric test's assumptions are broken, we reach for a non-parametric test.",
        },
        {
            "kind": "info",
            "title": "7. A different outcome, a different test",
            "body": (
                "The trial also recorded a BINARY outcome: 'responder' (yes/no — SBP dropped by 10 mmHg or "
                "more). Because that's categorical, it needs a different family: a chi-square test (or "
                "Fisher's exact for small counts), or logistic regression if you want to adjust for other "
                "factors. The point: the TYPE of outcome drives the choice of test — there is no one-size-fits-all."
            ),
            "emoji": "🧩",
        },
        {
            "kind": "run",
            "title": "8. Compare the binary outcome",
            "prompt": "Now test whether response is associated with the drug — chi-square between 'responder' and 'arm'.",
            "endpoint": "/api/analysis/chisquare",
            "payload": {"row": "responder", "col": "arm"},
            "explain": (
                "A chi-square test tells you whether the two categorical variables are associated. Again look at "
                "the p-value and the direction/strength. For a 2×2 table, an estimate of effect (like an odds "
                "ratio) or the row percentages tells you the size of the association."
            ),
        },
        {
            "kind": "summary",
            "title": "Takeaways",
            "body": (
                "• Start with a clear null and alternative hypothesis.\n"
                "• Name the OUTCOME type (continuous? categorical? time-to-event?) — it drives the test.\n"
                "• Two independent groups + continuous outcome → t-test (Mann–Whitney if assumptions break).\n"
                "• Categorical outcome → chi-square / Fisher's exact / logistic regression.\n"
                "• Don't just chase p < 0.05 — look at the effect size and confidence interval.\n"
                "• Randomisation protects against confounding, so you can compare groups directly.\n\n"
                "You've now walked the whole loop. Well done!"
            ),
            "emoji": "🎉",
        },
    ],
))


# ---------------------------------------------------------------------------
# Scenario 2 — a perioperative novel agent: time-to-event survival analysis
# ---------------------------------------------------------------------------
register(_scenario(
    sid="perioperative-trial",
    title="Does a new agent help before and after surgery?",
    blurb="A de-identified resectable-cancer trial. Master survival analysis: event-free survival, censoring, log-rank, Cox regression, hazard ratios.",
    emoji="🕰️",
    price_cents=100,
    dataset_file="scenario2_perioperative.csv",
    steps=[
        {
            "kind": "info",
            "title": "The trial",
            "body": (
                "Adults with a solid resectable cancer of the digestive tract were randomised 1:1 to receive "
                "either standard perioperative chemotherapy on its own, or the same chemotherapy PLUS a new "
                "biological agent (code-named 'AV-79'), before and after surgery. The trial was double-blind "
                "and ran across several countries.\n\n"
                "The primary question: does adding AV-79 reduce the chance of the cancer coming back (or dying) "
                "before it would have otherwise? We've loaded the synthetic trial data."
            ),
            "emoji": "🏥",
        },
        {
            "kind": "question",
            "title": "1. What kind of endpoint is event-free survival?",
            "prompt": "Event-free survival is recorded as BOTH a time and an event flag (efs_months and efs_event). What type of variable is this?",
            "options": [
                "Time-to-event (survival) data",
                "Continuous data",
                "Binary data",
                "Ordinal data",
            ],
            "correct": 0,
            "why_correct": (
                "Time-to-event data has two parts: a follow-up TIME (how long until either the event happens or "
                "the patient is censored) and an EVENT indicator (0/1). It's the natural way to describe 'time until "
                "the cancer returns or the patient dies.'"
            ),
            "why_wrong": {
                "1": "It's not just a number — the censored patients (event=0) carry a special meaning and can't be treated like a simple measurement.",
                "2": "The event flag is binary, but the full endpoint is the time-and-event pair, which needs survival methods.",
                "3": "Ordinal is for ranked categories like severity; this is a time until an event.",
            },
            "hint": "Think about what efs_event = 0 means for a patient who dropped out or hasn't had the event yet.",
        },
        {
            "kind": "question",
            "title": "2. What does 'censored' mean?",
            "prompt": "A participant is still alive and cancer-free at the end of follow-up (efs_event = 0). How should the analysis treat them?",
            "options": [
                "Include them for the time they were observed, then note they had no event yet",
                "Ignore them entirely",
                "Treat them as if they had died at that moment",
                "Remove them because they are incomplete",
            ],
            "correct": 0,
            "why_correct": (
                "Censored patients contribute follow-up time (they were 'at risk') but no event yet. Excluding them "
                "would bias results and ignore information; treating them as events would be wrong. Survival methods "
                "handle censoring correctly."
            ),
            "why_wrong": {
                "1": "Ignoring them wastes their follow-up time and biases the estimate (asks for trouble).",
                "2": "Calling them an event would wrongly inflate the event rate.",
                "3": "Dropping them is 'listwise deletion' and loses valid information.",
            },
            "hint": "Censoring isn't failure — it's 'no event seen by this time.'",
        },
        {
            "kind": "question",
            "title": "3. Choose the analysis for two survival curves",
            "prompt": "You want to compare event-free survival between the two arms. Which method?",
            "options": [
                "Kaplan–Meier curves + log-rank test",
                "A t-test on the mean months",
                "A chi-square test on event flags only",
                "A scatter plot with a trend line",
            ],
            "correct": 0,
            "why_correct": (
                "Kaplan–Meier estimates the survival (event-free) curve over time, and the log-rank test formally "
                "compares the two curves while correctly using all the censored times. This is the standard for a "
                "time-to-event endpoint."
            ),
            "why_wrong": {
                "1": "A t-test on mean time ignores censoring and is biased, and times are highly skewed.",
                "2": "Chi-square on the event flag discards the 'when' — a patient at 2 months and one at 40 months count the same.",
                "3": "A scatter/trend line doesn't account for censoring or produce a proper comparison.",
            },
            "hint": "The endpoint is time + event. The test must handle both, especially when some patients haven't had the event.",
        },
        {
            "kind": "run",
            "title": "4. Run the Kaplan–Meier analysis",
            "prompt": "Let's estimate event-free survival by arm. Look for the two curves, the log-rank p-value, and the median times.",
            "endpoint": "/api/analysis/kaplan-meier",
            "payload": {"time_col": "efs_months", "status_col": "efs_event", "model_type": "kaplan-meier", "factors": ["arm"]},
            "explain": (
                "The curves start at 100% and step down at each event. The log-rank p-value tells you whether the "
                "two curves differ. The median survival is the time at which the curve crosses 50%. A lower p with "
                "a separate upper curve is evidence AV-79 helps. (Run Cox next to get the size of the effect.)"
            ),
        },
        {
            "kind": "question",
            "title": "5. Reading the log-rank and the curves",
            "prompt": "If the two Kaplan–Meier curves are well separated and the log-rank p is 0.002, what is the correct conclusion?",
            "options": [
                "There is strong evidence the survival curves differ (the agent appears to help)",
                "AV-79 is definitely cured",
                "The difference is tiny and irrelevant",
                "We cannot compare the curves",
            ],
            "correct": 0,
            "why_correct": (
                "A small log-rank p means that observing such separated curves would be very unlikely if the two arms "
                "truly had the same survival. That's evidence the agent is associated with longer event-free survival."
            ),
            "why_wrong": {
                "1": "p < 0.05 is about evidence against no-difference, not proof a drug cures anyone.",
                "2": "Statistical significance is not the same as a large effect — check the median difference / hazard ratio.",
                "3": "The log-rank test is exactly the right tool for comparing curves.",
            },
            "hint": "p measures evidence, not the size of the effect — you'll quantify size next.",
        },
        {
            "kind": "question",
            "title": "6. Exercise: hazard ratio",
            "prompt": "What does a hazard ratio (HR) of 0.74 for AV-79 vs standard mean, when it is below 1?",
            "options": [
                "The event risk at any time is about 26% lower with AV-79",
                "AV-79 increases risk by 74%",
                "Patients in the AV-79 arm lived 74 months longer",
                "There is no meaningful interpretation",
            ],
            "correct": 0,
            "why_correct": (
                "The hazard ratio (<1) means the instantaneous rate of the event (recurrence/death) in the AV-79 arm "
                "is lower — roughly 26% lower (HR 0.74 ≈ 1 − 0.26). It is the relative speed of events over time, not "
                "months saved."
            ),
            "why_wrong": {
                "1": "An HR > 1 is the increased-risk direction; 0.74 is protective.",
                "2": "HR is a relative rate, not an absolute number of months.",
                "3": "HR is a standard, interpretable effect measure in survival analysis.",
            },
            "hint": "HR < 1 = lower rate of the event; 1 − HR is the rough relative reduction.",
        },
        {
            "kind": "run",
            "title": "7. Adjust with a Cox model",
            "prompt": "Now quantify the effect while adjusting for age and stage. This gives a hazard ratio and a confidence interval.",
            "endpoint": "/api/analysis/cox-regression",
            "payload": {"time_col": "efs_months", "status_col": "efs_event", "covariates": ["age", "stage"], "model_type": "cox"},
            "explain": (
                "Cox (proportional hazards) regression models the event rate against the arm and covariates, giving a "
                "hazard ratio per covariate with a 95% confidence interval. Look at the HR for 'arm' and its CI — if the "
                "whole CI is below 1, the effect is statistically significant and estimated to be protective."
            ),
        },
        {
            "kind": "question",
            "title": "8. Check the proportional-hazards assumption",
            "prompt": "The Cox model assumes hazards are proportional over time. A good visual/statistical check is that the log-minus-log survival curves (or the log-rank across time) ...",
            "options": [
                "Do not obviously cross over the follow-up",
                "Diverge exponentially then flatten",
                "Cross steeply several times",
                "Are all below 1",
            ],
            "correct": 0,
            "why_correct": (
                "If the hazard ratio is roughly constant, the log-survival curves stay roughly parallel. If they cross, "
                "the effect isn't proportional and a single HR can mislead."
            ),
            "why_wrong": {
                "1": "That pattern would suggest a changing (non-proportional) effect — exactly what pulls apart a single HR.",
                "2": "Crossing curves typically violate the assumption.",
                "3": "HR < 1 is a good sign but doesn't confirm proportional hazards.",
            },
            "hint": "Parallel curves = constant proportional hazard; crossing curves = not proportional.",
        },
        {
            "kind": "question",
            "title": "9. A different outcome: pathological response",
            "prompt": "A secondary outcome is whether the tumour had a complete or near-complete response after treatment (path_response, yes/no). What kind of test fits?",
            "options": [
                "Chi-square / Fisher's exact test (a binary outcome by arm)",
                "Kaplan–Meier",
                "Paired t-test",
                "Cox regression on the response",
            ],
            "correct": 0,
            "why_correct": (
                "path_response is a binary (yes/no) outcome, so we compare the proportion responding between the two "
                "arms with a chi-square test (or Fisher's exact for small expected counts)."
            ),
            "why_wrong": {
                "1": "Kaplan–Meier is for time-to-event, not a binary response.",
                "2": "A paired test needs repeated measurements in the same person.",
                "3": "Cox models a time-to-event, not a yes/no response.",
            },
            "hint": "Binary outcome + two groups → compare proportions.",
        },
        {
            "kind": "run",
            "title": "10. Run the chi-square on response",
            "prompt": "Compare the pathological response proportion between arms.",
            "endpoint": "/api/analysis/chisquare",
            "payload": {"row": "path_response", "col": "arm"},
            "explain": (
                "Look at the p-value and the proportions/percentages per arm. A chi-square test tells you whether the "
                "response rate is associated with the arm. Consider also reporting a relative risk or odds ratio — a "
                "single p-value doesn't tell you how big the benefit is."
            ),
        },
        {
            "kind": "question",
            "title": "11. Adverse events",
            "prompt": "Adverse events are graded 0–4 (none to life-threatening). How are these best handled?",
            "options": [
                "Summarise as counts/percentages by grade and compare with an appropriate categorical analysis",
                "Average the grades and run a t-test as if it were continuous",
                "Ignore them — only efficacy matters",
                "Treat each grade as a separate independent dataset",
            ],
            "correct": 0,
            "why_correct": (
                "Ordinal safety grades are summarised descriptively (counts and percentages by grade) and compared "
                "with an appropriate test; they are NOT averaged as a continuous number, because the gaps between "
                "grades are not truly equal."
            ),
            "why_wrong": {
                "1": "Averaging ordinal grades as if continuous is statistically questionable.",
                "2": "Safety must be reported, especially when adding a new agent.",
                "3": "Grades belong to one ordinal outcome, not separate datasets.",
            },
            "hint": "Ordinal grades: report the distribution, don't just average them.",
        },
        {
            "kind": "info",
            "title": "12. Advanced: intention-to-treat & multiplicity",
            "body": (
                "• Analyse by intention-to-treat (all randomised patients in their assigned arm) — that's the unbiased "
                "primary analysis in a randomised trial.\n"
                "• A trial tests several endpoints (event-free survival, overall survival, response, safety). Each extra "
                "test increases the chance of a false positive, so pre-specify the primary endpoint and treat secondary "
                "findings as hypothesis-generating.\n"
                "• Always report a confidence interval with an estimate, so clinicians can judge clinical (not just "
                "statistical) significance."
            ),
            "emoji": "🧠",
        },
        {
            "kind": "summary",
            "title": "Takeaways",
            "body": (
                "• Time-to-event data = a time AND an event flag; censoring is information, not loss.\n"
                "• Compare two survival curves with Kaplan–Meier + log-rank; quantify the effect with Cox (hazard ratio).\n"
                "• HR < 1 = protective; read it as a relative rate, not months saved.\n"
                "• Check proportional hazards before trusting a single HR.\n"
                "• Binary outcomes → chi-square / Fisher's exact; report effect size and CI.\n"
                "• Safety (ordinal grades) is summarised, not averaged.\n\n"
                "You've now mastered the survival-analysis loop. Beautifully done!"
            ),
            "emoji": "🎉",
        },
    ],
))


# ---------------------------------------------------------------------------
# Scenario 3 — two radiotherapy techniques: patient-reported outcomes & toxicity
# ---------------------------------------------------------------------------
register(_scenario(
    sid="radiotherapy-trial",
    title="Two ways to give radiotherapy",
    blurb="A de-identified head-and-neck trial. Compare patient-reported quality of life and toxicity — continuous, ordinal and binary outcomes in one study.",
    emoji="🎯",
    price_cents=100,
    dataset_file="scenario3_radiotherapy.csv",
    steps=[
        {
            "kind": "info",
            "title": "The trial",
            "body": (
                "Adults with a head-and-neck cancer needing curatively-intended radiotherapy were randomised to one of "
                "two radiotherapy delivery techniques: the current standard technique or a newer conformal technique "
                "(called 'Technique B'). Both are given with the same general care.\n\n"
                "The idea is that Techniqi B may spare healthy tissue and so improve the patient-reportted swallowing "
                "score (quality of life) at 26 weeks, as well as reducing side-effects, without harming survival. We've "
                "loaded the synthetic data."
            ),
            "emoji": "🎗️",
        },
        {
            "kind": "question",
            "title": "1. The primary outcome",
            "prompt": "The primary outcome is the patient-reported swallowing score at 26 weeks (qol_swallow_26wk, 0–100, higher is better). What is it?",
            "options": [
                "Continuous (scale) outcome",
                "Time-to-event",
                "Ordinal",
                "Count",
            ],
            "correct": 0,
            "why_correct": (
                "A 0–100 score measured on a continuous scale is a continuous (quantitative) outcome, often even "
                "approximating a scale. That's the first big clue for which test family to use."
            ),
            "why_wrong": {
                "1": "It's a score at one timepoint, not a time-to-event.",
                "2": "Ordinal would be rank-ordered categories; a 0–100 score is more fine-grained (though we'll check how normal it is).",
                "3": "Counts are for events you tally; this is a measured score.",
            },
            "hint": "Is the value a measurement on a numeric scale, or a ranked category?",
        },
        {
            "kind": "question",
            "title": "2. Choose the primary comparison",
            "prompt": "Comparing a continuous score between TWO independent groups (Technique A vs B). Which primary test?",
            "options": [
                "Independent-samples t-test (or Mann–Whitney if assumptions break)",
                "Paired t-test",
                "One-sample t-test against a fixed value",
                "Chi-square",
            ],
            "correct": 0,
            "why_correct": (
                "Continuous outcome + two independent groups = independent-samples t-test. If the score is clearly "
                "non-normal (common with quality-of-life data) we fall back on the Mann–Whitney U test."
            ),
            "why_wrong": {
                "1": "Not paired — different patients are in each arm.",
                "2": "One-sample tests against a fixed value, not between two groups.",
                "3": "Chi-square needs categorical variables.",
            },
            "hint": "Independent groups + continuous outcome → t-test, with a non-parametric plan B.",
        },
        {
            "kind": "run",
            "title": "3. Run the comparison",
            "prompt": "Compare mean swallowing score at 26 weeks between the two techniques.",
            "endpoint": "/api/analysis/ttest",
            "payload": {"test_type": "independent", "dependent": ["qol_swallow_26wk"], "group": "technique"},
            "explain": (
                "Look at the two group means and the p-value. If the score is skewed, the t-test may be unreliable — "
                "we'll check normality next. The t-test tells you whether the mean difference is statistically "
                "unlikely under the null of no difference."
            ),
        },
        {
            "kind": "question",
            "title": "4. Check for normality",
            "prompt": "Quality-of-life scores are often skewed. If the Shapiro–Wilk normality test gives a very small p-value (say p < 0.001), what should you do?",
            "options": [
                "Use the Mann–Whitney U (non-parametric) test instead",
                "Proceed with the t-test regardless — it's always fine",
                "Square the data to force normality",
                "Delete the outliers",
            ],
            "correct": 0,
            "why_correct": (
                "If the data are clearly non-normal, the distribution-free Mann–Whitney U test is the safer choice. It "
                "compares the distributions/rank ordering, not the mean, and doesn't require normality."
            ),
            "why_wrong": {
                "1": "The t-test is not robust to severe skew with small/moderate samples.",
                "2": "Data transformations should be pre-specified and principled, not just to make a test pass.",
                "3": "Deleting outliers distorts the data unless there's a defensible clinical reason.",
            },
            "hint": "Parametric assumption broken → non-parametric test.",
        },
        {
            "kind": "run",
            "title": "5. Run the non-parametric alternative",
            "prompt": "Compare the swallowing score distributions between techniques with the Mann–Whitney U test.",
            "endpoint": "/api/analysis/np-mannwhitney",
            "payload": {"dependent": "qol_swallow_26wk", "group": "technique"},
            "explain": (
                "The Mann–Whitney test compares the rank distributions of the two groups and gives a p-value. It's the "
                "non-parametric counterpart to the independent t-test. Note: it compares distributions, and the "
                "report could give a median and interquartile range rather than means."
            ),
        },
        {
            "kind": "question",
            "title": "6. Statistically significant ≠ clinically meaningful",
            "prompt": "The p is 0.03 (Technique B better), but the difference is about 5 points on a 0–100 scale and the study's meaningful-threshold (MCID) is 10 points. What's the right read?",
            "options": [
                "Statistically significant, but possibly NOT clinically meaningful — report the effect and CI",
                "It's definitely a big win because p < 0.05",
                "The result should be ignored entirely",
                "The MCID is irrelevant",
            ],
            "correct": 0,
            "why_correct": (
                "p < 0.05 only says the difference is unlikely to be due to chance. If the effect is smaller than what "
                "patients would actually notice (the MCID), we should be cautious about claiming a clinically important "
                "benefit. Report the difference and its confidence interval, and let the reader judge."
            ),
            "why_wrong": {
                "1": "p < 0.05 says nothing about whether the effect is LARGE — a tiny difference can be significant with a big sample.",
                "2": "The result is real evidence of a (small) difference; it shouldn't be ignored, but its clinical relevance is limited.",
                "3": "The MCID is exactly the yardstick that matters for whether a small difference is worth it.",
            },
            "hint": "Ask: 'is the size of the difference enough to matter to a patient?' That's the MCID.",
        },
        {
            "kind": "question",
            "title": "7. Ordinal toxicity",
            "prompt": "Toxicity is graded 0–4 (none→life-threatening) — an ORDINAL outcome. Which analysis is appropriate?",
            "options": [
                "Summarise counts by grade and compare with an appropriate categorical approach (e.g. chi-square / a trend test)",
                "Average the grades and run a t-test",
                "Fit a survival curve",
                "Ignore it because it's too subjective",
            ],
            "correct": 0,
            "why_correct": (
                "Ordinal grades are rank categories. Report the distribution across grades and use categorical "
                "comparison methods, possibly a test for trend across ordered categories. Averaging grades as a "
                "continuous number is not appropriate."
            ),
            "why_wrong": {
                "1": "Averaging ordinal grades loses the categorical nature.",
                "2": "A survival curve is for time-to-event, not toxicity grade.",
                "3": "Safety outcomes are important — they should be analysed and reported.",
            },
            "hint": "Ordinal: report the spread of grades, compare categorically.",
        },
        {
            "kind": "run",
            "title": "8. Compare a binary side-effect",
            "prompt": "Feeding-tube dependence is a binary (yes/no) outcome. Test whether it is associated with the technique.",
            "endpoint": "/api/analysis/chisquare",
            "payload": {"row": "feeding_tube", "col": "technique"},
            "explain": (
                "A chi-square test on a 2×2 table tells you whether the proportion needing a feeding tube differs by "
                "technique. Look at the p-value and the group percentages — and consider an odds ratio / relative "
                "risk to size the difference rather than p alone."
            ),
        },
        {
            "kind": "question",
            "title": "9. Survival as a secondary",
            "prompt": "The trial also recorded overall survival (survival_months, survival_event). How should this be analysed?",
            "options": [
                "Kaplan–Meier + log-rank (or Cox if you wish to adjust)",
                "A t-test on survival_months",
                "Chi-square on survival_event only",
                "Correlation",
            ],
            "correct": 0,
            "why_correct": (
                "Overall survival is time-to-event: use Kaplan–Meier curves and the log-rank test to compare, or Cox "
                "regression to adjust. It's the same survival toolkit you used in the other lesson."
            ),
            "why_wrong": {
                "1": "t-test on time ignores censoring and the skewed distribution.",
                "2": "Chi-square on the event flag alone loses the 'when' information.",
                "3": "Correlation isn't a comparison of survival between groups.",
            },
            "hint": "Time + event flag → survival analysis, again.",
        },
        {
            "kind": "info",
            "title": "10. Longitudinal & multiple testing",
            "body": (
                "Quality of life is often measured at several timepoints (baseline, 6, 12, 26, 52 weeks). Comparing each "
                "timepoint with a separate test inflates the chance of a false positive. Better approaches include a "
                "repeated-measures / mixed (multilevel) model, or analysis of a single primary timepoint with the "
                "others as secondary. Also consider adjusting for baseline score.\n\n"
                "In this lesson we focus on the single pre-specified 26-week primary score — which is exactly what a "
                "well-designed trial would do."
            ),
            "emoji": "📈",
        },
        {
            "kind": "summary",
            "title": "Takeaways",
            "body": (
                "• Name the outcome type first: continuous, ordinal, binary or time-to-event.\n"
                "• Continuous + two independent groups → t-test; use Mann–Whitney if not normal.\n"
                "• Statistical significance ≠ clinical meaning — use an effect size, a CI, and an MCID.\n"
                "• Ordinal (toxicity) outcomes are summarised by grade, not averaged.\n"
                "• Binary outcomes → chi-square / logistic; report the effect size.\n"
                "• Survival (if present) still needs Kaplan–Meier / Cox.\n"
                "• Many endpoints → pre-specify the primary and watch for multiplicity.\n\n"
                "You've now read a head-and-neck trial from every angle. Outstanding!"
            ),
            "emoji": "🎉",
        },
    ],
))


def list_scenarios() -> List[Dict[str, Any]]:
    """Scenario metadata for the list view (excluding the full step content)."""
    out = []
    for s in SCENARIOS.values():
        out.append({
            "id": s["id"], "title": s["title"], "blurb": s["blurb"],
            "emoji": s["emoji"], "price_cents": s["price_cents"], "free": s["free"],
            "steps": len(s["steps"]),
        })
    return out


def get_scenario(sid: str) -> Optional[Dict[str, Any]]:
    return SCENARIOS.get(sid)
