import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from netpulse_collector.alerts import AlertNotifier, AlertRepository, AlertWriteError
from netpulse_core import (
    AlertEvent,
    AlertKey,
    AlertPolicy,
    AlertState,
    AnomalySignal,
    Baseline,
    BaselineKey,
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

    def observe(self, report: PortStatsReport) -> tuple[AlertEvent, ...]:
        signals: list[AnomalySignal] = []
        seen: set[PortKey] = set()
        for switch in report.switches:
            for sample in port_samples(switch):
                seen.add((sample.dpid, sample.stats.port_no))
                signals.extend(self._score(sample))
        self._prune_vanished_ports(seen)
        self._states, events = evaluate_alerts(
            self._states, signals, now=self._report_time(report), policy=self._policy
        )
        return events

    def _score(self, sample: PortSample) -> tuple[AnomalySignal, ...]:
        port_no = sample.stats.port_no
        if is_reserved_port(port_no):
            return ()
        key: PortKey = (sample.dpid, port_no)
        previous = self._samples.get(key)
        self._samples[key] = sample
        if previous is None:
            return ()
        kpis = compute_port_kpis(previous, sample, link_capacity_bps=self._link_capacity_bps)
        self._baselines, signals = detect_port_anomalies(self._baselines, kpis, self._config)
        return signals

    def _prune_vanished_ports(self, seen: set[PortKey]) -> None:
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
            self._baselines = {
                baseline_key: baseline
                for baseline_key, baseline in self._baselines.items()
                if baseline_key[:2] != key
            }

    def _report_time(self, report: PortStatsReport) -> datetime:
        collected = [switch.collected_at for switch in report.switches]
        return max(collected) if collected else self._clock()


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
    ) -> None:
        self._detector = detector
        self._repository = repository
        self._notifier = notifier
        self._retention = retention
        self._cycles = 0

    async def observe(self, report: PortStatsReport) -> None:
        events = self._detector.observe(report)
        if events:
            await self._store(events)
            await self._notifier.notify(events)
        await self._purge_when_due()

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
