#!/bin/sh
set -eu

OVS_CTL=/usr/share/openvswitch/scripts/ovs-ctl

"$OVS_CTL" start --no-ovs-vswitchd --system-id=random
if [ "${NETPULSE_NETWORK_OVS_DATAPATH:-user}" = "kernel" ]; then
    "$OVS_CTL" start --no-ovsdb-server
else
    ovs-vswitchd --pidfile --detach --log-file
fi

exec python3 -m netpulse_network
