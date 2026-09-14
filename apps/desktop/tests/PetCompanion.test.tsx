import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PetCompanion } from "../src/components/Pet/PetCompanion";

describe("PetCompanion Component", () => {
  it("renders idle state by default", () => {
    render(<PetCompanion state="idle" />);
    expect(screen.getByTestId("pet-companion")).toBeInTheDocument();
    expect(screen.getByText("Online")).toBeInTheDocument();
  });

  it("updates text and badge when state changes to executing", () => {
    render(<PetCompanion state="executing" />);
    expect(screen.getByText("Executing")).toBeInTheDocument();
  });

  it("updates text when state is sleeping", () => {
    render(<PetCompanion state="sleeping" />);
    expect(screen.getByText("Offline")).toBeInTheDocument();
  });

  it("fires onPetClick callback when clicked", () => {
    const handleClick = vi.fn();
    render(<PetCompanion state="idle" onPetClick={handleClick} />);
    fireEvent.click(screen.getByTestId("pet-companion"));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
