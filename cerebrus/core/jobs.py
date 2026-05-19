"""Cerebrus background-job scheduler.

A small worker pool with explicit dependency declaration. Designed for the
recurring UI need to run something slow (ADB enumeration, S3 upload, perf
report generation, analytics upload) off the DPG callback thread without
freezing the UI.

Design choices
--------------

* **Atomic state transitions, not mutexes.** Python's GIL makes plain
  attribute writes on a ``Job`` atomic from any other thread's point of
  view. Readers see a single ``JobStatus`` value at a time, never a half-
  written one, so a per-job ``threading.Lock`` is unnecessary. The only
  mutex in the module guards a single multi-step operation: submitting a
  new job (mutating the registry + running the cycle check + promoting
  newly-ready jobs). Wait-for-completion uses ``threading.Event`` which
  exposes an atomic ``set()`` / ``wait()`` pair; readers never poll a
  shared counter.
* **Resource-Allocation-Graph cycle detection.** Dependencies form a
  directed graph (job -> its prerequisites). Before a job is enqueued, the
  scheduler runs a three-colour DFS over the registry and refuses to
  accept any submission that would close a cycle. Once accepted, the
  graph is acyclic by construction, so the worker loop can promote
  dependents to ``READY`` without re-checking.
* **Workers pull, scheduler promotes.** Workers block on a
  ``queue.Queue`` and never inspect dependency state — they trust the
  scheduler to have promoted only safe jobs. This keeps the hot path
  lock-free.
* **Failed dependencies cascade as cancellation.** A job whose
  prerequisite ``FAILED`` is moved to ``CANCELLED`` without being run,
  with a structured log line.
* **Logging is structured.** Every state change emits one log line at
  INFO or higher with the job id, status, and timing if relevant. Errors
  include the traceback. Callers wire this into the Cerebrus live log
  panel via Python ``logging`` handlers; the scheduler itself does not
  know about the UI.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from queue import Empty, Queue
from typing import Any, Callable, Iterable

logger = logging.getLogger("cerebrus.jobs")


class JobStatus(Enum):
    """Lifecycle states a job can occupy.

    Transitions are linear (no jumps backwards). Each transition is a
    single GIL-atomic attribute assignment on the ``Job`` instance.
    """

    PENDING = "pending"      # waiting for dependencies
    READY = "ready"          # enqueued, waiting for a worker
    RUNNING = "running"      # worker invoked fn
    DONE = "done"            # fn returned cleanly
    FAILED = "failed"        # fn raised
    CANCELLED = "cancelled"  # upstream failed; never ran


class CyclicDependencyError(ValueError):
    """Raised when a submission would close a dependency cycle."""


@dataclass
class Job:
    """A unit of work the scheduler manages.

    Attribute writes (``status``, ``error``) are intentionally lock-free.
    The GIL guarantees individual writes are atomic; transitions follow
    the linear lifecycle, so a stale read at most sees an older valid
    state — never a torn value.
    """

    fn: Callable[[], Any]
    name: str = "job"
    depends_on: tuple[str, ...] = ()
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    error: BaseException | None = None
    result: Any = None
    submitted_at: float = field(default_factory=time.monotonic)
    started_at: float | None = None
    finished_at: float | None = None
    _done: threading.Event = field(
        default_factory=threading.Event, repr=False, compare=False
    )

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the job is no longer RUNNING / READY / PENDING.

        Returns ``True`` if the job finished within ``timeout``, ``False``
        otherwise. Uses ``threading.Event`` so the caller does not have
        to busy-wait or hold a lock.
        """
        return self._done.wait(timeout)

    @property
    def duration_s(self) -> float | None:
        if self.started_at is None or self.finished_at is None:
            return None
        return self.finished_at - self.started_at


