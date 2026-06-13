from typing import Optional, Any, Dict, List, Literal, Union, Annotated
from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    dtype: str
    unique_count: int
    missing_count: int
    missing_pct: float
    is_numeric: bool
    is_categorical: bool
    labels: Optional[Dict[str, str]] = None
    # Extended SPSS-style metadata
    type: str = "numeric"       # numeric, string, date, comma, dot, dollar, percent
    width: int = 8
    decimals: int = 2
    label: str = ""
    value_labels: Dict[str, str] = {}
    missing_values: List[Any] = []
    columns: int = 10
    align: str = "right"        # left, center, right
    measure: str = "scale"      # scale, ordinal, nominal
    role: str = "input"         # input, target, both, none, partition, split


class DatasetInfo(BaseModel):
    name: str
    rows: int
    cols: int
    columns: List[ColumnInfo]
    preview: List[Dict[str, Any]]


class CellEdit(BaseModel):
    row: int
    col: str
    value: Any
    old_value: Optional[Any] = None


class VariableMetaUpdate(BaseModel):
    name: str
    updates: Dict[str, Any]


class ValueLabelSet(BaseModel):
    column: str
    value_labels: Dict[str, str]


class MissingValueSet(BaseModel):
    column: str
    missing_values: List[Any]


class AddColumnRequest(BaseModel):
    name: str
    dtype: str = "numeric"       # numeric, string, date
    default_value: Any = None


class ComputeRequest(BaseModel):
    name: str
    expression: str

class RecodeRule(BaseModel):
    from_val: Optional[Any] = None
    to_val: Optional[Any] = None
    new_value: Any = None

class RecodeRequest(BaseModel):
    column: str
    into_new: str = ""         # empty = recode into same column
    rules: List[RecodeRule] = []  # [{from_val, to_val, new_value}, ...]
    mappings: Dict[str, Any] = {}  # simple old->new value mapping

class UndoRedoResponse(BaseModel):
    success: bool
    description: Optional[str] = None
    undo_count: int = 0
    redo_count: int = 0


class AnalysisRequest(BaseModel):
    columns: List[str]
    group_col: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class TestRequest(BaseModel):
    test_type: str
    dependent: List[str]
    group: Optional[str] = None
    paired: bool = False
    options: Optional[Dict[str, Any]] = None


class RegressionRequest(BaseModel):
    dependent: str
    independents: List[str]
    method: str = "enter"  # enter, stepwise, forward, backward
    family: str = "linear"  # linear, logistic


class SurvivalRequest(BaseModel):
    time_col: str
    status_col: str
    event_code: int = 1
    factors: Optional[List[str]] = None
    covariates: Optional[List[str]] = None
    model_type: str = "kaplan-meier"  # kaplan-meier, cox


class DiagnosticRequest(BaseModel):
    test_col: str
    gold_col: str
    positive_code: Any = 1


# ---------------------------------------------------------------------------
# Response Models — explicit contracts for frontend consumption
# ---------------------------------------------------------------------------


class FrequencyRow(BaseModel):
    value: Any
    count: int
    percent: float
    cumulative_percent: float


class FrequencyResponse(BaseModel):
    chart_type: Literal["frequencies"] = "frequencies"
    column: str
    n: int
    missing: int
    table: List[FrequencyRow]


class CrosstabResponse(BaseModel):
    chart_type: Literal["crosstab"] = "crosstab"
    row: str
    col: str
    chi_square: Optional[Dict[str, Any]] = None
    cramers_v: Optional[Dict[str, Any]] = None
    table: List[Dict[str, Any]] = []
    interpretation: Optional[str] = None


class KMCurvePoint(BaseModel):
    group: str
    x: List[float]
    y: List[float]
    ci_lower: Optional[List[float]] = None
    ci_upper: Optional[List[float]] = None


class MedianSurvivalEntry(BaseModel):
    group: str
    median: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None


class SummaryTableRow(BaseModel):
    timeline: Optional[float] = None
    at_risk: Optional[int] = None
    events: Optional[int] = None
    censored: Optional[int] = None
    survival_prob: Optional[float] = None
    se: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    group: Optional[str] = None


class LogRankTest(BaseModel):
    statistic: Optional[float] = None
    p: Optional[float] = None
    p_label: Optional[Dict[str, Any]] = None


