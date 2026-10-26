from collections.abc import Mapping
from math import sqrt
from typing import Final, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from netpulse_core.kpi import PortKpis, Rate
from netpulse_core.telemetry import DatapathId, PortNumber, TelemetryModel

type Metric = Literal["rx_bps", "tx_bps", "drop_rate", "error_rate"]
Severity = Literal["warning", "critical"]

METRICS: Final[tuple[Metric, ...]] = ("rx_bps", "tx_bps", "drop_rate", "error_rate")
THROUGHPUT_METRICS: Final[frozenset[Metric]] = frozenset({"rx_bps", "tx_bps"})

type BaselineKey = tuple[DatapathId, PortNumber, Metric]
type Baselines = Mapping[BaselineKey, Baseline]


class Baseline(TelemetryModel):
    mean: float
    variance: float = Field(ge=0)
    samples: int = Field(ge=1)


class DetectionConfig(TelemetryModel):
    alpha: float = Field(default=0.2, gt=0, le=1)
    warmup_samples: int = Field(default=12, ge=1)
    warning_z: float = Field(default=3.0, gt=0)
    critical_z: float = Field(default=5.0, gt=0)
    min_bps_delta: float = Field(default=100_000.0, ge=0)
    drop_rate_floor: float = Field(default=0.02, ge=0, le=1)
    error_rate_floor: float = Field(default=0.0, ge=0, le=1)
    min_sigma_bps: float = Field(default=10_000.0, gt=0)
    min_sigma_rate: float = Field(default=0.005, gt=0)

    @model_validator(mode="after")
    def _critical_above_warning(self) -> Self:
        if self.critical_z <= self.warning_z:
            raise ValueError(
                f"critical_z must exceed warning_z: {self.critical_z} <= {self.warning_z}"
            )
        return self


class AnomalySignal(TelemetryModel):
    dpid: DatapathId
    port_no: PortNumber
    metric: Metric
    observed_at: AwareDatetime
    value: float
    expected: float
    zscore: float
    severity: Severity


def update_baseline(baseline: Baseline | None, value: float, *, alpha: float) -> Baseline:
    if baseline is None:
        return Baseline(mean=value, variance=0.0, samples=1)
    delta = value - baseline.mean
    return Baseline(
        mean=baseline.mean + alpha * delta,
        variance=(1 - alpha) * (baseline.variance + alpha * delta * delta),
        samples=baseline.samples + 1,
    )


def score_metric(
    baseline: Baseline, value: float, metric: Metric, config: DetectionConfig
) -> tuple[float, Severity | None]:
    deviation = value - baseline.mean
    zscore = deviation / max(sqrt(baseline.variance), _sigma_floor(metric, config))
    if metric in THROUGHPUT_METRICS:
        return zscore, _throughput_severity(abs(deviation), abs(zscore), config)
    return zscore, _rate_severity(value, zscore, metric, config)


def detect_port_anomalies(
    baselines: Baselines, kpis: PortKpis, config: DetectionConfig
) -> tuple[dict[BaselineKey, Baseline], tuple[AnomalySignal, ...]]:
    updated = dict(baselines)
    if kpis.counter_reset:
        return updated, ()

    signals: list[AnomalySignal] = []
    for metric, value in _metric_values(kpis):
        if value is None:
            continue
        key: BaselineKey = (kpis.dpid, kpis.port_no, metric)
        baseline = updated.get(key)
        if baseline is not None and baseline.samples >= config.warmup_samples:
            zscore, severity = score_metric(baseline, value, metric, config)
            if severity is not None:
                signals.append(
                    AnomalySignal(
                        dpid=kpis.dpid,
                        port_no=kpis.port_no,
                        metric=metric,
                        observed_at=kpis.computed_at,
                        value=value,
                        expected=baseline.mean,
                        zscore=zscore,
                        severity=severity,
                    )
                )
        updated[key] = update_baseline(baseline, value, alpha=config.alpha)
    return updated, tuple(signals)


def _metric_values(kpis: PortKpis) -> tuple[tuple[Metric, Rate], ...]:
    return (
        ("rx_bps", kpis.rx_bps),
        ("tx_bps", kpis.tx_bps),
        ("drop_rate", kpis.drop_rate),
        ("error_rate", kpis.error_rate),
    )


def _sigma_floor(metric: Metric, config: DetectionConfig) -> float:
    if metric in THROUGHPUT_METRICS:
        return config.min_sigma_bps
    return config.min_sigma_rate


def _throughput_severity(
    deviation: float, zscore: float, config: DetectionConfig
) -> Severity | None:
    if deviation < config.min_bps_delta:
        return None
    return _severity_from_z(zscore, config)


def _rate_severity(
    value: float, zscore: float, metric: Metric, config: DetectionConfig
) -> Severity | None:
    by_z = _severity_from_z(zscore, config)
    if by_z is not None:
        return by_z
    if _rate_floor_reached(value, metric, config):
        return "warning"
    return None


def _rate_floor_reached(value: float, metric: Metric, config: DetectionConfig) -> bool:
    if metric == "drop_rate":
        return value >= config.drop_rate_floor
    return value > config.error_rate_floor


def _severity_from_z(zscore: float, config: DetectionConfig) -> Severity | None:
    if zscore >= config.critical_z:
        return "critical"
    if zscore >= config.warning_z:
        return "warning"
    return None
