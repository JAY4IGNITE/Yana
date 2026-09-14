import React from "react";
import { PetState, PetMood } from "@yana/shared-types";

interface PetCompanionProps {
  state: PetState;
  mood?: PetMood;
  scale?: "small" | "medium" | "large";
  showBadge?: boolean;
  onPetClick?: () => void;
}

export const PetCompanion: React.FC<PetCompanionProps> = ({
  state,
  mood = "happy",
  scale = "medium",
  showBadge = true,
  onPetClick,
}) => {
  // Normalize state to lowercase for robust matching
  const normalizedState = (state || "idle").toLowerCase() as PetState;

  // Determine aura colors, eye colors, and state labels for all 8 states
  const getStateVisuals = () => {
    switch (normalizedState) {
      case "listening":
        return {
          aura: "#38BDF8", // Cyan
          eye: "#0284C7",
          shell: "#1E293B",
          visorBorder: "#38BDF8",
          label: "Listening",
        };
      case "thinking":
        return {
          aura: "#818CF8", // Indigo
          eye: "#6366F1",
          shell: "#1E293B",
          visorBorder: "#818CF8",
          label: "Thinking",
        };
      case "speaking":
        return {
          aura: "#06B6D4", // Electric Cyan
          eye: "#0891B2",
          shell: "#1E293B",
          visorBorder: "#22D3EE",
          label: "Speaking",
        };
      case "executing":
        return {
          aura: "#F59E0B", // Amber
          eye: "#D97706",
          shell: "#1E293B",
          visorBorder: "#FBBF24",
          label: "Executing",
        };
      case "success":
        return {
          aura: "#10B981", // Emerald
          eye: "#059669",
          shell: "#1E293B",
          visorBorder: "#34D399",
          label: "Success",
        };
      case "error":
        return {
          aura: "#F43F5E", // Rose/Red
          eye: "#E11D48",
          shell: "#1E293B",
          visorBorder: "#FB7185",
          label: "Attention",
        };
      case "offline":
      case "sleeping":
        return {
          aura: "#334155", // Slate/Muted
          eye: "#475569",
          shell: "#0F172A",
          visorBorder: "#334155",
          label: "Offline",
        };
      case "idle":
      default:
        return {
          aura: "#38BDF8", // Futuristic Cyan
          eye: "#38BDF8",
          shell: "#1E293B",
          visorBorder: "rgba(56, 189, 248, 0.4)",
          label: "Online",
        };
    }
  };

  const visuals = getStateVisuals();

  // Dimensions based on scale
  const sizeMap = {
    small: { container: "w-24 h-24", svg: "w-20 h-20" },
    medium: { container: "w-32 h-32", svg: "w-28 h-28" },
    large: { container: "w-40 h-40", svg: "w-36 h-36" },
  };
  const dimensions = sizeMap[scale] || sizeMap.medium;

  const isOffline = normalizedState === "offline" || normalizedState === "sleeping";
  const isSpeaking = normalizedState === "speaking";
  const isThinking = normalizedState === "thinking";
  const isListening = normalizedState === "listening";
  const isExecuting = normalizedState === "executing";

  return (
    <div
      data-testid="pet-companion"
      data-state={normalizedState}
      className={`flex flex-col items-center justify-center select-none cursor-pointer group transition-opacity duration-500 ${
        isOffline ? "opacity-60" : "opacity-100"
      }`}
      onClick={onPetClick}
      role="button"
      tabIndex={0}
      title={`YANA: ${visuals.label} (${normalizedState})`}
    >
      {/* Floating Robot Shell Container */}
      <div className={`relative ${dimensions.container} flex items-center justify-center animate-float`}>
        {/* Glowing Luminescent Aura */}
        <div
          data-testid="pet-aura"
          className="absolute inset-0 rounded-full blur-xl animate-pulse-glow transition-all duration-700"
          style={{
            backgroundColor: visuals.aura,
            opacity: isOffline ? 0.15 : 0.45,
          }}
        />

        {/* Robotic Pet Character SVG */}
        <svg
          viewBox="0 0 100 100"
          className={`${dimensions.svg} relative z-10 drop-shadow-2xl transition-transform duration-300 group-hover:scale-105`}
        >
          <defs>
            {/* Shell Body Gradient */}
            <linearGradient id="yanaShellGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#334155" />
              <stop offset="40%" stopColor="#1E293B" />
              <stop offset="100%" stopColor="#0F172A" />
            </linearGradient>

            {/* Dark Visor Screen */}
            <linearGradient id="yanaVisorGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#090D16" />
              <stop offset="100%" stopColor="#020617" />
            </linearGradient>

            {/* Glow Filter */}
            <filter id="eyeGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="1.8" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Left Audio Sensor / Antenna */}
          <path
            d="M 28 26 Q 20 12 12 18 Q 20 28 30 32"
            fill="#1E293B"
            stroke={visuals.visorBorder}
            strokeWidth="1.5"
            className="transition-colors duration-500"
          />
          {/* Right Audio Sensor / Antenna */}
          <path
            d="M 72 26 Q 80 12 88 18 Q 80 28 70 32"
            fill="#1E293B"
            stroke={visuals.visorBorder}
            strokeWidth="1.5"
            className="transition-colors duration-500"
          />

          {/* Antenna Tip Glow Orbs */}
          <circle
            cx="14"
            cy="16"
            r="2"
            fill={visuals.aura}
            className={isListening ? "animate-ping" : ""}
          />
          <circle
            cx="86"
            cy="16"
            r="2"
            fill={visuals.aura}
            className={isListening ? "animate-ping" : ""}
          />

          {/* Robotic Body Chassis */}
          <rect
            x="14"
            y="18"
            width="72"
            height="70"
            rx="35"
            fill="url(#yanaShellGrad)"
            stroke="rgba(255, 255, 255, 0.14)"
            strokeWidth="1.5"
          />

          {/* Visor Bezel */}
          <rect
            x="22"
            y="28"
            width="56"
            height="46"
            rx="20"
            fill="url(#yanaVisorGrad)"
            stroke={visuals.visorBorder}
            strokeWidth="1.2"
            className="transition-colors duration-500"
          />

          {/* Thinking: Visor Scan Line Sweep */}
          {isThinking && (
            <g clipPath="url(#visorClip)">
              <line
                x1="24"
                y1="32"
                x2="76"
                y2="32"
                stroke={visuals.aura}
                strokeWidth="1.5"
                opacity="0.75"
                className="animate-scan"
              />
            </g>
          )}

          {/* Eye Expressions by State */}
          {isOffline ? (
            /* OFFLINE / SLEEPING: Closed Resting Curves */
            <g stroke={visuals.eye} strokeWidth="2.5" strokeLinecap="round" fill="none" opacity="0.6">
              <path d="M 32 50 Q 38 56 44 50" />
              <path d="M 56 50 Q 62 56 68 50" />
            </g>
          ) : normalizedState === "error" ? (
            /* ERROR: Concerned Crosses */
            <g stroke={visuals.eye} strokeWidth="2.5" strokeLinecap="round">
              <line x1="34" y1="46" x2="42" y2="54" />
              <line x1="42" y1="46" x2="34" y2="54" />
              <line x1="58" y1="46" x2="66" y2="54" />
              <line x1="66" y1="46" x2="58" y2="54" />
            </g>
          ) : normalizedState === "success" ? (
            /* SUCCESS: Cheerful Crescent Happy Eyes */
            <g stroke={visuals.eye} strokeWidth="3" strokeLinecap="round" fill="none">
              <path d="M 32 52 Q 38 44 44 52" />
              <path d="M 56 52 Q 62 44 68 52" />
            </g>
          ) : (
            /* ACTIVE / LISTENING / THINKING / SPEAKING / EXECUTING: Expressive Glowing Ovals */
            <g filter="url(#eyeGlow)">
              <ellipse
                cx="38"
                cy={isThinking ? "48" : "50"}
                rx={isListening ? "5.5" : "5"}
                ry={isListening ? "7.5" : isThinking ? "4" : "5.5"}
                fill={visuals.eye}
                className="transition-all duration-300"
              />
              <ellipse
                cx="62"
                cy={isThinking ? "48" : "50"}
                rx={isListening ? "5.5" : "5"}
                ry={isListening ? "7.5" : isThinking ? "4" : "5.5"}
                fill={visuals.eye}
                className="transition-all duration-300"
              />
              {/* Highlight sparkles */}
              <circle cx="40" cy="48" r="1.5" fill="#ffffff" opacity="0.85" />
              <circle cx="64" cy="48" r="1.5" fill="#ffffff" opacity="0.85" />
            </g>
          )}

          {/* Blushing Cheeks for Happy/Success */}
          {(mood === "happy" || normalizedState === "success") && !isOffline && (
            <g opacity="0.55">
              <ellipse cx="28" cy="58" rx="3.5" ry="2" fill="#F43F5E" />
              <ellipse cx="72" cy="58" rx="3.5" ry="2" fill="#F43F5E" />
            </g>
          )}

          {/* Mouth / Voice Audio Waveform Area */}
          {isSpeaking ? (
            /* SPEAKING: Animated soundwave bars */
            <g fill={visuals.eye} opacity="0.9">
              <rect x="42" y="60" width="2" height="6" rx="1" className="animate-wave" />
              <rect x="46" y="58" width="2" height="10" rx="1" className="animate-wave" style={{ animationDelay: "0.15s" }} />
              <rect x="50" y="57" width="2" height="12" rx="1" className="animate-wave" style={{ animationDelay: "0.3s" }} />
              <rect x="54" y="58" width="2" height="10" rx="1" className="animate-wave" style={{ animationDelay: "0.45s" }} />
              <rect x="58" y="60" width="2" height="6" rx="1" className="animate-wave" style={{ animationDelay: "0.6s" }} />
            </g>
          ) : isExecuting ? (
            /* EXECUTING: Dynamic activity pulse line */
            <line
              x1="43"
              y1="62"
              x2="57"
              y2="62"
              stroke={visuals.eye}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeDasharray="3 2"
              className="animate-pulse"
            />
          ) : normalizedState === "success" ? (
            /* SUCCESS: Smiling mouth */
            <path
              d="M 43 60 Q 50 67 57 60"
              stroke={visuals.eye}
              strokeWidth="2.2"
              strokeLinecap="round"
              fill="none"
            />
          ) : isOffline ? (
            <line x1="47" y1="62" x2="53" y2="62" stroke="#475569" strokeWidth="1.5" strokeLinecap="round" />
          ) : (
            /* IDLE: Subtle calm mouth dot */
            <ellipse cx="50" cy="62" rx="2" ry="1.5" fill={visuals.eye} opacity="0.75" />
          )}
        </svg>
      </div>

      {/* Optional Compact Status Badge */}
      {showBadge && (
        <div
          data-testid="pet-badge"
          className="mt-1 flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-slate-950/85 border border-white/10 shadow-md text-[10px] font-medium tracking-wide text-slate-300 backdrop-blur-sm"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${isOffline ? "bg-slate-500" : "animate-ping"}`}
            style={{ backgroundColor: visuals.aura }}
          />
          <span>{visuals.label}</span>
        </div>
      )}
    </div>
  );
};
