import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ThemeProvider } from "../theme/ThemeProvider";
import { AppShell } from "./AppShell";

const renderShell = (version: string | null = "1.1.0") =>
  render(
    <ThemeProvider>
      <AppShell
        status={<output>API online</output>}
        version={version}
        summary={<section aria-label="Summary">summary</section>}
        alerts={<section aria-label="Alerts">alerts</section>}
        topology={<section aria-label="Topology">topology</section>}
        ports={<section aria-label="Ports">ports</section>}
      />
    </ThemeProvider>,
  );

describe("AppShell", () => {
  afterEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("exposes header, main and footer landmarks with the product name", () => {
    renderShell();

    const header = screen.getByRole("banner");
    expect(within(header).getByRole("heading", { level: 1 })).toHaveTextContent("NetPulse");
    expect(within(header).getByRole("status")).toHaveTextContent("API online");
    expect(within(header).getByRole("radiogroup", { name: "Theme" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toHaveTextContent("API v1.1.0");
  });

  it("places every panel inside the main landmark in reading order", () => {
    renderShell(null);

    const main = screen.getByRole("main");
    expect(
      within(main)
        .getAllByRole("region")
        .map((region) => region.getAttribute("aria-label")),
    ).toEqual(["Summary", "Alerts", "Topology", "Ports"]);
    expect(screen.getByRole("contentinfo")).not.toHaveTextContent("API v");
  });
});
