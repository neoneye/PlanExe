"""
Scheduling of activities.

Uses ``decimal.Decimal`` for fractional durations & lags.
"""
from decimal import Decimal, getcontext
from collections import deque
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Type

# ────────────────────────────────────────────────────────────────────────────────
#  Global decimal configuration  
# ----------------------------------------------------------------------------
# Adjust the precision if your schedules require more than 28 significant digits.
getcontext().prec = 28
ZERO = Decimal("0")

# ────────────────────────────────────────────────────────────────────────────────
#  Dependency types
# ----------------------------------------------------------------------------
class DependencyType(Enum):
    FS = "FS"  # Finish‑to‑Start
    SS = "SS"  # Start‑to‑Start
    FF = "FF"  # Finish‑to‑Finish
    SF = "SF"  # Start‑to‑Finish

# ────────────────────────────────────────────────────────────────────────────────
#  Data classes
# ----------------------------------------------------------------------------
@dataclass
class PredecessorInfo:
    activity_id: str
    dep_type: DependencyType = DependencyType.FS  # default to FS
    lag: Decimal = field(default=ZERO)

@dataclass
class Activity:
    id: str
    duration: Decimal
    predecessors_str: str
    parsed_predecessors: List[PredecessorInfo] = field(default_factory=list)
    successors: List["Activity"] = field(default_factory=list)  # populated later

    # What to display in the Gantt chart
    title: Optional[str] = None

    # The ID of the parent activity
    parent_id: Optional[str] = None

    # CPM dates
    es: Decimal = field(default=ZERO)  # Earliest Start
    ef: Decimal = field(default=ZERO)  # Earliest Finish
    ls: Optional[Decimal] = None       # Latest  Start
    lf: Optional[Decimal] = None       # Latest  Finish
    float: Optional[Decimal] = None    # Total   Float / Slack

    # Equality helpers (activities are unique by ID)
    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Activity):
            return NotImplemented
        return self.id == other.id

    # ────────────────────────────────────────────────────────────────────────
    #  Successor wiring (inverse of predecessor lists)
    # --------------------------------------------------------------------
    @classmethod
    def build_successor_links(cls, activities: Dict[str, "Activity"]) -> None:
        """Populate each activity's *successors* list from predecessor data."""
        # 1) clear any stale links (idempotent)
        for a in activities.values():
            a.successors.clear()

        # 2) build forward links
        for act in activities.values():
            for pred_info in act.parsed_predecessors:
                try:
                    pred = activities[pred_info.activity_id]
                except KeyError:
                    raise ValueError(
                        f"Predecessor '{pred_info.activity_id}' referenced by "
                        f"activity '{act.id}' not found."
                    )
                if act not in pred.successors:  # de‑dupe
                    pred.successors.append(act)

# ────────────────────────────────────────────────────────────────────────────────
#  Topological ordering (Kahn)
# ----------------------------------------------------------------------------

def _topological_order(activities: Dict[str, Activity]) -> List[Activity]:
    """Return activities in topological order or raise on cyclic dependency."""
    in_deg = {aid: len({p.activity_id for p in a.parsed_predecessors})
              for aid, a in activities.items()}
    queue = deque([a for aid, a in activities.items() if in_deg[aid] == 0])
    order: List[Activity] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for succ in node.successors:
            in_deg[succ.id] -= 1
            if in_deg[succ.id] == 0:
                queue.append(succ)

    if len(order) != len(activities):
        cycles = [aid for aid, deg in in_deg.items() if deg > 0]
        raise RuntimeError(f"Cycle detected involving: {', '.join(cycles)}")

    return order

# ────────────────────────────────────────────────────────────────────────────────
#  Post‑schedule validation / warnings
# ----------------------------------------------------------------------------

def _collect_schedule_warnings(acts: Dict[str, Activity]) -> List[str]:
    warnings: List[str] = []

    # 1) temporal‑constraint violations
    for succ in acts.values():
        for info in succ.parsed_predecessors:
            pred = acts[info.activity_id]
            lag  = info.lag

            ok = {
                DependencyType.FS: succ.es >= pred.ef + lag,
                DependencyType.SS: succ.es >= pred.es + lag,
                DependencyType.FF: succ.ef >= pred.ef + lag,
                DependencyType.SF: succ.ef >= pred.es + lag,
            }[info.dep_type]

            if not ok:
                warnings.append(
                    "Constraint violation: "
                    f"{pred.id}->{succ.id} {info.dep_type.value}{lag:+} not satisfied "
                    f"(pred.EF={pred.ef}, succ.ES={succ.es}, succ.EF={succ.ef})"
                )

    # 2) negative float
    for a in acts.values():
        if a.float is not None and a.float < ZERO:
            warnings.append(
                f"Negative total float ({a.float}) on activity {a.id} "
                f"(ES={a.es}, LS={a.ls})."
            )

    return warnings