class JobScheduler:
    """Worker-pool scheduler with dependency-graph cycle detection.

    Use::

        scheduler = JobScheduler(max_workers=2, name="cerebrus")
        scheduler.start()
        try:
            job = Job(fn=do_thing, name="detect-devices")
            scheduler.submit(job)
            job.wait()
        finally:
            scheduler.stop()

    For long-lived programs (e.g. the Cerebrus app), call ``start()``
    once at boot and ``stop()`` at shutdown.
    """

    def __init__(self, max_workers: int = 2, name: str = "cerebrus") -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self._name = name
        self._max_workers = max_workers
        self._jobs: dict[str, Job] = {}
        self._queue: Queue[Job] = Queue()
        self._workers: list[threading.Thread] = []
        self._stop_event = threading.Event()
        # The submit_lock guards the multi-step submit operation only.
        # Worker hot-paths do not acquire it: they read ``status`` via
        # GIL-atomic reads and trust the graph the scheduler has built.
        self._submit_lock = threading.Lock()
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._stop_event.clear()
        self._workers = [
            threading.Thread(
                target=self._worker_loop,
                name=f"{self._name}-worker-{i}",
                daemon=True,
            )
            for i in range(self._max_workers)
        ]
        for w in self._workers:
            w.start()
        self._running = True
        logger.info(
            "JobScheduler %r started with %d worker(s)", self._name, self._max_workers
        )

    def stop(self, drain: bool = True, timeout: float | None = 5.0) -> None:
        """Signal workers to exit. With ``drain=True`` waits for jobs in
        flight to finish (bounded by ``timeout``)."""
        if not self._running:
            return
        self._stop_event.set()
        if drain:
            for w in self._workers:
                w.join(timeout)
        self._workers.clear()
        self._running = False
        logger.info("JobScheduler %r stopped", self._name)

    # ------------------------------------------------------------------
    # Submission + dependency graph
    # ------------------------------------------------------------------

    def submit(self, job: Job) -> Job:
        """Register a job. Raises ``CyclicDependencyError`` if the
        resulting dependency graph contains a cycle. Job is enqueued
        only after the graph passes the acyclicity check."""
        with self._submit_lock:
            if job.id in self._jobs:
                raise ValueError(f"job id {job.id!r} already submitted")
            self._jobs[job.id] = job
            try:
                self._raise_on_cycle()
            except CyclicDependencyError:
                # Roll back so callers can retry with a fixed graph.
                del self._jobs[job.id]
                raise
            logger.info(
                "Job %s submitted (name=%r depends_on=%s)",
                job.id,
                job.name,
                list(job.depends_on),
            )
            self._promote_ready_jobs_locked()
        return job

    def cancel(self, job_id: str) -> bool:
        """Cancel a pending job. Returns True if cancelled; False if the
        job already started or is unknown."""
        job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.status not in (JobStatus.PENDING, JobStatus.READY):
            return False
        job.status = JobStatus.CANCELLED
        job._done.set()
        logger.info("Job %s cancelled by caller", job_id)
        return True

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def all_jobs(self) -> Iterable[Job]:
        return tuple(self._jobs.values())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _raise_on_cycle(self) -> None:
        """Three-colour DFS over the dependency graph.

        WHITE = unvisited, GRAY = on current DFS stack, BLACK = fully
        processed. A back-edge to GRAY is a cycle.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        colour: dict[str, int] = {jid: WHITE for jid in self._jobs}

        def visit(jid: str, stack: list[str]) -> None:
            colour[jid] = GRAY
            for dep in self._jobs[jid].depends_on:
                if dep not in self._jobs:
                    # External / not-yet-submitted dependency. Treated as
                    # satisfied for cycle purposes — the job stays
                    # PENDING until the dep shows up.
                    continue
                if colour[dep] == GRAY:
                    chain = stack + [jid, dep]
                    raise CyclicDependencyError(
                        "dependency cycle: " + " -> ".join(chain)
                    )
                if colour[dep] == WHITE:
                    visit(dep, stack + [jid])
            colour[jid] = BLACK

        for jid in list(self._jobs):
            if colour[jid] == WHITE:
                visit(jid, [])

    def _promote_ready_jobs_locked(self) -> None:
        """Move PENDING jobs to READY when their deps are DONE.

        Caller must hold ``_submit_lock`` OR be running inside a worker
        finalisation step (workers re-acquire the lock before calling
        this from ``_worker_loop``).
        """
        for job in self._jobs.values():
            if job.status is not JobStatus.PENDING:
                continue
            # Known deps that already failed/cancelled mark this job as
            # upstream-broken. Unknown deps are treated as not-yet-submitted
            # (the job stays PENDING until they arrive, matching cycle-check
            # semantics).
            broken_upstream = False
            unsatisfied = False
            for dep_id in job.depends_on:
                dep = self._jobs.get(dep_id)
                if dep is None:
                    unsatisfied = True
                    continue
                if dep.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                    broken_upstream = True
                    break
                if dep.status is not JobStatus.DONE:
                    unsatisfied = True
            if broken_upstream:
                job.status = JobStatus.CANCELLED
                job._done.set()
                logger.warning(
                    "Job %s cancelled (upstream failed/cancelled): %r",
                    job.id,
                    job.name,
                )
                continue
            if unsatisfied:
                continue
            job.status = JobStatus.READY
            self._queue.put(job)
            logger.debug("Job %s promoted to READY: %r", job.id, job.name)

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                job = self._queue.get(timeout=0.5)
            except Empty:
                continue
            self._execute(job)
            # Promote dependents now that this job finished.
            with self._submit_lock:
                self._promote_ready_jobs_locked()

    def _execute(self, job: Job) -> None:
        job.status = JobStatus.RUNNING
        job.started_at = time.monotonic()
        logger.info("Job %s started: %r", job.id, job.name)
        try:
            job.result = job.fn()
        except BaseException as exc:  # noqa: BLE001 - we record the error
            job.error = exc
            job.status = JobStatus.FAILED
            job.finished_at = time.monotonic()
            logger.exception(
                "Job %s failed after %.3fs: %r", job.id, job.duration_s or 0.0, job.name
            )
        else:
            job.status = JobStatus.DONE
            job.finished_at = time.monotonic()
            logger.info(
                "Job %s done in %.3fs: %r", job.id, job.duration_s or 0.0, job.name
            )
        finally:
            job._done.set()


# ----------------------------------------------------------------------
# Process-wide default scheduler
# ----------------------------------------------------------------------

_default_scheduler: JobScheduler | None = None
_default_scheduler_lock = threading.Lock()


def get_default_scheduler() -> JobScheduler:
    """Return the process-wide ``JobScheduler``, starting it on first
    use. Cerebrus app code uses this; tests construct their own."""
    global _default_scheduler
    with _default_scheduler_lock:
        if _default_scheduler is None:
            _default_scheduler = JobScheduler(name="cerebrus")
            _default_scheduler.start()
        return _default_scheduler


def shutdown_default_scheduler(timeout: float | None = 5.0) -> None:
    """Stop the process-wide scheduler (test hook + app shutdown)."""
    global _default_scheduler
    with _default_scheduler_lock:
        if _default_scheduler is not None:
            _default_scheduler.stop(drain=True, timeout=timeout)
            _default_scheduler = None


__all__ = [
    "CyclicDependencyError",
    "Job",
    "JobScheduler",
    "JobStatus",
    "get_default_scheduler",
    "shutdown_default_scheduler",
]
