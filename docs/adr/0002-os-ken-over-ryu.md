# ADR 0002: OS-Ken as the SDN controller framework

- Status: Accepted
- Date: 2026-10-20

## Context

The controller must speak OpenFlow 1.3 to Open vSwitch, request port statistics periodically and expose them to the collector. Ryu is the best-known Python OpenFlow framework, but it is no longer maintained: its last PyPI release is 4.34 from May 2020. OS-Ken is the OpenStack fork of Ryu, maintained by the Neutron team and published regularly on PyPI.

Facts checked on PyPI for `os-ken` 4.2.2:

- Declared Python support stops at 3.13 (classifiers 3.11 to 3.13).
- The 4.x line no longer ships Ryu's `ryu-manager` CLI, the WSGI helpers or the bundled REST applications (`ofctl_rest`).
- Its `hub` defaults to native threads (`OSKEN_HUB_TYPE=native`) instead of eventlet monkey patching.

## Decision

- Use **OS-Ken 4.x** for the controller.
- Run it as a **standalone uv project on Python 3.13** with its own lockfile, outside the 3.14 workspace, so its dependency tree (oslo.config, ovs, ncclient, eventlet) never constrains the other services.
- Start applications through `AppManager.run_apps` from our own entry point instead of a manager CLI.
- Expose statistics with a small **stdlib WSGI server** (`wsgiref` with a threading mix-in) running in an OS-Ken hub thread. The REST handlers and the statistics store are framework-free, fully typed and unit tested; only `netpulse_controller.app` touches OS-Ken.
- Install a single table-miss flow with the `NORMAL` action so the emulated network forwards traffic without a custom L2 learning app. This is valid because the default topology is a loop-free tree.

## Consequences

- The controller follows a maintained upstream and works with current Python.
- mypy strict covers the controller; the untyped OS-Ken boundary is isolated to one module with a scoped override.
- When OS-Ken declares Python 3.14 support, the controller can join the workspace by moving it into the members list and dropping its lockfile.
- A topology with loops would need a proper forwarding app or STP before replacing the `NORMAL` flow.
