from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from netpulse_core.anomaly import (
    METRICS,
    AnomalySignal,
    Baseline,
    BaselineKey,
    DetectionConfig,
    Metric,
    detect_port_anomalies,
    score_metric,
    update_baseline,
)
from netpulse_core.kpi import PortKpis

T0 = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
WARM = 12


def _kpis(
    *,
    dpid: int = 1,
    port_no: int = 1,
    rx_bps: float | None = None,
    tx_bps: float | None = None,
    drop_rate: float | None = None,
    error_rate: float | None = None,
    counter_reset: bool = False,
) -> PortKpis:
    return PortKpis(
        dpid=dpid,
        port_no=port_no,
        computed_at=T0,
        interval_seconds=5.0,
        rx_bps=rx_bps,
        tx_bps=tx_bps,
        rx_pps=None,
        tx_pps=None,
        drop_rate=drop_rate,
        error_rate=error_rate,
        utilization=None,
        counter_reset=counter_reset,
    )


def _baseline(mean: float, variance: float = 0.0, samples: int = WARM) -> Baseline:
    return Baseline(mean=mean, variance=variance, samples=samples)


def _key(metric: Metric, *, dpid: int = 1, port_no: int = 1) -> BaselineKey:
    return (dpid, port_no, metric)


CONFIG = DetectionConfig()


def test_metrics_cover_throughput_and_quality() -> None:
    assert METRICS == ("rx_bps", "tx_bps", "drop_rate", "error_rate")


def test_first_sample_seeds_baseline() -> None:
    assert update_baseline(None, 100.0, alpha=0.2) == Baseline(mean=100.0, variance=0.0, samples=1)


def test_ewma_update_matches_hand_computed_values() -> None:
    seeded = update_baseline(None, 100.0, alpha=0.5)

    second = update_baseline(seeded, 200.0, alpha=0.5)
    third = update_baseline(second, 100.0, alpha=0.5)

    assert second == Baseline(mean=150.0, variance=2_500.0, samples=2)
    assert third.mean == pytest.approx(125.0)
    assert third.variance == pytest.approx(1_875.0)
    assert third.samples == 3


def test_config_defaults() -> None:
    assert CONFIG.alpha == 0.2
    assert CONFIG.warmup_samples == 12
    assert CONFIG.warning_z == 3.0
    assert CONFIG.critical_z == 5.0
    assert CONFIG.min_bps_delta == 100_000.0
    assert CONFIG.drop_rate_floor == 0.02
    assert CONFIG.error_rate_floor == 0.0
    assert CONFIG.min_sigma_bps == 10_000.0
    assert CONFIG.min_sigma_rate == 0.005


