-- migrate:up
CREATE SEQUENCE alerts_seq;

ALTER TABLE alerts ADD COLUMN seq bigint NOT NULL DEFAULT nextval('alerts_seq');

CREATE UNIQUE INDEX alerts_seq_idx ON alerts (seq);

CREATE TABLE alert_baselines (
    dpid numeric(20, 0) NOT NULL,
    port_no bigint NOT NULL,
    metric text NOT NULL,
    mean double precision NOT NULL,
    variance double precision NOT NULL,
    samples integer NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dpid, port_no, metric),
    CONSTRAINT alert_baselines_dpid_range CHECK (dpid >= 0 AND dpid < 18446744073709551616),
    CONSTRAINT alert_baselines_port_no_range CHECK (port_no >= 0 AND port_no < 4294967296),
    CONSTRAINT alert_baselines_metric_known
        CHECK (metric IN ('rx_bps', 'tx_bps', 'drop_rate', 'error_rate')),
    CONSTRAINT alert_baselines_variance_non_negative CHECK (variance >= 0),
    CONSTRAINT alert_baselines_samples_positive CHECK (samples >= 1)
);

-- migrate:down
DROP TABLE alert_baselines;

DROP INDEX alerts_seq_idx;

ALTER TABLE alerts DROP COLUMN seq;

DROP SEQUENCE alerts_seq;
