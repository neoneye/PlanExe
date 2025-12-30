from decimal import Decimal
from typing import Dict, List
import re
import pandas as pd
from io import StringIO
from worker_plan_internal.schedule.schedule import Activity, PredecessorInfo, DependencyType, ZERO

# ────────────────────────────────────────────────────────────────────────────────
#  Parsing helpers
# ----------------------------------------------------------------------------
_DEF_RE = re.compile(r"(\w+)(?:\(([SF]{2})([-+]?\d+(?:\.\d+)?)?\))?", re.IGNORECASE)


def parse_dependency(dep_str: str) -> PredecessorInfo:
    dep_str = dep_str.strip()
    m = _DEF_RE.fullmatch(dep_str)
    if not m:
        raise ValueError(f"Invalid dependency format: {dep_str}")
    act_id, dep_type_str, lag_str = m.groups()
    dep_type = DependencyType(dep_type_str.upper()) if dep_type_str else DependencyType.FS
    lag = Decimal(lag_str) if lag_str else ZERO
    return PredecessorInfo(activity_id=act_id, dep_type=dep_type, lag=lag)

# -----------------------------------------------------------------------------
#  Main input parser (semicolon‑separated data)
# -----------------------------------------------------------------------------

def parse_schedule_input_data(data: str) -> List[Activity]:
    """Parse a semicolon‑separated text block into ``Activity`` objects."""
    df = pd.read_csv(
        StringIO(data),
        sep=";",
        comment="#",
        dtype=str,
        keep_default_na=False,
    )

    # normalise column names
    df.columns = df.columns.str.strip().str.lower()
    required = {"activity", "predecessor", "duration"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"Missing columns: {', '.join(missing)}")

    # duplication early exit
    if df["activity"].duplicated(keep=False).any():
        dups = df.loc[df["activity"].duplicated(keep=False), "activity"].tolist()
        raise ValueError(f"Duplicate activity IDs: {', '.join(dups)}")

    activities: Dict[str, Activity] = {}

    for _, row in df.iterrows():
        act_id = row["activity"].strip()
        duration_str = row["duration"].strip()
        if duration_str == "":
            raise ValueError(f"Duration empty for activity {act_id}")
        try:
            duration = Decimal(duration_str)
        except Exception:
            raise ValueError(f"Non‑numeric duration for activity {act_id}: '{duration_str}'")
        if duration <= ZERO:
            raise ValueError(f"Duration must be positive for {act_id}")

        pred_str = row["predecessor"].strip() or "-"
        act = Activity(id=act_id, duration=duration, predecessors_str=pred_str)

        if pred_str != "-":
            for item in pred_str.split(","):
                act.parsed_predecessors.append(parse_dependency(item))

        activities[act_id] = act

    return list(activities.values())
