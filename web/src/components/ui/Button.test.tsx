import { fireEvent, render, screen } from "@testing-library/react";
import { Check } from "lucide-react";
import { createRef } from "react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";
import { Icon } from "./Icon";

describe("Button", () => {
  it("renders a non-submitting secondary medium button by default", () => {
    render(<Button>Save</Button>);

    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveAttribute("data-variant", "secondary");
    expect(button).toHaveAttribute("data-size", "md");
  });

  it("exposes the chosen variant and size", () => {
    render(
      <Button variant="primary" size="sm">
        Go
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Go" });
    expect(button).toHaveAttribute("data-variant", "primary");
    expect(button).toHaveAttribute("data-size", "sm");
  });

  it("calls onClick when pressed", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Press</Button>);

    fireEvent.click(screen.getByRole("button", { name: "Press" }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("is disabled and busy while loading and ignores clicks", () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Acknowledge
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Acknowledge" });
    fireEvent.click(button);

    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(onClick).not.toHaveBeenCalled();
  });

  it("renders an icon slot before the label", () => {
    render(<Button icon={<Icon icon={Check} label="Done" />}>Confirm</Button>);

    const button = screen.getByRole("button", { name: /Confirm/ });
    expect(button.querySelector("svg")).toHaveAttribute("aria-label", "Done");
  });

  it("forwards the ref to the underlying button", () => {
    const ref = createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Focus me</Button>);

    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });
});
