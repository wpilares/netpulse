import { render, screen } from "@testing-library/react";
import { Activity } from "lucide-react";
import { describe, expect, it } from "vitest";
import { Icon } from "./Icon";

describe("Icon", () => {
  it("is decorative without a label", () => {
    const { container } = render(<Icon icon={Activity} />);

    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).not.toHaveAttribute("role");
  });

  it("becomes a named image with a label", () => {
    render(<Icon icon={Activity} label="Activity" />);

    expect(screen.getByRole("img", { name: "Activity" })).toBeInTheDocument();
  });

  it("maps the size token to pixels", () => {
    const { container } = render(<Icon icon={Activity} size="lg" />);

    expect(container.querySelector("svg")).toHaveAttribute("width", "20");
  });
});
