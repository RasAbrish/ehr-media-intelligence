"""Curated condition dictionary for the extractive summarizer and the eval.

Each concept has a canonical name and surface patterns. Patterns are diagnoses as
written in notes, never inferences: a sodium of 131 is not "hyponatremia" unless a
note says so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Concept:
    canonical: str
    patterns: tuple[str, ...]

    @property
    def regex(self) -> re.Pattern[str]:
        return re.compile("|".join(f"(?:{p})" for p in self.patterns), re.IGNORECASE)


CONCEPTS: tuple[Concept, ...] = (
    Concept("Type 2 diabetes mellitus", (r"\btype 2 diabetes(?: mellitus)?", r"\bT2DM\b")),
    Concept("Type 1 diabetes mellitus", (r"\btype 1 diabetes(?: mellitus)?",)),
    Concept(
        "Diabetic retinopathy",
        (r"\b(?:non)?proliferative diabetic retinopathy", r"\bdiabetic retinopathy"),
    ),
    Concept("Hyperlipidemia", (r"\bhyperlipidemia", r"\bdyslipidemia", r"\bhypercholesterolemia")),
    Concept("Hypertension", (r"\bhypertension", r"\bHTN\b")),
    Concept(
        "Congestive heart failure",
        (
            r"\bcongestive heart failure",
            r"\b(?:systolic|diastolic) heart failure",
            r"\bheart failure",
            r"\bCHF\b",
        ),
    ),
    Concept("Coronary artery disease", (r"\bcoronary artery disease", r"\bCAD\b")),
    Concept("Myocardial infarction", (r"\bmyocardial infarction", r"\bNSTEMI\b", r"\bSTEMI\b")),
    Concept("Atrial fibrillation", (r"\batrial fibrillation", r"\bAFib\b")),
    Concept("Mitral regurgitation", (r"\b(?:mild |moderate |severe )?mitral regurgitation",)),
    Concept("Pulmonary edema", (r"\bpulmonary edema",)),
    Concept("Pleural effusion", (r"\bpleural effusions?",)),
    Concept("Pulmonary embolism", (r"\bpulmonary embol(?:ism|us)",)),
    Concept("Right heart strain", (r"\bright heart strain",)),
    Concept("Deep vein thrombosis", (r"\bdeep vein thrombosis", r"\bDVT\b")),
    Concept(
        "Community-acquired pneumonia",
        (
            r"\bcommunity-acquired pneumonia",
            r"\b(?:right|left) (?:upper|middle|lower) lobe pneumonia",
            r"\bpneumonia",
        ),
    ),
    Concept(
        "COPD exacerbation",
        (
            r"\bacute exacerbation of COPD",
            r"\bCOPD exacerbation",
            r"\bCOPD\b",
            r"\bchronic obstructive pulmonary disease",
        ),
    ),
    Concept("Emphysema", (r"\bemphysema(?:tous changes)?",)),
    Concept("Asthma", (r"\basthma",)),
    Concept(
        "Chronic kidney disease",
        (
            r"\bchronic kidney disease(?: stage \w+)?",
            r"\bCKD(?: stage \w+)?\b",
            r"\bchronic medical renal disease",
        ),
    ),
    Concept("Acute kidney injury", (r"\bacute kidney injury", r"\bAKI\b")),
    Concept("Hyperkalemia", (r"\bhyperkalemia",)),
    Concept("Hypokalemia", (r"\bhypokalemia",)),
    Concept("Hyponatremia", (r"\bhyponatremia",)),
    Concept("Hypothyroidism", (r"\b(?:primary )?hypothyroidism",)),
    Concept("Hyperthyroidism", (r"\bhyperthyroidism",)),
    Concept("Chronic thyroiditis", (r"\bchronic thyroiditis", r"\bthyroiditis")),
    Concept(
        "Breast mass",
        (
            r"\bbreast mass",
            r"\b(?:irregular |spiculated |irregular spiculated )*mass in the (?:left|right) breast",
        ),
    ),
    Concept("Invasive ductal carcinoma", (r"\binvasive ductal carcinoma",)),
    Concept(
        "Acute ischemic stroke",
        (
            r"\bacute ischemic stroke",
            r"\bischemic stroke",
            r"\b(?:acute )?(?:left|right) MCA (?:territory )?(?:stroke|infarct)",
            r"\bstroke",
        ),
    ),
    Concept("Sepsis", (r"\bsepsis", r"\bseptic shock")),
    Concept("Urinary tract infection", (r"\burinary tract infection", r"\bUTI\b", r"\burosepsis")),
    Concept("Anemia", (r"\banemia",)),
    Concept("Obesity", (r"\bobesity",)),
    Concept("Cellulitis", (r"\bcellulitis",)),
    Concept("Pancreatitis", (r"\bpancreatitis",)),
    Concept("Cirrhosis", (r"\bcirrhosis",)),
    Concept("Depression", (r"\bmajor depressive disorder", r"\bdepression")),
    Concept("Osteoarthritis", (r"\bosteoarthritis",)),
    Concept("Gastroesophageal reflux disease", (r"\bgastroesophageal reflux disease", r"\bGERD\b")),
)


Certainty = Literal["affirmed", "uncertain"]

# Cues in the same clause, a few words before the mention (NegEx style, kept small).
_PRE_WINDOW_WORDS = 6
_NEGATION_BEFORE = re.compile(
    r"\b(?:no|not|without|negative for|denies|denied|free of|absence of|resolution of|"
    r"ruled out|rules out)\b(?![^,;]*\b(?:but|however)\b)",
    re.IGNORECASE,
)
_UNCERTAIN_BEFORE = re.compile(
    r"\b(?:suspected|suspicious for|possible|possibly|probable|questionable|query|"
    r"concern(?:ing)? for|rule out|r/o|cannot exclude|cannot rule out|may represent|"
    r"differential(?: diagnosis)? includes|evaluate for|versus|vs\.?)\b|\?",
    re.IGNORECASE,
)
_NEGATION_AFTER = re.compile(
    r"^\s*(?:was|is|has been|have been)?\s*(?:ruled out|excluded|unlikely)\b", re.IGNORECASE
)
_UNCERTAIN_AFTER = re.compile(
    r"^\s*(?:is|was)?\s*(?:suspected|possible|not (?:excluded|ruled out)|"
    r"cannot be (?:excluded|ruled out)|questioned)\b|^\s*\?",
    re.IGNORECASE,
)
# "No change in heart failure" still affirms heart failure.
_PSEUDO_NEGATION = re.compile(
    r"\b(?:no|not) (?:significant |interval |acute )?(?:change|worsening|improvement)\b",
    re.IGNORECASE,
)
_CLAUSE_END = re.compile(r"[.;:\n]")


@dataclass(frozen=True)
class Mention:
    surface: str
    certainty: Certainty


def _certainty(text: str, start: int, end: int) -> Certainty | None:
    """``None`` when the mention is negated, else whether it is affirmed or uncertain."""
    before = _CLAUSE_END.split(text[:start])[-1]
    before = _PSEUDO_NEGATION.sub(" ", " ".join(before.split()[-_PRE_WINDOW_WORDS:]))
    after = _CLAUSE_END.split(text[end:])[0]
    if _NEGATION_BEFORE.search(before) or _NEGATION_AFTER.search(after):
        return None
    if _UNCERTAIN_BEFORE.search(before) or _UNCERTAIN_AFTER.search(after):
        return "uncertain"
    return "affirmed"


def find_concepts(text: str) -> dict[str, Mention]:
    """Concepts written in ``text``: canonical name → the mention as written.

    Negated mentions ("no evidence of pneumonia") are skipped. A concept that is
    affirmed anywhere counts as affirmed; otherwise it is uncertain ("suspected PE").
    """
    found: dict[str, Mention] = {}
    for concept in CONCEPTS:
        for match in concept.regex.finditer(text):
            certainty = _certainty(text, match.start(), match.end())
            if certainty is None:
                continue
            mention = Mention(match.group(0), certainty)
            if concept.canonical not in found or (
                certainty == "affirmed" and found[concept.canonical].certainty == "uncertain"
            ):
                found[concept.canonical] = mention
            if certainty == "affirmed":
                break
    return found


def canonical_for(name: str) -> str | None:
    """Map a diagnosis name (canonical or surface form) to its concept, if any."""
    for concept in CONCEPTS:
        if concept.canonical.lower() == name.lower() or concept.regex.search(name):
            return concept.canonical
    return None
