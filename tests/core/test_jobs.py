"""Tests for the Cerebrus JobScheduler.

Focus areas
-----------

* Dependency-graph cycle detection refuses cyclic submissions
  (Resource-Allocation-Graph invariant).
* Topological execution order: dependents always run after their
  prerequisites.
* Status transitions follow the linear lifecycle and are visible to
  external observers without explicit locking (GIL-atomic reads).
* Failed jobs cascade-cancel their dependents instead of running them.
* ``Job.wait`` blocks until completion and returns an accurate flag.
"""

from __future__ import annotations

import threading
import time

import pytest

from cerebrus.core.jobs import (
    CyclicDependencyError,
    Job,
    JobScheduler,
    JobStatus,
)


@pytest.fixture
def scheduler():
    s = JobScheduler(max_workers=2, name="test")
    s.start()
    try:
        yield s
    finally:
        s.stop(drain=True, timeout=2.0)


def test_simple_job_runs_and_status_transitions_to_done(scheduler):
    ran = threading.Event()

    def work() -> None:
        ran.set()

    job = scheduler.submit(Job(fn=work, name="hello"))
    assert job.wait(timeout=2.0)
    assert ran.is_set()
    assert job.status is JobStatus.DONE
    assert job.error is None


def test_failing_job_records_exception_and_status(scheduler):
    def boom() -> None:
        raise RuntimeError("boom")

    job = scheduler.submit(Job(fn=boom, name="boom"))
    assert job.wait(timeout=2.0)
    assert job.status is JobStatus.FAILED
    assert isinstance(job.error, RuntimeError)
    assert str(job.error) == "boom"


def test_dependent_runs_after_prerequisite(scheduler):
    order: list[str] = []
    a_done = threading.Event()

    def a() -> None:
        time.sleep(0.05)
        order.append("a")
        a_done.set()

    def b() -> None:
        order.append("b")

    job_a = scheduler.submit(Job(fn=a, name="a"))
    scheduler.submit(Job(fn=b, name="b", depends_on=(job_a.id,)))

    a_done.wait(timeout=2.0)
    # Spin briefly so b can run after the worker promotes it.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and len(order) < 2:
        time.sleep(0.01)

    assert order == ["a", "b"]


def test_dependent_cancelled_when_prerequisite_fails(scheduler):
    def fail() -> None:
        raise RuntimeError("nope")

    ran_b = threading.Event()

    def b() -> None:
        ran_b.set()

    job_a = scheduler.submit(Job(fn=fail, name="a"))
    job_b = scheduler.submit(Job(fn=b, name="b", depends_on=(job_a.id,)))

    assert job_a.wait(timeout=2.0)
    assert job_b.wait(timeout=2.0)

    assert job_a.status is JobStatus.FAILED
    assert job_b.status is JobStatus.CANCELLED
    assert not ran_b.is_set()


def test_cycle_detection_rejects_two_node_cycle():
    s = JobScheduler(max_workers=1, name="cycle-test")
    s.start()
    try:
        a = Job(fn=lambda: None, name="a", depends_on=("b-id",), id="a-id")
        b = Job(fn=lambda: None, name="b", depends_on=("a-id",), id="b-id")
        s.submit(a)
        with pytest.raises(CyclicDependencyError) as excinfo:
            s.submit(b)
        assert "->" in str(excinfo.value)
        # After rejection the rejected job must not linger in the registry,
        # so the graph stays acyclic.
        assert s.get("b-id") is None
    finally:
        s.stop(drain=False, timeout=1.0)


def test_cycle_detection_rejects_three_node_cycle():
    s = JobScheduler(max_workers=1, name="cycle3")
    s.start()
    try:
        a = Job(fn=lambda: None, name="a", id="a", depends_on=("c",))
        b = Job(fn=lambda: None, name="b", id="b", depends_on=("a",))
        c = Job(fn=lambda: None, name="c", id="c", depends_on=("b",))
        s.submit(a)
        s.submit(b)
        with pytest.raises(CyclicDependencyError):
            s.submit(c)
    finally:
        s.stop(drain=False, timeout=1.0)


def test_cancel_pending_job(scheduler):
    started = threading.Event()
    release = threading.Event()

    def blocker() -> None:
        started.set()
        release.wait(timeout=2.0)

    def downstream() -> None:
        pass  # pragma: no cover - cancelled before it can run

    head = scheduler.submit(Job(fn=blocker, name="head"))
    started.wait(timeout=2.0)

    tail = scheduler.submit(Job(fn=downstream, name="tail", depends_on=(head.id,)))
    assert scheduler.cancel(tail.id) is True
    assert tail.status is JobStatus.CANCELLED

    release.set()
    head.wait(timeout=2.0)
    assert head.status is JobStatus.DONE


def test_wait_returns_false_on_timeout(scheduler):
    release = threading.Event()

    def blocker() -> None:
        release.wait(timeout=2.0)

    job = scheduler.submit(Job(fn=blocker, name="blocker"))
    assert job.wait(timeout=0.1) is False
    assert job.status in (JobStatus.READY, JobStatus.RUNNING)
    release.set()
    job.wait(timeout=2.0)
    assert job.status is JobStatus.DONE


def test_status_visible_to_external_thread_without_locks(scheduler):
    """Readers should never see a torn status. They may see an older
    valid state but never an invalid value. Sample 100 times and assert
    every reading is a real JobStatus enum member."""
    release = threading.Event()

    def blocker() -> None:
        release.wait(timeout=2.0)

    job = scheduler.submit(Job(fn=blocker, name="status-probe"))
    seen: set[JobStatus] = set()
    for _ in range(100):
        seen.add(job.status)
    release.set()
    job.wait(timeout=2.0)
    seen.add(job.status)

    # Every observed value is a valid JobStatus (no torn reads possible
    # due to GIL atomicity of single-attribute writes).
    assert seen.issubset(set(JobStatus))
    assert JobStatus.DONE in seen


def test_submit_with_dangling_external_dep_keeps_job_pending():
    """A dependency that hasn't been submitted yet does not block the
    cycle check, but the job stays PENDING until the dep arrives and
    completes."""
    s = JobScheduler(max_workers=1, name="dangling")
    s.start()
    try:
        ran = threading.Event()
        tail = s.submit(
            Job(fn=lambda: ran.set(), name="tail", depends_on=("not-yet",))
        )
        # No worker should pick this up.
        time.sleep(0.2)
        assert tail.status is JobStatus.PENDING
        assert not ran.is_set()
    finally:
        s.stop(drain=False, timeout=1.0)
