from concurrent.futures import ThreadPoolExecutor

import pytest

from ios_poll.storage import PollError, PollStore


@pytest.fixture
def store(tmp_path):
    result = PollStore(tmp_path / "poll.sqlite3")
    result.init()
    return result


def test_initial_and_zero_votes(store):
    assert store.snapshot()["status"] == "WAITING"
    session = store.start()
    assert session == 1
    assert store.snapshot()["total"] == 0
    assert store.snapshot()["results"]["ios"]["percentage"] == 0


def test_one_vote_per_account_and_change(store):
    session = store.start()
    assert store.cast(session, 101, "ios") is True
    version = store.snapshot()["version"]
    assert store.cast(session, 101, "ios") is False
    assert store.snapshot()["version"] == version
    assert store.cast(session, 101, "android") is True
    assert store.get_vote(session, 101) == "android"
    assert store.snapshot()["total"] == 1
    assert store.snapshot()["results"]["ios"]["votes"] == 0


def test_close_and_new_round(store):
    session = store.start()
    with pytest.raises(PollError):
        store.start()
    store.cast(session, 101, "ios")
    assert store.close() == session
    with pytest.raises(PollError):
        store.close()
    with pytest.raises(PollError):
        store.cast(session, 101, "android")
    newer = store.start()
    assert newer != session
    assert store.snapshot()["total"] == 0
    with pytest.raises(PollError):
        store.cast(session, 102, "ios")


def test_other_and_percentages(store):
    session = store.start()
    for user, choice in enumerate(("ios", "android", "other"), 1):
        store.cast(session, user, choice)
    state = store.snapshot()
    assert state["total"] == 3
    assert all(state["results"][choice]["percentage"] == 33.3 for choice in ("ios", "android", "other"))


def test_concurrent_votes_no_duplicates(store):
    session = store.start()

    def write(n):
        return store.cast(session, n % 100 + 1, "ios" if n % 2 else "android")

    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(write, range(300)))
    assert store.snapshot()["total"] == 100


def test_state_persists_and_notifications_queued(store):
    session = store.start()
    store.cast(session, 42, "ios")
    store.close()
    reopened = PollStore(store.path)
    assert reopened.snapshot()["status"] == "CLOSED"
    assert reopened.snapshot()["total"] == 1
    assert reopened.claim_notification(session) == 42
    reopened.finish_notification(session, 42, True)
    assert reopened.claim_notification(session) is None


def test_reject_invalid_choice(store):
    session = store.start()
    with pytest.raises(ValueError):
        store.cast(session, 1, "windows")


def test_close_competes_with_vote(store):
    session = store.start()
    with ThreadPoolExecutor(max_workers=2) as pool:
        vote = pool.submit(store.cast, session, 1, "ios")
        close = pool.submit(store.close)
        try:
            vote.result()
        except PollError:
            pass
        assert close.result() == session
    assert store.snapshot()["status"] == "CLOSED"
