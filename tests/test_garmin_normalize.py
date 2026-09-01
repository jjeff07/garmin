import pytest

from dive_qr.garmin import (
    GarminError,
    _activities_to_summaries,
    _extract_dives,
    dive_from_summary,
)

DIVE_SUMMARY_JSON = {
    "diveActivities": [
        {"connectActivityId": 1, "startTime": "2026-06-06T17:10:50-04:00", "maxDepth": 3.8,
         "totalTime": 1414.3, "avgDepth": 2.9, "number": 5, "name": "Single-Gas"},
        {"connectActivityId": 2, "startTime": "2026-06-05T09:00:00-04:00", "maxDepth": 18.0,
         "totalTime": 2600.0},
    ]
}

ACTIVITY_LIST = [
    {"activityId": 99, "activityName": "Dive", "startTimeLocal": "2026-06-06 17:10:50",
     "startTimeGMT": "2026-06-06 21:10:50", "duration": 1414.3, "maxDepth": 3.8,
     "averageDepth": 2.9},
    {"activityId": 98, "activityName": "Older", "startTimeLocal": "2026-01-01 08:00:00",
     "duration": 1200.0},
]


def test_extract_dives_sorts_newest_first():
    d = _extract_dives(DIVE_SUMMARY_JSON)
    assert [x["connectActivityId"] for x in d] == [1, 2]


def test_dive_from_summary_web_shape():
    dv = dive_from_summary(_extract_dives(DIVE_SUMMARY_JSON)[0], None, use_fit=False)
    assert dv.start_local.strftime("%Y%m%d%H%M") == "202606061710"
    assert dv.max_depth_m == 3.8
    assert dv.activity_id == 1
    assert dv.dive_number == 5


def test_activities_to_summaries_maps_and_sorts():
    s = _activities_to_summaries(ACTIVITY_LIST)
    assert s[0]["connectActivityId"] == 99
    assert s[0]["startTime"] == "2026-06-06 17:10:50"  # prefers local
    assert s[0]["maxDepth"] == 3.8


def test_dive_from_summary_activity_list_shape():
    dv = dive_from_summary(_activities_to_summaries(ACTIVITY_LIST)[0], None, use_fit=False)
    assert dv.start_local.strftime("%Y%m%d%H%M") == "202606061710"
    assert dv.max_depth_m == 3.8
    assert dv.activity_id == 99


def test_dive_from_summary_rejects_non_dive():
    with pytest.raises(GarminError):
        dive_from_summary({"activityId": 5, "startTimeLocal": "2026-01-01 08:00:00"}, None, use_fit=False)
