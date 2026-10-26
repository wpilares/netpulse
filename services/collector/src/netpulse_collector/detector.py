import logging
from collections.abc import Callable
from datetime import UTC, datetime

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
    ) -> None:
        self._config = config
        self._policy = policy
        self._link_capacity_bps = link_capacity_bps
        self._clock = clock
        self._samples: dict[PortKey, PortSample] = {}
        self._baselines: dict[BaselineKey, Baseline] = {}
        self._states: dict[AlertKey, AlertState] = {}

    def observe(self, report: PortStatsReport) -> tuple[AlertEvent, ...]:
        signals: list[AnomalySignal] = []
        for switch in report.switches:
            for sample in port_samples(switch):
                signals.extend(self._score(sample))
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

    def _report_time(self, report: PortStatsReport) -> datetime:
        collected = [switch.collected_at for switch in report.switches]
        return max(collected) if collected else self._clock()


class DetectionObserver:
    def __init__(
        self, detector: AnomalyDetector, repository: AlertRepository, notifier: AlertNotifier
    ) -> None:
        self._detector = detector
        self._repository = repository
        self._notifier = notifier

    async def observe(self, report: PortStatsReport) -> None:
        events = self._detector.observe(report)
        if not events:
            return
        try:
            await self._repository.apply(events)
        except AlertWriteError:
            logger.exception("storing %d alert events failed", len(events))
        await self._notifier.notify(events)
