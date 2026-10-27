import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from netpulse_collector.alerts import (
    AlertNotifier,
    AlertRepository,
    AlertWriteError,
    BaselineRepository,
)
from netpulse_core import (
    METRICS,
    AlertEvent,
    AlertKey,
    AlertPolicy,
    AlertState,
    AnomalySignal,
    Baseline,
    BaselineKey,
    Baselines,
    DatapathId,
    DetectionConfig,
    PortNumber,
    PortSample,
    PortStatsReport,
    compute_port_kpis,
    detect_port_anomalies,
    evaluate_alerts,
    is_reserved_port,
    port_samples,
)

logger = logging.getLogger(__name__)

type Clock = Callable[[], datetime]
type PortKey = tuple[DatapathId, PortNumber]

DEFAULT_PRUNE_AFTER_CYCLES = 60


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ObservationResult:
    events: tuple[AlertEvent, ...]
    updated_baselines: dict[BaselineKey, Baseline]
    pruned_keys: tuple[BaselineKey, ...]


class AnomalyDetector:
    def __init__(
        self,
        *,
        config: DetectionConfig,
        policy: AlertPolicy,
        link_capacity_bps: int | None,
        clock: Clock = utc_now,
        prune_after_cycles: int = DEFAULT_PRUNE_AFTER_CYCLES,
    ) -> None:
        self._config = config
        self._policy = policy
        self._link_capacity_bps = link_capacity_bps
        self._clock = clock
        self._prune_after_cycles = prune_after_cycles
        self._samples: dict[PortKey, PortSample] = {}
        self._baselines: dict[BaselineKey, Baseline] = {}
        self._states: dict[AlertKey, AlertState] = {}
        self._absent_cycles: dict[PortKey, int] = {}

    def seed(self, states: Iterable[AlertState]) -> None:
        for state in states:
            self._states[state.key] = state

    def seed_baselines(self, baselines: Baselines) -> None:
        self._baselines.update(baselines)

    def observe(self, report: PortStatsReport) -> tuple[AlertEvent, ...]:
        return self.observe_cycle(report).events

    def observe_cycle(self, report: PortStatsReport) -> ObservationResult:
        signals: list[AnomalySignal] = []
        seen: set[PortKey] = set()
        updated: dict[BaselineKey, Baseline] = {}
        for switch in report.switches:
            for sample in port_samples(switch):
                seen.add((sample.dpid, sample.stats.port_no))
                port_signals, port_baselines = self._score(sample)
                signals.extend(port_signals)
                updated.update(port_baselines)
        now = self._report_time(report)
        vanished = self._prune_vanished_ports(seen)
        pruned = self._forget_baselines(vanished)
        self._states, events = evaluate_alerts(self._states, signals, now=now, policy=self._policy)
        resolved = self._forget_alerts(vanished, now)
        return ObservationResult(events + resolved, updated, pruned)

    def _score(
        self, sample: PortSample
    ) -> tuple[tuple[AnomalySignal, ...], dict[BaselineKey, Baseline]]:
        port_no = sample.stats.port_no
        if is_reserved_port(port_no):
            return (), {}
        key: PortKey = (sample.dpid, port_no)
        previous = self._samples.get(key)
        self._samples[key] = sample
        if previous is None:
            return (), {}
        kpis = compute_port_kpis(previous, sample, link_capacity_bps=self._link_capacity_bps)
        before = self._baselines
        self._baselines, signals = detect_port_anomalies(before, kpis, self._config)
        updated = {
            baseline_key: baseline
            for baseline_key in _baseline_keys(key)
            if (baseline := self._baselines.get(baseline_key)) is not None
            and before.get(baseline_key) != baseline
        }
        return signals, updated

    def _prune_vanished_ports(self, seen: set[PortKey]) -> frozenset[PortKey]:
        vanished: set[PortKey] = set()
        for key in list(self._samples):
            if key in seen:
                self._absent_cycles.pop(key, None)
                continue
            absent = self._absent_cycles.get(key, 0) + 1
            if absent <= self._prune_after_cycles:
                self._absent_cycles[key] = absent
                continue
            del self._samples[key]
            del self._absent_cycles[key]
            vanished.add(key)
        return frozenset(vanished)

    def _forget_baselines(self, vanished: frozenset[PortKey]) -> tuple[BaselineKey, ...]:
        return tuple(
            baseline_key
            for port in sorted(vanished)
            for baseline_key in _baseline_keys(port)
            if self._baselines.pop(baseline_key, None) is not None
        )

    def _forget_alerts(self, vanished: frozenset[PortKey], now: datetime) -> tuple[AlertEvent, ...]:
        resolved: list[AlertEvent] = []
        for key in sorted(key for key in self._states if (key[0], key[1]) in vanished):
            state = self._states.pop(key)
            if state.status != "open":
                continue
            closed = state.model_copy(update={"status": "resolved", "resolved_at": now})
            resolved.append(AlertEvent(kind="resolved", state=closed))
        return tuple(resolved)

    def _report_time(self, report: PortStatsReport) -> datetime:
        collected = [switch.collected_at for switch in report.switches]
        return max(collected) if collected else self._clock()


