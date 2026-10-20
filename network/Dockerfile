FROM debian:trixie-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        iperf3 \
        iproute2 \
        iputils-ping \
        mininet \
        openvswitch-switch \
        procps \
        python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/netpulse
COPY src/netpulse_network netpulse_network
COPY entrypoint.sh /usr/local/bin/netpulse-network
RUN chmod 0755 /usr/local/bin/netpulse-network
ENV PYTHONPATH=/opt/netpulse \
    PYTHONUNBUFFERED=1
STOPSIGNAL SIGTERM
ENTRYPOINT ["netpulse-network"]