class KaplanMeierData(BaseModel):
    """Full Kaplan-Meier result shape (success branch)."""
    time_col: str
    status_col: str
    event_code: int
    group_col: Optional[str] = None
    n_total: int
    n_events: int
    n_censored: int
    summary_table: List[SummaryTableRow]
    median_survival: List[MedianSurvivalEntry]
    km_curve: List[KMCurvePoint]
    log_rank_test: Optional[LogRankTest] = None
    pairwise_comparisons: Optional[List[Dict[str, Any]]] = None
    interpretation: str


class KaplanMeierSuccess(BaseModel):
    """Validated Kaplan-Meier success response."""
    status: Literal["success"] = "success"
    data: KaplanMeierData


class KaplanMeierError(BaseModel):
    """Kaplan-Meier error response."""
    status: Literal["error"] = "error"
    error: str


# Discriminated union — FastAPI validates against the correct branch
KaplanMeierResponse = Annotated[
    Union[KaplanMeierSuccess, KaplanMeierError],
    Field(discriminator="status"),
]


class CoxCoefficient(BaseModel):
    name: str
    coef: float
    hr: float
    hr_ci_lower: float
    hr_ci_upper: float
    se: float
    z: float
    p: float
    p_label: Optional[Dict[str, Any]] = None


class CoxModelSummary(BaseModel):
    concordance_index: float
    log_likelihood: float
    aic: float
    n: int
    n_events: int
    n_covariates: int


class CoxData(BaseModel):
    """Full Cox regression result shape (success branch)."""
    coefficients: List[CoxCoefficient]
    model_summary: CoxModelSummary
    proportional_hazards_test: Dict[str, Any] = {}
    interpretation: str


class CoxSuccess(BaseModel):
    """Validated Cox regression success response."""
    status: Literal["success"] = "success"
    data: CoxData


class CoxError(BaseModel):
    """Cox regression error response."""
    status: Literal["error"] = "error"
    error: str


# Discriminated union
CoxResponse = Annotated[
    Union[CoxSuccess, CoxError],
    Field(discriminator="status"),
]


class ChartSeries(BaseModel):
    group: Optional[str] = None
    label: Optional[str] = None
    categories: Optional[List[str]] = None
    values: Optional[List[float]] = None
    errors: Optional[List[float]] = None
    bins: Optional[List[float]] = None
    counts: Optional[List[int]] = None
    x: Optional[List[float]] = None
    y: Optional[List[float]] = None


class ChartResponse(BaseModel):
    chart_type: str
    column: Optional[str] = None
    group_col: Optional[str] = None
    series: List[ChartSeries] = []
    error: Optional[str] = None


class SurvivalPrepResponse(BaseModel):
    status: str
    rows: int
    n_events: int
    n_censored: int
    mean_time: Optional[float] = None
    new_time_col: str
    new_status_col: str
    unit: str
    diagnostics: Dict[str, Any] = {}


class CategoricalSummary(BaseModel):
    value: str
    count: int
    percent: float
    cumulative_percent: float


# ── Transform models (SPSS Transform menu) ─────────────────────────────────


class RankRequest(BaseModel):
    variables: List[str]
    rank_type: str = "rank"  # rank, rintile, ntile, savage, fractional
    ntiles: int = 4
    descending: bool = False
    group_var: Optional[str] = None
    suffix: str = "_rank"


class CountRequest(BaseModel):
    variables: List[str]
    values: List[Any]
    target: str = "count"
    group_var: Optional[str] = None


class SelectIfRequest(BaseModel):
    expression: str
    mode: str = "filter"  # filter, delete


class SortRequest(BaseModel):
    keys: List[Dict[str, str]]  # [{"column": "age", "order": "asc"}, ...]


class SplitFileRequest(BaseModel):
    group_var: Optional[str] = None
    state: str = "off"  # off, on, organize


class WeightRequest(BaseModel):
    weight_var: Optional[str] = None
    state: str = "off"  # off, on


class AggregateRequest(BaseModel):
    group_var: str
    aggregates: List[Dict[str, str]]  # [{"variable": "age", "function": "mean"}, ...]
    suffix: str = "_agg"