def _baseline_keys(port: PortKey) -> tuple[BaselineKey, ...]:
    dpid, port_no = port
    return tuple((dpid, port_no, metric) for metric in METRICS)


@dataclass(frozen=True, slots=True)
class AlertRetention:
    older_than: timedelta
    every_cycles: int


class DetectionObserver:
    def __init__(
        self,
        detector: AnomalyDetector,
        repository: AlertRepository,
        notifier: AlertNotifier,
        retention: AlertRetention | None = None,
        *,
        baselines: BaselineRepository | None = None,
    ) -> None:
        self._detector = detector
        self._repository = repository
        self._notifier = notifier
        self._retention = retention
        self._baselines = baselines
        self._pending_prunes: set[BaselineKey] = set()
        self._cycles = 0

    async def observe(self, report: PortStatsReport) -> None:
        result = self._detector.observe_cycle(report)
        if result.events:
            await self._store(result.events)
            await self._notifier.notify(result.events)
        await self._persist_baselines(result)
        await self._purge_when_due()

    async def _persist_baselines(self, result: ObservationResult) -> None:
        if self._baselines is None:
            return
        self._pending_prunes.update(result.pruned_keys)
        self._pending_prunes.difference_update(result.updated_baselines)
        if result.updated_baselines:
            await self._save_baselines(self._baselines, result.updated_baselines)
        if self._pending_prunes:
            await self._delete_pending_baselines(self._baselines)

    async def _save_baselines(
        self, repository: BaselineRepository, baselines: dict[BaselineKey, Baseline]
    ) -> None:
        try:
            await repository.save(baselines)
        except AlertWriteError:
            logger.exception("saving %d baselines failed", len(baselines))

    async def _delete_pending_baselines(self, repository: BaselineRepository) -> None:
        pending = tuple(sorted(self._pending_prunes))
        try:
            await repository.delete(pending)
        except AlertWriteError:
            logger.exception(
                "deleting %d pruned baselines failed, retrying next cycle", len(pending)
            )
            return
        self._pending_prunes.clear()

    async def _store(self, events: tuple[AlertEvent, ...]) -> None:
        try:
            await self._repository.apply(events)
        except AlertWriteError:
            logger.exception("storing %d alert events failed", len(events))

    async def _purge_when_due(self) -> None:
        if self._retention is None:
            return
        self._cycles += 1
        if self._cycles % self._retention.every_cycles:
            return
        try:
            purged = await self._repository.purge_resolved(self._retention.older_than)
        except AlertWriteError:
            logger.exception("purging resolved alerts failed")
            return
        logger.info("purged %d resolved alerts older than %s", purged, self._retention.older_than)
