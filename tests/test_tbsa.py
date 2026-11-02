import pytest

from tbsa import (
    AgeGroup,
    BurnCase,
    Depth,
    Region,
    RegionBurn,
    assess,
    parkland_ml,
    region_percent,
)


@pytest.mark.parametrize("age", list(AgeGroup))
def test_every_age_column_sums_to_100(age):
    assert sum(region_percent(r, age) for r in Region) == pytest.approx(100.0)


def test_adult_close_to_rule_of_nines():
    adult = AgeGroup.ADULT
    head_neck = sum(region_percent(r, adult) for r in
                    (Region.HEAD_FRONT, Region.HEAD_BACK, Region.NECK_FRONT, Region.NECK_BACK))
    assert head_neck == 9.0


def test_infant_head_larger_than_adult():
    infant = region_percent(Region.HEAD_FRONT, AgeGroup.UNDER_1) * 2
    adult = region_percent(Region.HEAD_FRONT, AgeGroup.ADULT) * 2
    assert (infant, adult) == (19.0, 7.0)


def test_superficial_burns_excluded_from_tbsa():
    case = BurnCase(age=AgeGroup.ADULT)
    case.add(RegionBurn(Region.CHEST_ABDOMEN, 1.0, Depth.SUPERFICIAL))
    result = assess(case)
    assert result.tbsa == 0
    assert result.superficial_only == 13.0
    assert result.level == "home"


def test_large_adult_burn_is_emergency():
    case = BurnCase(age=AgeGroup.ADULT)
    case.add(RegionBurn(Region.CHEST_ABDOMEN, 1.0, Depth.SUPERFICIAL_PARTIAL))
    case.add(RegionBurn(Region.BACK, 0.6, Depth.SUPERFICIAL_PARTIAL))
    result = assess(case)
    assert result.tbsa == pytest.approx(20.8)
    assert result.level == "emergency"


def test_child_threshold_is_lower():
    case = BurnCase(age=AgeGroup.AGE_5_9)
    case.add(RegionBurn(Region.CHEST_ABDOMEN, 0.8, Depth.SUPERFICIAL_PARTIAL))
    assert assess(case).level == "emergency"  # 10.4% in a child


def test_hand_burn_needs_hospital_even_if_small():
    case = BurnCase(age=AgeGroup.ADULT)
    case.add(RegionBurn(Region.RIGHT_HAND_PALM, 0.3, Depth.SUPERFICIAL_PARTIAL))
    result = assess(case)
    assert result.tbsa < 1
    assert result.level == "hospital"


def test_small_blister_on_forearm_is_home_care():
    case = BurnCase(age=AgeGroup.ADULT)
    case.add(RegionBurn(Region.LEFT_FOREARM_FRONT, 0.2, Depth.SUPERFICIAL_PARTIAL))
    assert assess(case).level == "home"


def test_same_region_keeps_max_extent_and_deepest():
    case = BurnCase(age=AgeGroup.ADULT)
    case.add(RegionBurn(Region.LEFT_THIGH_FRONT, 0.5, Depth.FULL_THICKNESS))
    case.add(RegionBurn(Region.LEFT_THIGH_FRONT, 0.8, Depth.SUPERFICIAL_PARTIAL))
    burn = case.burns[Region.LEFT_THIGH_FRONT]
    assert (burn.fraction, burn.depth) == (0.8, Depth.FULL_THICKNESS)


def test_fraction_is_clamped():
    case = BurnCase(age=AgeGroup.ADULT)
    case.add(RegionBurn(Region.BACK, 1.7, Depth.SUPERFICIAL_PARTIAL))
    assert assess(case).tbsa == 13.0


def test_parkland():
    assert parkland_ml(70, 30) == (8400, 4200, 4200)