# ────────────────────────────────────────────────────────────────────────────────
#  CPM calculation (forward & backward pass)
# ----------------------------------------------------------------------------
@dataclass
class ProjectSchedule:
    activities: Dict[str, Activity]
    project_duration: Decimal
    warnings: List[str] = field(default_factory=list)

    # --------------------------------------------------------------------
    #  Factory – compute CPM
    # --------------------------------------------------------------------
    @classmethod
    def create(cls: Type["ProjectSchedule"], activities: List[Activity]) -> "ProjectSchedule":
        acts: Dict[str, Activity] = {a.id: a for a in activities}
        if not acts:
            return cls(activities={}, project_duration=ZERO)

        # build successor links & ordering
        Activity.build_successor_links(acts)
        topo = _topological_order(acts)

        # ── Forward pass ────────────────────────────────────────────
        for node in topo:
            if not node.parsed_predecessors:  # start node
                node.es = ZERO
            else:
                node.es = max(
                    {
                        DependencyType.FS: lambda p, lag: p.ef + lag,
                        DependencyType.SS: lambda p, lag: p.es + lag,
                        DependencyType.FF: lambda p, lag: p.ef + lag - node.duration,
                        DependencyType.SF: lambda p, lag: p.es + lag - node.duration,
                    }[info.dep_type](acts[info.activity_id], info.lag)
                    for info in node.parsed_predecessors
                )
            node.ef = node.es + node.duration

        project_duration = max(a.ef for a in acts.values())

        # ── Backward pass ───────────────────────────────────────────
        for node in reversed(topo):
            if not node.successors:  # end node
                node.lf = project_duration
            else:
                node.lf = min(
                    {
                        DependencyType.FS: lambda s, link: s.ls - link.lag,
                        DependencyType.SS: lambda s, link: s.ls - link.lag + node.duration,
                        DependencyType.FF: lambda s, link: s.lf - link.lag,
                        DependencyType.SF: lambda s, link: s.lf - link.lag + node.duration,
                    }[link.dep_type](s, link)
                    for s in node.successors
                    for link in (p for p in s.parsed_predecessors
                                 if p.activity_id == node.id)
                )            
            node.ls = node.lf - node.duration
            node.float = node.ls - node.es

        warnings = _collect_schedule_warnings(acts)
        return cls(activities=acts, project_duration=project_duration, warnings=warnings)

    # --------------------------------------------------------------------
    #  Helper utilities
    # --------------------------------------------------------------------
    def get_critical_path_activities(self) -> List[Activity]:
        crit = [a for a in self.activities.values() if a.float == ZERO]
        crit.sort(key=lambda x: x.es)
        return crit

    def obtain_critical_path(self) -> List[str]:
        """
        Identifies *a* critical path through the network. There might
        be multiple critical paths in a network; this method returns one.
        """
        crit_nodes = self.get_critical_path_activities()
        if not crit_nodes:
            return []

        final_path: List[str] = []
        processed: Set[str] = set()
        min_es = min(n.es for n in crit_nodes)
        to_process = sorted(
            [n for n in crit_nodes if n.es == min_es], key=lambda x: x.id
        )
        current: Optional[Activity] = to_process[0] if to_process else None

        while current:
            if current.id in processed:
                break
            final_path.append(current.id)
            processed.add(current.id)
            next_on_path: List[Activity] = []

            for succ in current.successors:
                if succ.float != ZERO:
                    continue

                # any link between current → succ may be the driving one
                links = [p for p in succ.parsed_predecessors
                         if p.activity_id == current.id]

                def _drives(link: PredecessorInfo) -> bool:
                    lag = link.lag
                    return {
                        DependencyType.FS: succ.es == current.ef + lag,
                        DependencyType.SS: succ.es == current.es + lag,
                        DependencyType.FF: succ.lf == current.lf + lag,
                        DependencyType.SF: succ.lf == current.es + lag,
                    }[link.dep_type]

                if any(_drives(link) for link in links) and succ.id not in processed:
                    next_on_path.append(succ)

            if next_on_path:
                next_on_path.sort(key=lambda x: (x.es, x.id))
                current = next_on_path[0]
            else:
                current = None
        return final_path
    
    def to_csv(self, *, sep: str = ";", sort_by: str = "id") -> str:
        """
        Human‑readable / test‑friendly serialisation

        Return the full schedule as a deterministic line‑oriented string
        (semicolon‑delimited by default).

        Columns…… Activity ID · Duration · ES · EF · LS · LF · Float
        Sort order… default α‑numeric by *sort_by*.

        Change *sep* if you ever need a different delimiter.
        """

        def _d(val: Decimal | str | None) -> str:
            """
            Convert *val* to the shortest plain‑decimal string.

            * Decimals show no exponent (1E+1 → "10") and no trailing zeros (1.50 → "1.5").
            * None becomes an empty field so the column count stays constant.
            * Non‑Decimal values fall back to ``str`` unchanged.
            """
            if val is None:
                return ""
            if isinstance(val, Decimal):
                return format(val.normalize(), "f")  # fixed‑point, no exponent
            return str(val)

        # ``Activity`` is a dataclass so most attributes are stored in
        # ``Activity.__dataclass_fields__`` rather than ``Activity.__dict__``.
        # Using ``__dict__`` means valid fields like ``duration`` are rejected.
        valid_fields = set(Activity.__dataclass_fields__.keys()) | {"id"}
        if sort_by not in valid_fields:
            raise ValueError(f"Unknown sort key: {sort_by!r}")

        acts = sorted(self.activities.values(), key=lambda a: getattr(a, sort_by))

        header = sep.join(("Activity", "Duration", "ES", "EF", "LS", "LF", "Float"))
        rows = [
            sep.join(
                _d(val)
                for val in (
                    a.id,
                    a.duration,
                    a.es,
                    a.ef,
                    a.ls,
                    a.lf,
                    a.float,
                )
            )
            for a in acts
        ]
        return "\n".join([header, *rows])
    
    def __str__(self) -> str:
        return self.to_csv()
