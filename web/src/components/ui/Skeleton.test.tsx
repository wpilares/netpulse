import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Skeleton } from "./Skeleton";

describe("Skeleton", () => {
  it("is hidden from assistive technology and sized by props", () => {
    const { container } = render(<Skeleton width="8rem" height={16} />);

    const skeleton = container.firstElementChild;
    expect(skeleton).toHaveAttribute("aria-hidden", "true");
    expect(skeleton).toHaveAttribute("style", "width: 8rem; height: 16px;");
    expect(skeleton).toHaveAttribute("data-rounded", "md");
  });

  it("exposes the rounding variant", () => {
    const { container } = render(<Skeleton width={24} height={24} rounded="full" />);

    expect(container.firstElementChild).toHaveAttribute("data-rounded", "full");
  });
});
