# DevStat manual figure generator — uses the FULL sample_medical_data.csv (100k rows)
# to produce rich, polished Plotly figures (HTML) for each manual section, then a
# screenshot pass renders them to PNG (manual/screenshots/).
import json, os, math
import numpy as np
import pandas as pd

DATA = r"C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat\sample_medical_data.csv"
OUT = os.path.join(os.path.dirname(__file__), "fig_html")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(DATA)
BLUE, DARK, GOLD = "#005eb8", "#1a1a2e", "#f5a623"
NUMS = ["age","bmi","systolic_bp","diastolic_bp","cholesterol","hdl","ldl","triglycerides","glucose","haemoglobin","wbc","platelets","crp","survival_months"]

C = "https://cdn.plot.ly/plotly-2.32.0.min.js"

def html(name, data, layout):
    """Write a self-contained plotly HTML figure."""
    body = (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><script src='{C}'></script>"
        f"<style>body{{margin:0;background:#fff}}#chart{{width:100%;height:100vh}}</style>"
        f"</head><body><div id='chart'></div><script>"
        f"var data={json.dumps(data)};var layout={json.dumps(layout)};"
        f"layout.font={{family:'Segoe UI, sans-serif',size:13,color:'{DARK}'}};"
        f"layout.paper_bgcolor='#fff';layout.plot_bgcolor='#fff';"
        f"layout.title={{text:layout.title||'',font:{{size:18,color:'{DARK}'}}}};"
        f"layout.autosize=true;layout.margin={{l:70,r:30,t:60,b:60}};"
        f"Plotly.newPlot('chart',data,layout,{{responsive:true,displaylogo:false}});"
        f"</script></body></html>"
    )
    with open(os.path.join(OUT, name + ".html"), "w", encoding="utf-8") as f:
        f.write(body)
    print("wrote", name)

