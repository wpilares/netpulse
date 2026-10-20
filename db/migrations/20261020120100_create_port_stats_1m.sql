-- migrate:up
CREATE MATERIALIZED VIEW port_stats_1m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
    time_bucket(INTERVAL '1 minute', time) AS bucket,
    dpid,
    port_no,
    last(rx_packets, time) AS rx_packets,
    last(tx_packets, time) AS tx_packets,
    last(rx_bytes, time) AS rx_bytes,
    last(tx_bytes, time) AS tx_bytes,
    last(rx_dropped, time) AS rx_dropped,
    last(tx_dropped, time) AS tx_dropped,
    last(rx_errors, time) AS rx_errors,
    last(tx_errors, time) AS tx_errors,
    last(duration_sec, time) AS duration_sec,
    count(*) AS samples
FROM port_stats
GROUP BY bucket, dpid, port_no
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'port_stats_1m',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);

SELECT add_retention_policy('port_stats_1m', drop_after => INTERVAL '90 days');

-- migrate:down
DROP MATERIALIZED VIEW port_stats_1m;
