import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ErrorState } from "./ErrorState";

describe("ErrorState", () => {
  it("announces the error with a default title", () => {
    render(<ErrorState description="The API is unavailable." />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong");
    expect(alert).toHaveTextContent("The API is unavailable.");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("offers a retry action when a handler is given", () => {
    const onRetry = vi.fn();
    render(<ErrorState title="Alerts failed to load" onRetry={onRetry} />);

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("alert")).toHaveTextContent("Alerts failed to load");
  });
});
