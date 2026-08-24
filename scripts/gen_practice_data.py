#!/usr/bin/env python
"""Generate the DevStat synthetic practice dataset (deterministic, seed 42).

Pure numpy+pandas (no heavy stats libs) so it runs cheaply in CI on every
release. Produces data/devstat-practice-data.csv (240 rows, 14 cols) for the
FRCR 'Learn as you do' exercises.
"""
import numpy as np
import pandas as pd

np.random.seed(42)
n = 240

age = np.clip(np.random.normal(58, 15, n), 18, 95).round(0)
sex = np.random.choice(["Male", "Female"], n, p=[0.5, 0.5])
treat = np.random.choice(["Drug A", "Drug B", "Placebo"], n, p=[0.34, 0.33, 0.33])
bmi = np.round(np.clip(np.random.normal(27, 5, n), 15, 45), 1)

bp_effect = {"Drug A": -7, "Drug B": -9, "Placebo": 0}
systolic = np.round(np.clip(
    95 + 0.65 * (age - 50) + np.array([bp_effect[t] for t in treat]) + np.random.normal(0, 8, n),
    85, 190), 0)

chol = np.round(np.clip(np.random.normal(5.2, 1.1, n), 2.5, 9.5), 2)
smoking = np.random.choice(["Yes", "No"], n, p=[0.25, 0.75])

out_p = {"Drug A": 0.72, "Drug B": 0.60, "Placebo": 0.40}
outcome = np.array([np.random.choice(["Improved", "Not improved"], p=[out_p[t], 1 - out_p[t]]) for t in treat])

pain_score = np.clip(np.round(3 + 3.4 * (outcome == "Not improved").astype(int) + np.random.normal(0, 1.7, n)), 0, 10).astype(int)

gold_standard = np.random.choice([0, 1], n, p=[0.55, 0.45]).astype(int)
new_biomarker = np.round(np.clip(0.5 + 1.1 * gold_standard + np.random.normal(0, 0.9, n), 0, 6), 2)

surv_factor = {"Drug A": 1.35, "Drug B": 1.10, "Placebo": 0.75}
surv = np.round(np.clip(np.random.gamma(2.2, 22, n) * np.array([surv_factor[t] for t in treat]), 0.5, 120), 1)
ev_p = [0.45 if t == "Placebo" else (0.28 if t == "Drug B" else 0.22) for t in treat]
event_death = np.array([int(np.random.rand() < p) for p in ev_p])

df = pd.DataFrame({
    "patient_id": range(1, n + 1),
    "age": age, "sex": sex, "bmi": bmi, "treatment": treat,
    "systolic_bp": systolic, "cholesterol": chol, "smoking": smoking,
    "pain_score": pain_score, "outcome": outcome,
    "new_biomarker": new_biomarker, "gold_standard": gold_standard,
    "followup_months": surv, "event_death": event_death,
})

df.to_csv("data/devstat-practice-data.csv", index=False)
print("rows", len(df), "cols", len(df.columns))
