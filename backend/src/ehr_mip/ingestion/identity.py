"""Identity resolution (docs/05-ALGORITHMS.md section 1.4, ADR-007).

Conservative by design: a wrong merge is clinically dangerous, a missed merge
is only inconvenient.

1. Group records by MRN. Inside a group, records are the same person when DOBs
   agree (or one is missing) and family name plus first given name score at
   least 90 on ``token_sort_ratio``. More than one person on an MRN is a
   conflict: the largest group keeps ``patient:{mrn}``, the others are split
   into ``patient:{mrn}:{dob}`` and every side is flagged.
2. Clusters with different MRNs merge only on exact equality of normalized
   family name, first given name and DOB. The most frequent MRN becomes the
   primary (ties: lowest); the others become secondary identifiers.
3. Records without an MRN attach only to an exact (family, first given, DOB)
   match. Records with no MRN and no name plus DOB are unresolvable.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from rapidfuzz import fuzz

from ehr_mip import ids
from ehr_mip.ingestion.audit import Note

NAME_MATCH_THRESHOLD = 90


@dataclass(frozen=True, slots=True)
class IdentityInput:
    record_id: str
    order: int
    mrn: str | None
    family: str | None
    first_given: str | None
    dob: date | None

    @property
    def name_key(self) -> str | None:
        if self.family is None or self.first_given is None:
            return None
        return f"{self.first_given.lower()} {self.family.lower()}"


@dataclass
class _Group:
    """People-on-one-MRN candidate group, with running DOB and name counts."""

    mrn: str
    members: list[IdentityInput] = field(default_factory=list)
    dob_counts: Counter[date] = field(default_factory=Counter)
    name_counts: Counter[str] = field(default_factory=Counter)

    def add(self, record: IdentityInput) -> None:
        self.members.append(record)
        if record.dob is not None:
            self.dob_counts[record.dob] += 1
        if record.name_key is not None:
            self.name_counts[record.name_key] += 1

    @property
    def dob(self) -> date | None:
        return self.dob_counts.most_common(1)[0][0] if self.dob_counts else None

    @property
    def name_key(self) -> str | None:
        return self.name_counts.most_common(1)[0][0] if self.name_counts else None

    def accepts(self, record: IdentityInput) -> bool:
        group_dob = self.dob
        if record.dob is not None and group_dob is not None and record.dob != group_dob:
            return False
        group_name = self.name_key
        if record.name_key is None or group_name is None:
            return True
        return fuzz.token_sort_ratio(record.name_key, group_name) >= NAME_MATCH_THRESHOLD


@dataclass
class Cluster:
    """One resolved person."""

    patient_key: str
    mrn: str
    secondary_mrns: list[str]
    record_ids: list[str]
    identity_conflict: bool


@dataclass
class IdentityResult:
    assignment: dict[str, str]
    clusters: list[Cluster]
    unresolved: list[str]
    notes: list[tuple[str, Note]]
    merged: int
    conflicts: int


@dataclass
class _Working:
    mrn_counts: Counter[str]
    members: list[IdentityInput]
    conflict: bool
    split_dob: date | None = None
    split: bool = False
    split_qualifier: str | None = None

    @property
    def merge_key(self) -> tuple[str, date] | None:
        names = Counter(m.name_key for m in self.members if m.name_key is not None)
        dobs = Counter(m.dob for m in self.members if m.dob is not None)
        if not names or not dobs:
            return None
        return names.most_common(1)[0][0], dobs.most_common(1)[0][0]

    @property
    def first_order(self) -> int:
        return min(m.order for m in self.members)


def _split_mrn(mrn: str, records: list[IdentityInput]) -> list[_Group]:
    groups: list[_Group] = []
    for record in sorted(records, key=lambda r: r.order):
        target = next((g for g in groups if g.accepts(record)), None)
        if target is None:
            target = _Group(mrn)
            groups.append(target)
        target.add(record)
    return groups


def _ranked_mrns(counts: Counter[str]) -> list[str]:
    """Most frequent first; ties go to the lowest MRN."""
    return [m for m, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def _people_per_mrn(
    by_mrn: dict[str, list[IdentityInput]], notes: list[tuple[str, Note]]
) -> tuple[list[_Working], int]:
    """Step 1: one or more people per MRN. Returns the working clusters and the conflict count."""
    working: list[_Working] = []
    conflicts = 0
    for mrn in sorted(by_mrn, key=lambda m: min(r.order for r in by_mrn[m])):
        groups = _split_mrn(mrn, by_mrn[mrn])
        conflict = len(groups) > 1
        conflicts += conflict
        ranked = sorted(groups, key=lambda g: (-len(g.members), min(m.order for m in g.members)))
        split_dobs: Counter[date | None] = Counter(g.dob for g in ranked[1:])
        for index, group in enumerate(ranked):
            item = _Working(Counter({mrn: len(group.members)}), group.members, conflict)
            if index > 0:
                item.split, item.split_dob = True, group.dob
                if split_dobs[group.dob] > 1:  # twins, or several people without a DOB
                    item.split_qualifier = group.name_key or f"record:{group.members[0].record_id}"
                first = min(group.members, key=lambda m: m.order)
                message = (
                    "Records on this MRN disagree on DOB or name; split into a separate "
                    "patient and flagged for review."
                )
                notes.append(
                    (first.record_id, Note("identity.conflict", "error", message, mrn, None, "mrn"))
                )
            working.append(item)
    return working, conflicts


def _merge_across_mrns(working: list[_Working], notes: list[tuple[str, Note]]) -> list[_Working]:
    """Step 2: union clusters with different MRNs but the same exact (name, DOB)."""
    by_key: dict[tuple[str, date], list[_Working]] = {}
    for item in working:
        key = item.merge_key
        if key is not None:
            by_key.setdefault(key, []).append(item)
    absorbed: set[int] = set()
    for group in by_key.values():
        if len(group) < 2:  # noqa: PLR2004
            continue
        total: Counter[str] = Counter()
        for item in group:
            total.update(item.mrn_counts)
        primary = _ranked_mrns(total)[0]
        keeper = next(
            w for w in sorted(group, key=lambda w: w.first_order) if primary in w.mrn_counts
        )
        for item in group:
            if item is keeper:
                continue
            first = min(item.members, key=lambda m: m.order)
            message = "Same name and DOB under a different MRN; merged as a secondary identifier."
            notes.extend(
                (
                    first.record_id,
                    Note("identity.merge_mrn", "warning", message, mrn, primary, "mrn"),
                )
                for mrn in item.mrn_counts
            )
            keeper.members.extend(item.members)
            keeper.mrn_counts.update(item.mrn_counts)
            keeper.conflict = keeper.conflict or item.conflict
            absorbed.add(id(item))
    return [w for w in working if id(w) not in absorbed]


def _to_cluster(item: _Working) -> Cluster:
    mrns = _ranked_mrns(item.mrn_counts)
    return Cluster(
        patient_key=ids.patient_key(
            mrns[0], item.split_dob, split=item.split, qualifier=item.split_qualifier
        ),
        mrn=mrns[0],
        secondary_mrns=sorted(mrns[1:]),
        record_ids=[m.record_id for m in sorted(item.members, key=lambda m: m.order)],
        identity_conflict=item.conflict,
    )


def resolve_identities(inputs: list[IdentityInput]) -> IdentityResult:
    """Assign every record to a patient, or report it as unresolvable."""
    notes: list[tuple[str, Note]] = []
    by_mrn: dict[str, list[IdentityInput]] = {}
    without_mrn: list[IdentityInput] = []
    unresolved: list[str] = []
    for record in inputs:
        if record.mrn is not None:
            by_mrn.setdefault(record.mrn, []).append(record)
        elif record.name_key is not None and record.dob is not None:
            without_mrn.append(record)
        else:
            unresolved.append(record.record_id)

    working, conflicts = _people_per_mrn(by_mrn, notes)
    survivors = _merge_across_mrns(working, notes)
    merged = len(working) - len(survivors)

    clusters: list[Cluster] = []
    assignment: dict[str, str] = {}
    exact: dict[tuple[str, date], Cluster] = {}
    for item in survivors:
        cluster = _to_cluster(item)
        clusters.append(cluster)
        if item.merge_key is not None:
            exact.setdefault(item.merge_key, cluster)
        assignment.update(dict.fromkeys(cluster.record_ids, cluster.patient_key))

    # Step 3: records without an MRN attach only to an exact (name, DOB) match.
    for record in sorted(without_mrn, key=lambda r: r.order):
        match = exact.get((record.name_key or "", record.dob)) if record.dob else None
        if match is None:
            unresolved.append(record.record_id)
            continue
        assignment[record.record_id] = match.patient_key
        match.record_ids.append(record.record_id)

    return IdentityResult(assignment, clusters, unresolved, notes, merged, conflicts)
