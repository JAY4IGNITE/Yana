import React from "react";
import { PetState, PetMood } from "@yana/shared-types";

interface PetCompanionProps {
  state: PetState;
  mood?: PetMood;
  onPetClick?: () => void;
}

export const PetCompanion: React.FC<PetCompanionProps> = ({
  state,
  mood = "happy",
  onPetClick,
}) => {
  // Determine aura and eye color based on state
  const getStateColors = () => {
    switch (state) {
      case "listening":
        return { aura: "#38BDF8", eye: "#0284C7", text: "Listening..." };
      case "thinking":
        return { aura: "#818CF8", eye: "#4F46E5", text: "Thinking..." };
      case "executing":
        return { aura: "#F59E0B", eye: "#D97706", text: "Executing Tool..." };
      case "verifying":
        return { aura: "#A855F7", eye: "#7E22CE", text: "Verifying..." };
      case "success":
        return { aura: "#10B981", eye: "#059669", text: "Task Complete!" };
      case "error":
        return { aura: "#F43F5E", eye: "#E11D48", text: "Attention Needed" };
      case "sleeping":
        return { aura: "#475569", eye: "#334155", text: "Resting" };
      case "idle":
      default:
        return { aura: "#38BDF8", eye: "#38BDF8", text: "Ready" };
    }
  };

  const { aura, eye, text } = getStateColors();

  return (
    <div
      data-testid="pet-companion"
      className="flex flex-col items-center justify-center p-4 cursor-pointer select-none group"
      onClick={onPetClick}
      role="button"
      tabIndex={0}
      title={`YANA Pet: ${state} (${mood})`}
    >
      <div className="relative w-36 h-36 flex items-center justify-center animate-float">
        {/* Glow Aura */}
        <div
          className="absolute inset-0 rounded-full blur-xl opacity-40 animate-pulse-glow transition-colors duration-500"
          style={{ backgroundColor: aura }}
        />

        {/* Pet Body (Robot Orb Companion) */}
        <svg
          viewBox="0 0 100 100"
          className="w-28 h-28 relative z-10 drop-shadow-2xl transition-transform duration-300 group-hover:scale-105"
        >
          {/* Outer Shell Gradient */}
          <defs>
            <linearGradient id="bodyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#1E293B" />
              <stop offset="100%" stopColor="#0F172A" />
            </linearGradient>
            <linearGradient id="faceGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#0B0F19" />
              <stop offset="100%" stopColor="#020617" />
            </linearGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Antennas / Ears */}
          <path
            d="M 30 25 Q 22 10 15 16 Q 22 25 32 30"
            fill="#334155"
            stroke="#475569"
            strokeWidth="1.5"
          />
          <path
            d="M 70 25 Q 78 10 85 16 Q 78 25 68 30"
            fill="#334155"
            stroke="#475569"
            strokeWidth="1.5"
          />

          {/* Body Sphere */}
          <rect
            x="14"
            y="18"
            width="72"
            height="70"
            rx="35"
            fill="url(#bodyGrad)"
            stroke="rgba(255, 255, 255, 0.15)"
            strokeWidth="1.5"
          />

          {/* Visor / Screen Face */}
          <rect
            x="22"
            y="28"
            width="56"
            height="46"
            rx="20"
            fill="url(#faceGrad)"
            stroke={aura}
            strokeWidth="1"
            className="transition-colors duration-500"
          />

          {/* Eyes based on state */}
          {state === "sleeping" ? (
            // Closed / sleeping eyes (curved lines)
            <g stroke={eye} strokeWidth="3" strokeLinecap="round" fill="none">
              <path d="M 32 50 Q 38 56 44 50" />
              <path d="M 56 50 Q 62 56 68 50" />
            </g>
          ) : state === "error" ? (
            // Concerned / error eyes (crosses or alert shapes)
            <g stroke={eye} strokeWidth="2.5" strokeLinecap="round">
              <line x1="34" y1="46" x2="42" y2="54" />
              <line x1="42" y1="46" x2="34" y2="54" />
              <line x1="58" y1="46" x2="66" y2="54" />
              <line x1="66" y1="46" x2="58" y2="54" />
            </g>
          ) : (
            // Expressive Glowing Oval Eyes
            <g filter="url(#glow)">
              <ellipse
                cx="38"
                cy={state === "thinking" ? "48" : "50"}
                rx={state === "listening" ? "5.5" : "5"}
                ry={state === "listening" ? "7" : "5.5"}
                fill={eye}
                className="transition-all duration-300"
              />
              <ellipse
                cx="62"
                cy={state === "thinking" ? "48" : "50"}
                rx={state === "listening" ? "5.5" : "5"}
                ry={state === "listening" ? "7" : "5.5"}
                fill={eye}
                className="transition-all duration-300"
              />
              {/* Eye sparkle reflections */}
              <circle cx="40" cy="48" r="1.5" fill="#ffffff" opacity="0.8" />
              <circle cx="64" cy="48" r="1.5" fill="#ffffff" opacity="0.8" />
            </g>
          )}

          {/* Cheeks blush for happy / success mood */}
          {(mood === "happy" || state === "success") && (
            <g opacity="0.6">
              <ellipse cx="28" cy="58" rx="3" ry="1.5" fill="#F43F5E" />
              <ellipse cx="72" cy="58" rx="3" ry="1.5" fill="#F43F5E" />
            </g>
          )}

          {/* Mouth */}
          {state === "success" || mood === "happy" ? (
            <path
              d="M 44 60 Q 50 66 56 60"
              stroke={eye}
              strokeWidth="2"
              strokeLinecap="round"
              fill="none"
            />
          ) : state === "thinking" ? (
            <line x1="46" y1="62" x2="54" y2="62" stroke={eye} strokeWidth="2" strokeLinecap="round" />
          ) : (
            <ellipse cx="50" cy="62" rx="2" ry="1.5" fill={eye} opacity="0.6" />
          )}
        </svg>
      </div>

      {/* State Badge */}
      <div className="mt-2 flex items-center space-x-2 px-3 py-1 rounded-full bg-slate-900/80 border border-white/10 shadow-lg text-xs font-medium tracking-wide">
        <span
          className="w-2 h-2 rounded-full animate-ping"
          style={{ backgroundColor: aura }}
        />
        <span className="text-slate-300">{text}</span>
      </div>
    </div>
  );
};
