from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Link:
    source: str
    target: str


@dataclass(frozen=True, slots=True)
class TopologySpec:
    switches: tuple[str, ...]
    hosts: tuple[str, ...]
    links: tuple[Link, ...]

    def datapath_id(self, switch: str) -> str:
        return f"{self.switches.index(switch) + 1:016x}"


@dataclass(slots=True)
class _TreeBuilder:
    fanout: int
    switches: list[str] = field(default_factory=list)
    hosts: list[str] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)

    def add_switch(self, parent: str | None, depth: int) -> None:
        switch = f"s{len(self.switches) + 1}"
        self.switches.append(switch)
        if parent is not None:
            self.links.append(Link(parent, switch))
        for _ in range(self.fanout):
            if depth > 1:
                self.add_switch(switch, depth - 1)
            else:
                self.add_host(switch)

    def add_host(self, parent: str) -> None:
        host = f"h{len(self.hosts) + 1}"
        self.hosts.append(host)
        self.links.append(Link(parent, host))


def build_tree(*, depth: int, fanout: int) -> TopologySpec:
    if depth < 1 or fanout < 1:
        raise ValueError("depth and fanout must be positive")
    builder = _TreeBuilder(fanout=fanout)
    builder.add_switch(None, depth)
    return TopologySpec(
        switches=tuple(builder.switches),
        hosts=tuple(builder.hosts),
        links=tuple(builder.links),
    )
