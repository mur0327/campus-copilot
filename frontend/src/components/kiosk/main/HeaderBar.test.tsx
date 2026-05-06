import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HeaderBar } from "./HeaderBar";

describe("HeaderBar", () => {
  it("renders university and service name", () => {
    render(<HeaderBar />);

    expect(screen.getByText("호남대학교")).toBeInTheDocument();
    expect(screen.getByText("Campus Copilot")).toBeInTheDocument();
  });
});