@pytest.mark.parametrize(
    "overrides",
    [
        {"alpha": 0.0},
        {"alpha": 1.5},
        {"warmup_samples": 0},
        {"warning_z": 0.0},
        {"critical_z": 3.0},
        {"warning_z": 6.0},
        {"min_bps_delta": -1.0},
        {"drop_rate_floor": 1.5},
        {"min_sigma_bps": 0.0},
        {"min_sigma_rate": 0.0},
    ],
)
def test_invalid_config_is_rejected(overrides: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        DetectionConfig.model_validate(overrides)


def test_flat_throughput_baseline_uses_sigma_floor() -> None:
    zscore, severity = score_metric(_baseline(1_000_000.0), 2_000_000.0, "rx_bps", CONFIG)

    assert zscore == pytest.approx(100.0)
    assert severity == "critical"


def test_throughput_drop_counts_as_anomaly() -> None:
    zscore, severity = score_metric(_baseline(1_000_000.0), 0.0, "tx_bps", CONFIG)

    assert zscore == pytest.approx(-100.0)
    assert severity == "critical"


def test_throughput_warning_between_thresholds() -> None:
    baseline = _baseline(1_000_000.0, variance=100_000.0**2)

    zscore, severity = score_metric(baseline, 1_400_000.0, "rx_bps", CONFIG)

    assert zscore == pytest.approx(4.0)
    assert severity == "warning"


def test_throughput_wiggle_below_absolute_floor_is_ignored() -> None:
    zscore, severity = score_metric(_baseline(1_000_000.0), 1_050_000.0, "rx_bps", CONFIG)

    assert zscore == pytest.approx(5.0)
    assert severity is None


def test_throughput_within_noise_is_ignored() -> None:
    baseline = _baseline(1_000_000.0, variance=200_000.0**2)

    zscore, severity = score_metric(baseline, 1_300_000.0, "rx_bps", CONFIG)

    assert zscore == pytest.approx(1.5)
    assert severity is None


def test_drop_rate_floor_warns_even_with_small_z() -> None:
    baseline = _baseline(0.019, variance=0.1**2)

    zscore, severity = score_metric(baseline, 0.02, "drop_rate", CONFIG)

    assert zscore == pytest.approx(0.01)
    assert severity == "warning"


def test_drop_rate_below_floor_and_noise_is_ignored() -> None:
    zscore, severity = score_metric(_baseline(0.0), 0.01, "drop_rate", CONFIG)

    assert zscore == pytest.approx(2.0)
    assert severity is None


def test_drop_rate_far_above_baseline_is_critical() -> None:
    zscore, severity = score_metric(_baseline(0.0), 0.05, "drop_rate", CONFIG)

    assert zscore == pytest.approx(10.0)
    assert severity == "critical"


def test_rate_decrease_is_not_an_anomaly() -> None:
    zscore, severity = score_metric(_baseline(0.5), 0.0, "drop_rate", CONFIG)

    assert zscore == pytest.approx(-100.0)
    assert severity is None


def test_any_error_rate_is_at_least_warning() -> None:
    zscore, severity = score_metric(_baseline(0.0), 0.001, "error_rate", CONFIG)

    assert zscore == pytest.approx(0.2)
    assert severity == "warning"


def test_zero_error_rate_is_not_an_anomaly() -> None:
    assert score_metric(_baseline(0.0), 0.0, "error_rate", CONFIG) == (0.0, None)


def test_warmup_only_updates_baselines() -> None:
    config = DetectionConfig(warmup_samples=2)
    kpis = _kpis(rx_bps=5_000_000.0)

    first, first_signals = detect_port_anomalies({}, kpis, config)
    second, second_signals = detect_port_anomalies(first, kpis, config)
    third, third_signals = detect_port_anomalies(second, _kpis(rx_bps=50_000_000.0), config)

    assert first == {_key("rx_bps"): Baseline(mean=5_000_000.0, variance=0.0, samples=1)}
    assert first_signals == ()
    assert second[_key("rx_bps")].samples == 2
    assert second_signals == ()
    assert third[_key("rx_bps")].samples == 3
    assert [signal.severity for signal in third_signals] == ["critical"]


def test_spike_is_scored_against_previous_baseline_then_updated() -> None:
    baselines = {_key("rx_bps"): _baseline(1_000_000.0)}
    kpis = _kpis(rx_bps=2_000_000.0)

    updated, signals = detect_port_anomalies(baselines, kpis, CONFIG)

    assert signals == (
        AnomalySignal(
            dpid=1,
            port_no=1,
            metric="rx_bps",
            observed_at=T0,
            value=2_000_000.0,
            expected=1_000_000.0,
            zscore=100.0,
            severity="critical",
        ),
    )
    assert updated[_key("rx_bps")].mean == pytest.approx(1_200_000.0)
    assert updated[_key("rx_bps")].variance == pytest.approx(1.6e11)
    assert updated[_key("rx_bps")].samples == WARM + 1
    assert baselines[_key("rx_bps")] == _baseline(1_000_000.0)


def test_counter_reset_skips_scoring_and_updates() -> None:
    baselines = {_key("rx_bps"): _baseline(1_000_000.0)}
    kpis = _kpis(rx_bps=50_000_000.0, drop_rate=0.5, counter_reset=True)

    updated, signals = detect_port_anomalies(baselines, kpis, CONFIG)

    assert updated == baselines
    assert signals == ()


def test_unknown_metrics_are_skipped() -> None:
    kpis = _kpis(tx_bps=1_000.0)

    updated, signals = detect_port_anomalies({}, kpis, CONFIG)

    assert set(updated) == {_key("tx_bps")}
    assert signals == ()


def test_other_ports_are_preserved_and_signals_follow_metric_order() -> None:
    other = _key("rx_bps", dpid=2, port_no=7)
    baselines = {
        other: _baseline(5.0),
        _key("rx_bps"): _baseline(1_000_000.0),
        _key("drop_rate"): _baseline(0.0),
        _key("error_rate"): _baseline(0.0),
    }
    kpis = _kpis(rx_bps=3_000_000.0, drop_rate=0.03, error_rate=0.0)

    updated, signals = detect_port_anomalies(baselines, kpis, CONFIG)

    assert updated[other] == _baseline(5.0)
    assert [(signal.metric, signal.severity) for signal in signals] == [
        ("rx_bps", "critical"),
        ("drop_rate", "critical"),
    ]
