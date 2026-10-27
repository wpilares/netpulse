import { fireEvent, render, screen } from "@testing-library/react";
import { Inbox } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("shows the title and description", () => {
    render(<EmptyState icon={Inbox} title="No alerts" description="Everything is within thresholds." />);

    expect(screen.getByText("No alerts")).toBeInTheDocument();
    expect(screen.getByText("Everything is within thresholds.")).toBeInTheDocument();
  });

  it("renders an optional action", () => {
    const onClick = vi.fn();
    render(<EmptyState title="No ports" action={<Button onClick={onClick}>Refresh</Button>} />);

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
