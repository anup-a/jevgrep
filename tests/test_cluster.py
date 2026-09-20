"""Incremental semantic grouping: each record joins a group or starts one."""

import pytest

from jevgrep.cluster import NEW_GROUP, Group, assign, build_group_question, visible
from jevgrep.records import Record


def rec(text: str, index: int = 1) -> Record:
    return Record(origin="(standard input)", index=index, text=text, state={"record": text})


def test_first_record_starts_a_group():
    groups = assign((), rec("login broken"), NEW_GROUP, confidence=0.9, min_confidence=0.0)

    assert len(groups) == 1
    assert groups[0].representative.text == "login broken"
    assert groups[0].members == (groups[0].representative,)


def test_a_matching_record_joins_the_named_group():
    groups = assign((), rec("login broken", 1), NEW_GROUP, 0.9, 0.0)
    groups = assign(groups, rec("cannot sign in", 2), groups[0].key, 0.9, 0.0)

    assert len(groups) == 1
    assert [m.text for m in groups[0].members] == ["login broken", "cannot sign in"]


def test_a_distinct_record_starts_a_second_group():
    groups = assign((), rec("login broken", 1), NEW_GROUP, 0.9, 0.0)
    groups = assign(groups, rec("checkout 500s", 2), NEW_GROUP, 0.9, 0.0)

    assert [g.key for g in groups] == ["g0", "g1"]


def test_group_keys_stay_unique_as_groups_accumulate():
    groups = ()
    for i in range(5):
        groups = assign(groups, rec(f"issue {i}", i), NEW_GROUP, 0.9, 0.0)

    assert len({g.key for g in groups}) == 5


def test_a_low_confidence_match_starts_a_new_group_instead_of_merging():
    # Merging is the destructive direction: a wrong merge hides a record entirely,
    # while a wrong split only costs a duplicate line.
    groups = assign((), rec("login broken", 1), NEW_GROUP, 0.9, 0.0)
    groups = assign(groups, rec("cannot sign in", 2), groups[0].key, 0.2, min_confidence=0.7)

    assert len(groups) == 2


def test_a_confident_match_still_merges_under_the_same_floor():
    groups = assign((), rec("login broken", 1), NEW_GROUP, 0.9, 0.0)
    groups = assign(groups, rec("cannot sign in", 2), groups[0].key, 0.95, min_confidence=0.7)

    assert len(groups) == 1


def test_assign_does_not_mutate_the_groups_it_was_given():
    original = assign((), rec("login broken", 1), NEW_GROUP, 0.9, 0.0)
    assign(original, rec("cannot sign in", 2), original[0].key, 0.9, 0.0)

    assert len(original[0].members) == 1


def test_an_unknown_choice_is_rejected():
    groups = assign((), rec("login broken"), NEW_GROUP, 0.9, 0.0)

    with pytest.raises(ValueError):
        assign(groups, rec("other", 2), "g99", 0.9, 0.0)


def test_visible_returns_everything_below_the_cap():
    groups = tuple(Group(f"g{i}", rec(f"r{i}", i), (rec(f"r{i}", i),)) for i in range(3))

    assert visible(groups, 10) == groups


def test_visible_keeps_the_most_recent_groups_when_over_the_cap():
    groups = tuple(Group(f"g{i}", rec(f"r{i}", i), (rec(f"r{i}", i),)) for i in range(10))

    assert [g.key for g in visible(groups, 3)] == ["g7", "g8", "g9"]


def test_question_offers_every_visible_group_plus_a_new_option():
    groups = (
        Group("g0", rec("login broken"), (rec("login broken"),)),
        Group("g1", rec("checkout 500s", 2), (rec("checkout 500s", 2),)),
    )

    body = build_group_question(groups, aspect=None)

    assert body["type"] == "choice"
    assert set(body["criteria"]) == {"g0", "g1", NEW_GROUP}
    assert "login broken" in body["criteria"]["g0"]


def test_the_aspect_is_carried_into_the_instructions():
    groups = (Group("g0", rec("login broken"), (rec("login broken"),)),)

    body = build_group_question(groups, aspect="the underlying root cause")

    assert "the underlying root cause" in body["instructions"]


def test_a_long_representative_is_truncated_so_the_question_stays_small():
    long_text = "x" * 5000
    groups = (Group("g0", rec(long_text), (rec(long_text),)),)

    assert len(build_group_question(groups, None)["criteria"]["g0"]) < 400
