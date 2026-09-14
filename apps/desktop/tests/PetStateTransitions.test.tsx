import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PetCompanion } from "../src/components/Pet/PetCompanion";
import { PetState } from "@yana/shared-types";

describe("PetAnimationSystem - All 8 States", () => {
  const states: Array<{ state: PetState; expectedText: string }> = [
    { state: "idle", expectedText: "Online" },
    { state: "listening", expectedText: "Listening" },
    { state: "thinking", expectedText: "Thinking" },
    { state: "speaking", expectedText: "Speaking" },
    { state: "executing", expectedText: "Executing" },
    { state: "success", expectedText: "Success" },
    { state: "error", expectedText: "Attention" },
    { state: "offline", expectedText: "Offline" },
  ];

  states.forEach(({ state, expectedText }) => {
    it(`renders pet in ${state.toUpperCase()} state with label "${expectedText}"`, () => {
      const { unmount } = render(<PetCompanion state={state} />);
      expect(screen.getByTestId("pet-companion")).toHaveAttribute("data-state", state);
      expect(screen.getByText(expectedText)).toBeInTheDocument();
      unmount();
    });
  });

  it("handles uppercase state values gracefully", () => {
    render(<PetCompanion state={"SPEAKING" as any} />);
    expect(screen.getByTestId("pet-companion")).toHaveAttribute("data-state", "speaking");
    expect(screen.getByText("Speaking")).toBeInTheDocument();
  });

  it("renders with reduced opacity when offline", () => {
    render(<PetCompanion state="offline" />);
    expect(screen.getByTestId("pet-companion")).toHaveClass("opacity-60");
  });
});
