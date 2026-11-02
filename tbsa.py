"""Burn surface-area (%TBSA) calculation using the Lund & Browder chart.

Lund & Browder is the age-adjusted refinement of the Rule of Nines used in burn
units. Each body region below is one half (front or back) of the chart's
entries, so a fully burned region contributes exactly its listed percentage.

The LLM never does this arithmetic; it only reports which regions are burned,
what fraction of each region, and how deep. Everything numeric happens here.
"""

from dataclasses import dataclass, field
from enum import Enum


class AgeGroup(str, Enum):
    UNDER_1 = "under_1"
    AGE_1_4 = "1_4"
    AGE_5_9 = "5_9"
    AGE_10_14 = "10_14"
    AGE_15_17 = "15_17"
    ADULT = "adult"


# Age-dependent Lund & Browder values: A = half of head, B = half of one thigh,
# C = half of one lower leg. Columns: 0, 1, 5, 10, 15 years, adult.
_LB_AGE_VALUES = {
    AgeGroup.UNDER_1: (9.5, 2.75, 2.5),
    AgeGroup.AGE_1_4: (8.5, 3.25, 2.5),
    AgeGroup.AGE_5_9: (6.5, 4.0, 2.75),
    AgeGroup.AGE_10_14: (5.5, 4.25, 3.0),
    AgeGroup.AGE_15_17: (4.5, 4.5, 3.25),
    AgeGroup.ADULT: (3.5, 4.75, 3.5),
}


class Region(str, Enum):
    HEAD_FRONT = "head_front"  # face
    HEAD_BACK = "head_back"
    NECK_FRONT = "neck_front"
    NECK_BACK = "neck_back"
    CHEST_ABDOMEN = "chest_abdomen"
    BACK = "back"
    LEFT_BUTTOCK = "left_buttock"
    RIGHT_BUTTOCK = "right_buttock"
    GENITALIA = "genitalia"
    LEFT_UPPER_ARM_FRONT = "left_upper_arm_front"
    LEFT_UPPER_ARM_BACK = "left_upper_arm_back"
    RIGHT_UPPER_ARM_FRONT = "right_upper_arm_front"
    RIGHT_UPPER_ARM_BACK = "right_upper_arm_back"
    LEFT_FOREARM_FRONT = "left_forearm_front"
    LEFT_FOREARM_BACK = "left_forearm_back"
    RIGHT_FOREARM_FRONT = "right_forearm_front"
    RIGHT_FOREARM_BACK = "right_forearm_back"
    LEFT_HAND_PALM = "left_hand_palm"
    LEFT_HAND_BACK = "left_hand_back"
    RIGHT_HAND_PALM = "right_hand_palm"
    RIGHT_HAND_BACK = "right_hand_back"
    LEFT_THIGH_FRONT = "left_thigh_front"
    LEFT_THIGH_BACK = "left_thigh_back"
    RIGHT_THIGH_FRONT = "right_thigh_front"
    RIGHT_THIGH_BACK = "right_thigh_back"
    LEFT_LOWER_LEG_FRONT = "left_lower_leg_front"
    LEFT_LOWER_LEG_BACK = "left_lower_leg_back"
    RIGHT_LOWER_LEG_FRONT = "right_lower_leg_front"
    RIGHT_LOWER_LEG_BACK = "right_lower_leg_back"
    LEFT_FOOT_TOP = "left_foot_top"
    LEFT_FOOT_SOLE = "left_foot_sole"
    RIGHT_FOOT_TOP = "right_foot_top"
    RIGHT_FOOT_SOLE = "right_foot_sole"


# Fixed (age-independent) values; "A", "B", "C" are resolved per age group.
_REGION_VALUES: dict[Region, float | str] = {
    Region.HEAD_FRONT: "A",
    Region.HEAD_BACK: "A",
    Region.NECK_FRONT: 1.0,
    Region.NECK_BACK: 1.0,
    Region.CHEST_ABDOMEN: 13.0,
    Region.BACK: 13.0,
    Region.LEFT_BUTTOCK: 2.5,
    Region.RIGHT_BUTTOCK: 2.5,
    Region.GENITALIA: 1.0,
    Region.LEFT_UPPER_ARM_FRONT: 2.0,
    Region.LEFT_UPPER_ARM_BACK: 2.0,
    Region.RIGHT_UPPER_ARM_FRONT: 2.0,
    Region.RIGHT_UPPER_ARM_BACK: 2.0,
    Region.LEFT_FOREARM_FRONT: 1.5,
    Region.LEFT_FOREARM_BACK: 1.5,
    Region.RIGHT_FOREARM_FRONT: 1.5,
    Region.RIGHT_FOREARM_BACK: 1.5,
    Region.LEFT_HAND_PALM: 1.25,
    Region.LEFT_HAND_BACK: 1.25,
    Region.RIGHT_HAND_PALM: 1.25,
    Region.RIGHT_HAND_BACK: 1.25,
    Region.LEFT_THIGH_FRONT: "B",
    Region.LEFT_THIGH_BACK: "B",
    Region.RIGHT_THIGH_FRONT: "B",
    Region.RIGHT_THIGH_BACK: "B",
    Region.LEFT_LOWER_LEG_FRONT: "C",
    Region.LEFT_LOWER_LEG_BACK: "C",
    Region.RIGHT_LOWER_LEG_FRONT: "C",
    Region.RIGHT_LOWER_LEG_BACK: "C",
    Region.LEFT_FOOT_TOP: 1.75,
    Region.LEFT_FOOT_SOLE: 1.75,
    Region.RIGHT_FOOT_TOP: 1.75,
    Region.RIGHT_FOOT_SOLE: 1.75,
}

