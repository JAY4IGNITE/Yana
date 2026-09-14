import React, { useState } from "react";
import { PetCompanion } from "../Pet/PetCompanion";
import { PetState, PetMood, PetScale } from "@yana/shared-types";
import { Maximize2, Pin, PinOff, ZoomIn } from "lucide-react";

interface CollapsedPetViewProps {
  petState: PetState;
  petMood?: PetMood;
  scale: PetScale;
  alwaysOnTop: boolean;
  onExpand: () => void;
  onToggleAlwaysOnTop: () => void;
  onCycleScale: () => void;
}

export const CollapsedPetView: React.FC<CollapsedPetViewProps> = ({
  petState,
  petMood = "happy",
  scale,
  alwaysOnTop,
  onExpand,
  onToggleAlwaysOnTop,
  onCycleScale,
}) => {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      data-testid="collapsed-pet-view"
      data-tauri-drag-region
      className="relative w-full h-full flex flex-col items-center justify-center p-2 select-none cursor-move group"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Floating Control Overlay on Hover */}
      <div
        className={`absolute top-1 right-2 flex items-center space-x-1 z-30 transition-opacity duration-200 ${
          hovered ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      >
        {/* Scale Toggle */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onCycleScale();
          }}
          className="p-1 rounded-lg bg-slate-900/90 hover:bg-slate-800 text-slate-300 border border-slate-700/60 shadow transition text-[10px]"
          title={`Scale: ${scale}`}
          aria-label="Change Pet Size"
        >
          <ZoomIn className="w-3 h-3" />
        </button>

        {/* Pin / Always-On-Top Toggle */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleAlwaysOnTop();
          }}
          className={`p-1 rounded-lg border shadow transition text-[10px] ${
            alwaysOnTop
              ? "bg-sky-500/30 text-sky-300 border-sky-500/50"
              : "bg-slate-900/90 hover:bg-slate-800 text-slate-400 border-slate-700/60"
          }`}
          title={alwaysOnTop ? "Always on top (Enabled)" : "Always on top (Disabled)"}
          aria-label="Toggle Always On Top"
        >
          {alwaysOnTop ? <Pin className="w-3 h-3 text-sky-400" /> : <PinOff className="w-3 h-3" />}
        </button>

        {/* Expand into Assistant Interface */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onExpand();
          }}
          className="p-1 rounded-lg bg-slate-900/90 hover:bg-sky-500 hover:text-slate-950 text-slate-300 border border-slate-700/60 shadow transition"
          title="Open Assistant Interface"
          aria-label="Expand YANA Interface"
        >
          <Maximize2 className="w-3 h-3" />
        </button>
      </div>

      {/* The Floating Pet Companion */}
      <div
        className="cursor-pointer transition-transform duration-200 active:scale-95"
        onClick={onExpand}
        title="Click to interact with YANA"
      >
        <PetCompanion
          state={petState}
          mood={petMood}
          scale={scale}
          showBadge={true}
        />
      </div>
    </div>
  );
};
