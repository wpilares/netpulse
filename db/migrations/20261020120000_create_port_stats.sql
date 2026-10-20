-- migrate:up
CREATE TABLE port_stats (
    time timestamptz NOT NULL,
    dpid numeric(20, 0) NOT NULL,
    port_no bigint NOT NULL,
    rx_packets bigint,
    tx_packets bigint,
    rx_bytes bigint,
    tx_bytes bigint,
    rx_dropped bigint,
    tx_dropped bigint,
    rx_errors bigint,
    tx_errors bigint,
    duration_sec bigint,
    CONSTRAINT port_stats_dpid_range CHECK (dpid >= 0 AND dpid < 18446744073709551616),
    CONSTRAINT port_stats_port_no_range CHECK (port_no >= 0 AND port_no < 4294967296),
    CONSTRAINT port_stats_pkey PRIMARY KEY (dpid, port_no, time)
);

SELECT create_hypertable('port_stats', by_range('time', INTERVAL '1 day'));

ALTER TABLE port_stats SET (
    timescaledb.enable_columnstore,
    timescaledb.segmentby = 'dpid, port_no',
    timescaledb.orderby = 'time DESC'
);

CALL add_columnstore_policy('port_stats', after => INTERVAL '1 day');

SELECT add_retention_policy('port_stats', drop_after => INTERVAL '7 days');

-- migrate:down
DROP TABLE port_stats;
