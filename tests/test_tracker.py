from study_buddy.models import Question
from study_buddy.tracker import WeakPointTracker


def q(text="Q1", topic="T1"):
    return Question("short", text, "rep", topic=topic)


def test_error_goes_to_review_queue():
    t = WeakPointTracker()
    t.record(q(), "incorrect")
    assert [x.question for x in t.review_queue()] == ["Q1"]


def test_clean_correct_is_not_reviewed():
    t = WeakPointTracker()
    t.record(q(), "correct", elapsed=5)
    assert t.review_queue() == []


def test_slow_or_hint_counts_as_hesitation():
    t = WeakPointTracker()
    t.record(q("A"), "correct", elapsed=120)
    t.record(q("B"), "correct", elapsed=5, hint_used=True)
    assert {x.question for x in t.review_queue()} == {"A", "B"}
    assert t.summary()["hesitations"] == 2


def test_mastery_removes_from_queue():
    t = WeakPointTracker()
    t.record(q(), "incorrect")
    t.record(q(), "correct", elapsed=3)
    assert t.review_queue()  # 1 seule bonne réponse nette : pas encore acquis
    t.record(q(), "correct", elapsed=3)
    assert t.review_queue() == []


def test_priority_order_and_weak_topics():
    t = WeakPointTracker()
    t.record(q("easy", "Facile"), "correct", elapsed=100)  # hésitation
    t.record(q("hard", "Dur"), "incorrect")
    t.record(q("hard", "Dur"), "incorrect")
    assert t.review_queue()[0].question == "hard"
    assert t.weak_topics()[0] == "Dur"
    assert t.to_dict()["summary"]["errors"] == 2