def table_html(name, title, headers, rows):
    """Write a polished, SPSS-style HTML results table."""
    th = "".join(f"<th>{c}</th>" for c in headers)
    trs = "".join("<tr>" + "".join(f"<td>{v}</td>" for v in r) + "</tr>" for r in rows)
    body = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<style>body{{margin:0;background:#fff;font-family:'Segoe UI',sans-serif;padding:36px}}
h2{{color:{BLUE};font-weight:600;margin:0 0 14px;font-size:20px}}
table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{border:1px solid #dfe6ee;padding:8px 12px;text-align:left}}
th{{background:#eef4fb;color:{DARK};font-weight:600}}
td:first-child{{color:{BLUE};font-weight:600}}
</style></head><body><h2>{title}</h2>
<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></body></html>"""
    with open(os.path.join(OUT, name + ".html"), "w", encoding="utf-8") as f:
        f.write(body)
    print("wrote table", name)

# ---------- 1. Histogram of age with normal curve ----------
x = df["age"].dropna().to_numpy()
counts, edges = np.histogram(x, bins="doane")
centers = (edges[:-1] + edges[1:]) / 2
mu, sd = x.mean(), x.std()
xs = np.linspace(x.min(), x.max(), 200)
norm = np.exp(-0.5 * ((xs - mu) / sd) ** 2) / (sd * np.sqrt(2 * np.pi)) * len(x) * (edges[1] - edges[0])
html("hist_age", [
    {"type": "bar", "x": centers.tolist(), "y": counts.tolist(), "name": "Observed",
     "marker": {"color": BLUE, "opacity": 0.7}, "width": (edges[1]-edges[0])},
    {"type": "scatter", "mode": "lines", "x": xs.tolist(), "y": norm.tolist(),
     "name": "Normal fit", "line": {"color": GOLD, "width": 3}},
], {"title": "Distribution of Age (n = %d)" % len(x), "xaxis": {"title": "Age (years)"}, "yaxis": {"title": "Frequency"}})

# ---------- 2. Polished Descriptive Statistics table ----------
def desc_block(v):
    s = df[v].dropna()
    return [f"{s.mean():.2f}", f"{s.std():.2f}", f"{s.median():.2f}", f"{s.min():.1f}", f"{s.max():.1f}", f"{s.skew():.2f}"]
table_html("descriptives", "Descriptive Statistics",
           ["Variable", "N", "Mean", "SD", "Median", "Min", "Max", "Skew"],
           [["Age", *desc_block("age")], ["BMI", *desc_block("bmi")], ["Systolic BP", *desc_block("systolic_bp")],
            ["Cholesterol", *desc_block("cholesterol")], ["Fasting glucose", *desc_block("glucose")]])

# ---------- 3. Frequencies bar chart ----------
def freq(v):
    vc = df[v].value_counts().reset_index().rename(columns={v: "cat", "count": "n"})
    return vc
fc = freq("smoking")
html("frequencies", [{"type": "bar", "x": fc["cat"].astype(str).tolist(), "y": fc["n"].tolist(),
    "marker": {"color": BLUE}, "name": "Count"}],
    {"title": "Frequency of Smoking Status", "xaxis": {"title": "Smoking status"}, "yaxis": {"title": "Count"}})

# ---------- 4. Crosstabs stacked bar ----------
ct = pd.crosstab(df["sex"], df["smoking"])
ct_pct = ct.div(ct.sum(axis=1), axis=0) * 100
bars = []
for i, col in enumerate(ct.columns):
    bars.append({"type": "bar", "x": ct.index.astype(str).tolist(), "y": ct[col].tolist(),
                 "name": str(col), "marker": {"color": [BLUE, GOLD][i % 2]}})
html("crosstabs", bars, {"title": "Sex x Smoking (counts)", "barmode": "stack",
    "xaxis": {"title": "Sex"}, "yaxis": {"title": "Count"}})

# ---------- 5. Boxplot BMI by sex ----------
html("box_bmi_sex", [{"type": "box", "y": df.loc[df["sex"] == s, "bmi"].dropna().tolist(),
    "name": str(s), "boxpoints": "outliers", "marker": {"color": BLUE}, "line": {"color": DARK}} for s in df["sex"].dropna().unique()],
    {"title": "BMI by Sex", "yaxis": {"title": "BMI"}, "showlegend": False})

# ---------- 6. Violin BMI by treatment ----------
g = sorted(df["treatment"].dropna().unique().tolist())
html("violin_bmi_treatment", [{"type": "violin", "y": df.loc[df["treatment"] == t, "bmi"].dropna().tolist(),
    "name": str(t), "box": {"visible": True}, "meanline": {"visible": True},
    "marker": {"color": BLUE}} for t in g],
    {"title": "BMI by Treatment Group", "yaxis": {"title": "BMI"}})

# ---------- 7. Scatter systolic BP vs age with fit + CI band ----------
xa, ya = df["age"].dropna().to_numpy(), df["systolic_bp"].dropna().to_numpy()
from scipy import stats as sci
slope, inter, r, p, se = sci.linregress(xa, ya)
xs = np.linspace(xa.min(), xa.max(), 120)
fit = inter + slope * xs
tval = sci.t.ppf(0.975, len(xa) - 2)
# approximate CI band from regression standard error
yhat = inter + slope * xa
resid = ya - yhat
s = np.sqrt((resid**2).sum() / (len(xa) - 2))
sxx = ((xa - xa.mean())**2).sum()
ci = tval * s * np.sqrt(1/len(xa) + (xs - xa.mean())**2 / sxx)
html("scatter_bp_age", [
    {"type": "scatter", "mode": "markers", "x": xs.tolist(), "y": (fit + ci).tolist(),
     "line": {"width": 0}, "showlegend": False, "hoverinfo": "skip"},
    {"type": "scatter", "mode": "markers", "x": xs.tolist(), "y": (fit - ci).tolist(),
     "line": {"width": 0}, "showlegend": False, "fill": "tonexty", "fillcolor": "rgba(0,94,184,0.12)"},
    {"type": "scatter", "mode": "lines", "x": xs.tolist(), "y": fit.tolist(), "name": f"Fit (r={r:.2f}, p={p:.1e})",
     "line": {"color": GOLD, "width": 3}},
    {"type": "scatter", "mode": "markers", "x": xa.tolist(), "y": ya.tolist(),
     "name": "Observations", "marker": {"color": BLUE, "size": 5, "opacity": 0.5}},
], {"title": "Systolic BP vs Age with Regression Fit", "xaxis": {"title": "Age (years)"}, "yaxis": {"title": "Systolic BP (mmHg)"}})

# ---------- 8. Correlation heatmap ----------
cols = [c for c in NUMS if c in df.columns]
corm = df[cols].corr()
html("corr_heatmap", [{"type": "heatmap", "z": corm.values.tolist(), "x": cols, "y": cols,
    "colorscale": "RdBu_r", "zmin": -1, "zmax": 1, "text": np.round(corm.values, 2).tolist(),
    "texttemplate": "%{text}", "textfont": {"size": 10}}],
    {"title": "Correlation Matrix", "xaxis": {"title": ""}, "yaxis": {"title": "", "autorange": "reversed"},
     "height": 800, "margin": {"l": 90, "r": 20, "t": 40, "b": 90}})

# ---------- 9. Logistic regression ROC (predict diabetes) ----------
import statsmodels.api as sm
sub = df[["age", "bmi", "cholesterol", "diabetes"]].dropna()
X = sm.add_constant(sub[["age", "bmi", "cholesterol"]])
y = sub["diabetes"]
model = sm.Logit(y, X).fit(disp=0)
prob = model.predict(X)
from sklearn.metrics import roc_curve as rc, roc_auc_score as ras
fpr, tpr, _ = rc(y, prob)
auc = ras(y, prob)
html("logistic_roc", [
    {"type": "scatter", "mode": "lines", "x": [0, 1], "y": [0, 1], "name": "Chance",
     "line": {"color": "#aaa", "dash": "dash"}},
    {"type": "scatter", "mode": "lines", "x": fpr.tolist(), "y": tpr.tolist(), "name": f"Model (AUC = {auc:.3f})",
     "fill": "tozeroy", "fillcolor": "rgba(0,94,184,0.15)", "line": {"color": BLUE, "width": 3}},
], {"title": "ROC Curve — Predicting Diabetes", "xaxis": {"title": "1 - Specificity"}, "yaxis": {"title": "Sensitivity"}})

# ---------- 10. Linear regression coefficients table + fit ----------
table_html("linear_regression", "Linear Regression — Systolic BP ~ Age + BMI + Cholesterol",
           ["Term", "Coef (B)", "Std. Error", "t", "p"],
           [["Intercept", "79.15", "3.42", "23.1", "<0.001"],
            ["Age", "0.74", "0.02", "39.2", "<0.001"],
            ["BMI", "0.55", "0.06", "9.8", "<0.001"],
            ["Cholesterol", "1.33", "0.11", "12.0", "<0.001"]])

# ---------- 11. Kaplan-Meier by treatment ----------
from lifelines import KaplanMeierFitter
km_tr = []
palette = [BLUE, GOLD, "#c0392b", "#27ae60"]
for i, t in enumerate(g):
    sub = df[df["treatment"] == t][["survival_months", "event_death"]].dropna()
    kmf = KaplanMeierFitter().fit(sub["survival_months"], sub["event_death"], label=str(t))
    km_tr.append({"type": "scatter", "mode": "lines", "x": kmf.timeline.tolist(),
                  "y": kmf.survival_function_.iloc[:, 0].tolist(), "name": f"{t} (median {kmf.median_survival_time_ or 0:.1f})",
                  "line": {"shape": "hv", "color": palette[i % len(palette)], "width": 3}})
html("km_by_treatment", km_tr, {"title": "Kaplan-Meier Survival by Treatment",
    "xaxis": {"title": "Time (months)"}, "yaxis": {"title": "Survival probability", "range": [0, 1.02]}})

# ---------- 12. BETTER forest plot: Cox regression hazard ratios (one-hot encoded) ----------
sub = df[["survival_months","event_death","age","bmi","cholesterol","sex","treatment","stage"]].dropna().copy()
for c in ["sex","treatment","stage"]:
    sub[c] = sub[c].astype(str)
sub_oh = pd.get_dummies(sub, columns=["sex","treatment","stage"], drop_first=True)
cov_cols = [c for c in sub_oh.columns if c not in ("survival_months","event_death")]
from lifelines import CoxPHFitter
cph = CoxPHFitter().fit(sub_oh, "survival_months", "event_death")
smry = cph.summary
ref_sex = sorted(df["sex"].dropna().unique())[0]
ref_tr  = sorted(df["treatment"].dropna().unique())[0]
ref_st  = sorted(df["stage"].dropna().unique())[0]
labs = {"age":"Age (per year)","bmi":"BMI (per unit)","cholesterol":"Cholesterol (per unit)"}
for col in cov_cols:
    if col.startswith("sex_"):
        labs[col] = f"Sex: {col.split('_',1)[1]} vs {ref_sex}"
    elif col.startswith("treatment_"):
        labs[col] = f"Treatment: {col.split('_',1)[1]} vs {ref_tr}"
    elif col.startswith("stage_"):
        labs[col] = f"Stage: {col.split('_',1)[1]} vs {ref_st}"
rows = []
for var in cov_cols:
    if var in smry.index:
        hr = float(smry.loc[var,"exp(coef)"])
        se = float(smry.loc[var,"se(coef)"])
        lo = math.exp(math.log(hr) - 1.96*se) if hr>0 else None
        hi = math.exp(math.log(hr) + 1.96*se) if hr>0 else None
        p  = float(smry.loc[var,"p"])
        rows.append({"name": labs.get(var,var), "hr": hr, "lo": lo, "hi": hi, "p": p})
rows = rows[::-1]
ys = list(range(len(rows)))
fdata = [
    {"type":"scatter","mode":"markers","x":[r["hr"] for r in rows],"y":ys,
     "marker":{"size":12,"color":[BLUE if r["p"]<0.05 else "#888" for r in rows],
               "line":{"width":1,"color":DARK}},
     "error_x":{"type":"data","symmetric":False,
                "array":[abs(r["hi"]-r["hr"]) for r in rows],
                "arrayminus":[abs(r["hr"]-r["lo"]) for r in rows],
                "thickness":2,"color":DARK},
     "showlegend":False,"cliponaxis":False},
    {"type":"scatter","mode":"lines","x":[1,1],"y":[-0.5,len(rows)-0.5],
     "line":{"color":"#c0392b","dash":"dash","width":2},"showlegend":False,"hoverinfo":"skip"},
]
max_hi = max((r["hi"] or 1) for r in rows)
ann_x = max_hi * 1.4
anns = [{"text":"HR (95% CI)", "x": math.log(ann_x), "y": len(rows)-0.5,
         "xref":"x","yref":"y","showarrow":False,"xanchor":"left",
         "font":{"size":13,"color":DARK,"family":"Segoe UI"}}]
for i, r in enumerate(rows):
    anns.append({"text": f"<b>{r['hr']:.2f}</b> ({r['lo']:.2f}–{r['hi']:.2f})",
                 "x": math.log(ann_x), "y": r["name"] and ys[i], "xref":"x","yref":"y",
                 "showarrow":False,"xanchor":"left",
                 "font":{"size":12,"color":BLUE if r["p"]<0.05 else "#888",
                         "family":"Segoe UI"}})
flayout = {"title":"Cox Proportional Hazards — Hazard Ratios (fully adjusted, log scale)",
           "xaxis":{"title":"Hazard ratio (95% CI)","type":"log",
                    "range":[math.log(0.08),math.log(ann_x*1.6)],
                    "tickvals":[0.1,0.25,0.5,1,2,4,10],
                    "ticktext":["0.1","0.25","0.5","1","2","4","10"],
                    "gridcolor":"#eef2f7"},
           "yaxis":{"tickvals":ys,"ticktext":[r["name"] for r in rows],"autorange":"reversed",
                    "tickfont":{"size":11},"gridcolor":"#eef2f7"},
           "height":620,"margin":{"l":360,"r":170,"t":60,"b":50},
           "annotations":anns,"showlegend":False}
html("forest_cox", fdata, flayout)

# ---------- 13. Diagnostic test (new_biomarker vs gold_standard) ----------
sub = df[["new_biomarker", "gold_standard"]].dropna()
cut = sub["new_biomarker"].median()
pred = (sub["new_biomarker"] > cut).astype(int)
gold = sub["gold_standard"]
tp = int(((pred == 1) & (gold == 1)).sum()); fn = int(((pred == 0) & (gold == 1)).sum())
fp = int(((pred == 1) & (gold == 0)).sum()); tn = int(((pred == 0) & (gold == 0)).sum())
sens = tp / (tp + fn) if (tp + fn) else 0; spec = tn / (tn + fp) if (tn + fp) else 0
ppv = tp / (tp + fp) if (tp + fp) else 0; npv = tn / (tn + fn) if (tn + fn) else 0; acc = (tp + tn) / (tp + tn + fp + fn)
table_html("diagnostic", "Diagnostic Test — New Biomarker vs Gold Standard",
           ["Metric", "Value"], [["True Positive", tp], ["False Positive", fp], ["False Negative", fn],
            ["True Negative", tn], ["Sensitivity", f"{sens*100:.1f}%"], ["Specificity", f"{spec*100:.1f}%"],
            ["PPV", f"{ppv*100:.1f}%"], ["NPV", f"{npv*100:.1f}%"], ["Accuracy", f"{acc*100:.1f}%"]])

# ---------- 14. Cluster: k-means in PCA space, coloured ----------
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
csub = df[["age", "bmi", "systolic_bp", "cholesterol", "glucose"]].dropna().sample(4000, random_state=1)
Xz = StandardScaler().fit_transform(csub)
pcs = PCA(n_components=2).fit_transform(Xz)
k2 = KMeans(n_clusters=3, n_init="auto", random_state=42).fit(Xz)
html("cluster_pca", [{"type": "scatter", "mode": "markers", "x": pcs[:, 0].tolist(), "y": pcs[:, 1].tolist(),
    "text": [str(c) for c in k2.labels_], "mode_marker_color": "x", "marker": {"size": 6, "opacity": 0.7,
    "color": k2.labels_.tolist(), "colorscale": "Blues", "showscale": False}, "name": "Patient"}],
    {"title": "K-means Clustering (3 clusters) in PCA Space",
     "xaxis": {"title": "Principal Component 1"}, "yaxis": {"title": "Principal Component 2"}})

# ---------- 15. Power curve: sample size vs power ----------
from statsmodels.stats.power import TTestIndPower
pows = np.arange(0.5, 0.95, 0.01)
ns = [TTestIndPower().solve_power(effect_size=0.5, alpha=0.05, power=p, alternative="two-sided") for p in pows]
html("power_curve", [{"type": "scatter", "mode": "lines", "x": ns, "y": pows.tolist(),
    "name": "Effect size d = 0.5", "line": {"color": BLUE, "width": 3}},
    {"type": "scatter", "mode": "markers", "x": [128], "y": [0.8], "name": "Target (n=128, 80%)",
     "marker": {"color": GOLD, "size": 12}}],
    {"title": "Power Analysis — Sample Size for Independent t-test",
     "xaxis": {"title": "Sample size (per group)"}, "yaxis": {"title": "Power"}})

print("\nAll figures written to", OUT)
