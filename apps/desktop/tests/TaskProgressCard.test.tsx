import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  TaskProgressCard,
  ActiveTaskState,
} from "../src/components/Companion/TaskProgressCard";

describe("TaskProgressCard Component", () => {
  const sampleExecutingTask: ActiveTaskState = {
    id: "task-100",
    goal: "Run agent diagnostic mock sequence",
    status: "executing",
    progress: 0.5,
    currentStep: 2,
    totalSteps: 3,
    stepDescription: "Executing step 2: Wait for sensor stabilization",
    steps: [
      {
        version: "1.0.0",
        id: "step-1",
        timestamp: new Date().toISOString(),
        type: "task_step",
        taskId: "task-100",
        stepId: "s1",
        stepNumber: 1,
        toolName: "mock.action",
        description: "Initialize telemetry check",
        status: "completed",
        verified: true,
      },
      {
        version: "1.0.0",
        id: "step-2",
        timestamp: new Date().toISOString(),
        type: "task_step",
        taskId: "task-100",
        stepId: "s2",
        stepNumber: 2,
        toolName: "mock.wait",
        description: "Wait for sensor stabilization",
        status: "executing",
      },
    ],
  };

  it("renders task goal, status badge, and progress percentage", () => {
    render(<TaskProgressCard task={sampleExecutingTask} onCancel={vi.fn()} />);

    expect(screen.getByTestId("task-progress-card")).toBeInTheDocument();
    expect(screen.getByText("Run agent diagnostic mock sequence")).toBeInTheDocument();
    expect(screen.getByText("Executing")).toBeInTheDocument();
    expect(screen.getByText("(2/3)")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(
      screen.getByText("Executing step 2: Wait for sensor stabilization")
    ).toBeInTheDocument();
  });

  it("renders steps with tool names and descriptions", () => {
    render(<TaskProgressCard task={sampleExecutingTask} onCancel={vi.fn()} />);

    expect(screen.getByText("Initialize telemetry check")).toBeInTheDocument();
    expect(screen.getByText("mock.action")).toBeInTheDocument();
    expect(screen.getByText("mock.wait")).toBeInTheDocument();
  });

  it("calls onCancel when cancel button is clicked", () => {
    const handleCancel = vi.fn();
    render(
      <TaskProgressCard
        task={sampleExecutingTask}
        onCancel={handleCancel}
      />
    );

    const cancelBtn = screen.getByTestId("cancel-task-button");
    expect(cancelBtn).toBeInTheDocument();
    fireEvent.click(cancelBtn);
    expect(handleCancel).toHaveBeenCalledTimes(1);
  });

  it("renders completed status and dismiss button on completion", () => {
    const handleDismiss = vi.fn();
    const completedTask: ActiveTaskState = {
      ...sampleExecutingTask,
      status: "completed",
      progress: 1.0,
      stepDescription: "All steps completed successfully",
    };

    render(
      <TaskProgressCard
        task={completedTask}
        onCancel={vi.fn()}
        onDismiss={handleDismiss}
      />
    );

    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.queryByTestId("cancel-task-button")).not.toBeInTheDocument();

    const dismissBtn = screen.getByText("Dismiss");
    expect(dismissBtn).toBeInTheDocument();
    fireEvent.click(dismissBtn);
    expect(handleDismiss).toHaveBeenCalledTimes(1);
  });

  it("renders error alert message when task fails", () => {
    const failedTask: ActiveTaskState = {
      ...sampleExecutingTask,
      status: "failed",
      error: "Maximum retry limit exceeded for step 1",
    };

    render(<TaskProgressCard task={failedTask} />);

    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(
      screen.getByText("Maximum retry limit exceeded for step 1")
    ).toBeInTheDocument();
  });
});
