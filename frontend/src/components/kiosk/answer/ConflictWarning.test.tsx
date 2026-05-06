import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConflictWarning } from "./ConflictWarning";

describe("ConflictWarning", () => {
  it("renders only when a conflict exists", () => {
    const { container } = render(<ConflictWarning warning={{ exists: false }} />);
    expect(container.firstChild).toBeNull();

    render(<ConflictWarning warning={{ exists: true, description: "날짜가 다릅니다." }} />);
    expect(screen.getByText("날짜가 다릅니다.")).toBeInTheDocument();
  });
});
