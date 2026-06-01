import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProcedureSteps } from "./ProcedureSteps";

describe("ProcedureSteps", () => {
  it("renders numbered steps and hides empty steps", () => {
    render(<ProcedureSteps steps={["포털 로그인", "신청서 작성"]} />);

    expect(screen.getByText("포털 로그인")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("renders the no-procedure message after streaming completes", () => {
    render(<ProcedureSteps steps={[]} />);

    expect(screen.getByText("확인된 절차가 없습니다.")).toBeInTheDocument();
  });
});