# Burns here need medical review regardless of size (ABA / NHS guidance).
SPECIAL_AREAS = {
    Region.HEAD_FRONT,
    Region.GENITALIA,
    Region.LEFT_HAND_PALM, Region.LEFT_HAND_BACK,
    Region.RIGHT_HAND_PALM, Region.RIGHT_HAND_BACK,
    Region.LEFT_FOOT_TOP, Region.LEFT_FOOT_SOLE,
    Region.RIGHT_FOOT_TOP, Region.RIGHT_FOOT_SOLE,
}

CHILD_GROUPS = {AgeGroup.UNDER_1, AgeGroup.AGE_1_4, AgeGroup.AGE_5_9, AgeGroup.AGE_10_14}


class Depth(str, Enum):
    SUPERFICIAL = "superficial"  # 1st degree: red, no blisters
    SUPERFICIAL_PARTIAL = "superficial_partial"  # 2nd degree: blisters, moist, painful
    DEEP_PARTIAL = "deep_partial"  # 2nd degree deep: blotchy, less painful
    FULL_THICKNESS = "full_thickness"  # 3rd degree: white/leathery/charred
    UNCLEAR = "unclear"


DEPTH_ORDER = [Depth.SUPERFICIAL, Depth.UNCLEAR, Depth.SUPERFICIAL_PARTIAL,
               Depth.DEEP_PARTIAL, Depth.FULL_THICKNESS]

def region_percent(region: Region, age: AgeGroup) -> float:
    value = _REGION_VALUES[region]
    if isinstance(value, float):
        return value
    a, b, c = _LB_AGE_VALUES[age]
    return {"A": a, "B": b, "C": c}[value]


@dataclass
class RegionBurn:
    region: Region
    fraction: float  # 0..1 of that region that is burned
    depth: Depth


@dataclass
class BurnCase:
    """Burns accumulated across one or more photos of the same patient."""

    burns: dict[Region, RegionBurn] = field(default_factory=dict)
    age: AgeGroup | None = None
    circumferential: bool = False

    def add(self, burn: RegionBurn) -> None:
        fraction = min(max(burn.fraction, 0.0), 1.0)
        existing = self.burns.get(burn.region)
        if existing is None:
            self.burns[burn.region] = RegionBurn(burn.region, fraction, burn.depth)
            return
        # Same region seen again: keep the larger extent and the deeper burn.
        existing.fraction = max(existing.fraction, fraction)
        if DEPTH_ORDER.index(burn.depth) > DEPTH_ORDER.index(existing.depth):
            existing.depth = burn.depth


@dataclass
class Assessment:
    tbsa: float  # partial + full thickness (and unclear), what doctors count
    superficial_only: float  # 1st-degree area, excluded from TBSA by convention
    rows: list[tuple[RegionBurn, float]]  # (burn, % contributed)
    level: str  # "emergency" | "hospital" | "home"
    reasons: list[tuple[str, dict]]  # (i18n key suffix, format params)


def assess(case: BurnCase) -> Assessment:
    if case.age is None:
        raise ValueError("age group required")

    tbsa = 0.0
    superficial = 0.0
    rows = []
    for burn in case.burns.values():
        pct = region_percent(burn.region, case.age) * burn.fraction
        rows.append((burn, pct))
        if burn.depth == Depth.SUPERFICIAL:
            superficial += pct
        else:
            tbsa += pct  # unclear depth is counted, to err on the safe side

    is_child = case.age in CHILD_GROUPS
    partial_burns = [b for b in case.burns.values() if b.depth != Depth.SUPERFICIAL]
    deep_burns = [b for b in case.burns.values()
                  if b.depth in (Depth.DEEP_PARTIAL, Depth.FULL_THICKNESS)]
    special = [b for b in partial_burns if b.region in SPECIAL_AREAS]

    emergency, hospital = [], []
    shock_threshold = 10 if is_child else 20
    if tbsa >= shock_threshold:
        emergency.append(("shock", {"threshold": shock_threshold}))
    if case.circumferential:
        emergency.append(("circumferential", {}))
    if tbsa > 10 and not emergency:
        hospital.append(("over10", {}))
    if any(b.depth == Depth.FULL_THICKNESS for b in deep_burns):
        hospital.append(("full", {}))
    elif deep_burns:
        hospital.append(("deep", {}))
    if special:
        hospital.append(("special", {}))
    if tbsa >= 1 and not emergency:
        hospital.append(("palm", {}))
    if case.age in (AgeGroup.UNDER_1, AgeGroup.AGE_1_4) and partial_burns:
        hospital.append(("child5", {}))

    if emergency:
        level, reasons = "emergency", emergency + hospital
    elif hospital:
        level, reasons = "hospital", hospital
    else:
        level, reasons = "home", [("home", {})]

    return Assessment(round(tbsa, 1), round(superficial, 1), rows, level, reasons)


def parkland_ml(weight_kg: float, tbsa: float) -> tuple[float, float, float]:
    """Parkland formula: 4 mL x kg x %TBSA over 24 h, half in the first 8 h."""
    total = 4 * weight_kg * tbsa
    return total, total / 2, total / 2
