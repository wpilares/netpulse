-- migrate:up
CREATE TABLE alerts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dpid numeric(20, 0) NOT NULL,
    port_no bigint NOT NULL,
    metric text NOT NULL,
    severity text NOT NULL,
    status text NOT NULL,
    opened_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    resolved_at timestamptz,
    acknowledged_at timestamptz,
    value double precision NOT NULL,
    expected double precision NOT NULL,
    zscore double precision NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT alerts_dpid_range CHECK (dpid >= 0 AND dpid < 18446744073709551616),
    CONSTRAINT alerts_port_no_range CHECK (port_no >= 0 AND port_no < 4294967296),
    CONSTRAINT alerts_metric_known CHECK (metric IN ('rx_bps', 'tx_bps', 'drop_rate', 'error_rate')),
    CONSTRAINT alerts_severity_known CHECK (severity IN ('warning', 'critical')),
    CONSTRAINT alerts_status_known CHECK (status IN ('open', 'resolved')),
    CONSTRAINT alerts_resolved_at_matches_status CHECK ((status = 'resolved') = (resolved_at IS NOT NULL))
);

CREATE UNIQUE INDEX alerts_open_key_idx ON alerts (dpid, port_no, metric) WHERE status = 'open';

CREATE INDEX alerts_status_opened_idx ON alerts (status, opened_at DESC);

-- migrate:down
DROP TABLE alerts;
