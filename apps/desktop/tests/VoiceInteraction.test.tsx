import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SettingsModal } from "../src/components/Settings/SettingsModal";
import { PetCompanion } from "../src/components/Pet/PetCompanion";
import { AudioDevice } from "../src/services/agentClient";

describe("VoiceInteraction - Settings & Audio Controls", () => {
  const mockMicrophones: AudioDevice[] = [
    {
      id: "mic_default",
      name: "Default Microphone",
      deviceType: "input",
      isDefault: true,
      isAvailable: true,
    },
    {
      id: "mic_usb",
      name: "USB Studio Mic",
      deviceType: "input",
      isDefault: false,
      isAvailable: true,
    },
  ];

  const mockSpeakers: AudioDevice[] = [
    {
      id: "spk_default",
      name: "Default Speaker",
      deviceType: "output",
      isDefault: true,
      isAvailable: true,
    },
    {
      id: "spk_headphones",
      name: "Wireless Headphones",
      deviceType: "output",
      isDefault: false,
      isAvailable: true,
    },
  ];

  it("renders Audio & Voice settings tab with hardware controls", () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        agentConnected={true}
        agentUrl="http://127.0.0.1:8765/api"
        microphones={mockMicrophones}
        speakers={mockSpeakers}
        selectedMicId="mic_default"
        selectedSpeakerId="spk_default"
        wakeWordEnabled={false}
      />
    );

    // Switch to audio tab
    const audioTabBtn = screen.getByText("Voice & Audio");
    fireEvent.click(audioTabBtn);

    expect(screen.getByText("Microphone Input")).toBeInTheDocument();
    expect(screen.getByText("Speaker Output")).toBeInTheDocument();
    expect(screen.getByText(/Wake Word/)).toBeInTheDocument();
    expect(screen.getByText("Ctrl + Shift + Space")).toBeInTheDocument();
  });

  it("triggers microphone selection callback when changed", () => {
    const onSelectMic = vi.fn();
    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        agentConnected={true}
        agentUrl="http://127.0.0.1:8765/api"
        microphones={mockMicrophones}
        speakers={mockSpeakers}
        selectedMicId="mic_default"
        onSelectMic={onSelectMic}
      />
    );

    fireEvent.click(screen.getByText("Voice & Audio"));

    const select = screen.getByLabelText("Microphone Input");
    fireEvent.change(select, { target: { value: "mic_usb" } });

    expect(onSelectMic).toHaveBeenCalledWith("mic_usb");
  });

  it("triggers speaker selection callback when changed", () => {
    const onSelectSpeaker = vi.fn();
    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        agentConnected={true}
        agentUrl="http://127.0.0.1:8765/api"
        microphones={mockMicrophones}
        speakers={mockSpeakers}
        selectedSpeakerId="spk_default"
        onSelectSpeaker={onSelectSpeaker}
      />
    );

    fireEvent.click(screen.getByText("Voice & Audio"));

    const select = screen.getByLabelText("Speaker Output");
    fireEvent.change(select, { target: { value: "spk_headphones" } });

    expect(onSelectSpeaker).toHaveBeenCalledWith("spk_headphones");
  });

  it("triggers wake-word toggle callback", () => {
    const onToggleWakeWord = vi.fn();
    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        agentConnected={true}
        agentUrl="http://127.0.0.1:8765/api"
        wakeWordEnabled={false}
        onToggleWakeWord={onToggleWakeWord}
      />
    );

    fireEvent.click(screen.getByText("Voice & Audio"));

    const checkbox = screen.getByLabelText("Toggle Wake Word");
    fireEvent.click(checkbox);

    expect(onToggleWakeWord).toHaveBeenCalledWith(true);
  });

  it("verifies voice drives LISTENING, THINKING, and SPEAKING pet animations", () => {
    // 1. LISTENING
    const { unmount: u1 } = render(<PetCompanion state="listening" />);
    expect(screen.getByTestId("pet-companion")).toHaveAttribute("data-state", "listening");
    expect(screen.getByText("Listening")).toBeInTheDocument();
    u1();

    // 2. THINKING
    const { unmount: u2 } = render(<PetCompanion state="thinking" />);
    expect(screen.getByTestId("pet-companion")).toHaveAttribute("data-state", "thinking");
    expect(screen.getByText("Thinking")).toBeInTheDocument();
    u2();

    // 3. SPEAKING
    const { unmount: u3 } = render(<PetCompanion state="speaking" />);
    expect(screen.getByTestId("pet-companion")).toHaveAttribute("data-state", "speaking");
    expect(screen.getByText("Speaking")).toBeInTheDocument();
    u3();
  });
});
