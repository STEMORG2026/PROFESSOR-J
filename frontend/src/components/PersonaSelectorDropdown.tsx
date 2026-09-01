"use client";

import { useState, useRef, useEffect } from "react";
import { usePersonas } from "@/hooks/usePersonas";

interface PersonaSelectorDropdownProps {
  selectedPersonaId: string | null;
  selectedCustomPrompt: string;
  onPersonaSelect: (personaId: string | null, customPrompt?: string) => void;
  onCustomPromptChange: (prompt: string) => void;
  disabled?: boolean;
}

export function PersonaSelectorDropdown({
  selectedPersonaId,
  selectedCustomPrompt,
  onPersonaSelect,
  onCustomPromptChange,
  disabled = false,
}: PersonaSelectorDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [showCustomEditor, setShowCustomEditor] = useState(false);
  const [customPrompt, setCustomPrompt] = useState(selectedCustomPrompt);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { personas, loading: personasLoading } = usePersonas();

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setShowCustomEditor(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const getDisplayText = () => {
    if (selectedPersonaId === "custom") {
      return "Custom System Prompt";
    }
    if (selectedPersonaId === null) {
      return "Default (JARVIS)";
    }
    const persona = personas.find((p) => p.persona_id === selectedPersonaId);
    return persona ? persona.name : "Default (JARVIS)";
  };

  const handlePersonaClick = (personaId: string | null) => {
    if (personaId === "custom") {
      setShowCustomEditor(true);
      setCustomPrompt(selectedCustomPrompt);
    } else {
      onPersonaSelect(personaId);
      setIsOpen(false);
      setShowCustomEditor(false);
    }
  };

  const handleSaveCustom = () => {
    onPersonaSelect("custom", customPrompt);
    onCustomPromptChange(customPrompt);
    setIsOpen(false);
    setShowCustomEditor(false);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled || personasLoading}
        className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 transition-all hover:border-cyan-500/50 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 disabled:opacity-40 disabled:cursor-not-allowed min-w-[180px]"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        <span className="truncate max-w-[140px] font-medium">{getDisplayText()}</span>
        <svg className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-1.5 w-[360px] max-h-[520px] overflow-y-auto rounded-xl border border-white/10 bg-slate-900/95 backdrop-blur-sm shadow-xl ring-1 ring-white/5 z-50 animate-in fade-in-0 zoom-in-95 duration-150">
          {/* Search */}
          <div className="p-2 border-b border-white/10">
            <input
              type="text"
              placeholder="Search personas..."
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              autoFocus
            />
          </div>

          {/* Default Option */}
          <div className="p-2 border-b border-white/10">
            <button
              type="button"
              onClick={() => handlePersonaClick(null)}
              disabled={disabled}
              className={`w-full px-3 py-2 text-sm text-left rounded-lg transition flex items-center gap-2 ${
                selectedPersonaId === null
                  ? "bg-cyan-500/20 text-cyan-300 font-medium"
                  : "text-slate-200 hover:bg-white/5"
              } disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="flex-1 truncate">Default (JARVIS)</span>
              {selectedPersonaId === null && (
                <svg className="w-4 h-4 text-cyan-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
            </button>
          </div>

          {/* Saved Personas */}
          {personasLoading ? (
            <div className="px-3 py-4 text-center text-slate-500 text-sm">Loading personas...</div>
          ) : personas.length === 0 ? (
            <div className="px-3 py-4 text-center text-slate-500 text-sm">No saved personas</div>
          ) : (
            <>
              <div className="px-3 py-1 text-xs font-semibold text-slate-400 uppercase tracking-wider">Saved Personas</div>
              {personas.map((persona) => (
                <button
                  key={persona.persona_id}
                  type="button"
                  onClick={() => handlePersonaClick(persona.persona_id)}
                  disabled={disabled}
                  className={`w-full px-3 py-2 text-sm text-left rounded-lg transition flex items-center gap-2 ${
                    selectedPersonaId === persona.persona_id
                      ? "bg-cyan-500/20 text-cyan-300 font-medium"
                      : "text-slate-200 hover:bg-white/5"
                  } disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  <div className="flex-1 min-w-0 flex flex-col">
                    <span className="truncate">{persona.name}</span>
                    {persona.description && (
                      <span className="text-xs text-slate-500 truncate">{persona.description}</span>
                    )}
                  </div>
                  {selectedPersonaId === persona.persona_id && (
                    <svg className="w-4 h-4 text-cyan-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  )}
                </button>
              ))}
            </>
          )}

          <div className="border-t border-white/10 my-1" />

          {/* Custom Option */}
          {showCustomEditor ? (
            <div className="p-3 space-y-2 border-t border-white/10">
              <label className="text-xs font-medium text-slate-400">Custom System Prompt</label>
              <textarea
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                placeholder="Enter custom system prompt..."
                rows={5}
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 font-mono resize-y min-h-[120px]"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCustomEditor(false)}
                  className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5 text-sm"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveCustom}
                  className="px-3 py-1.5 rounded-lg bg-cyan-500 text-white hover:bg-cyan-600 text-sm"
                >
                  Save & Use
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => handlePersonaClick("custom")}
              disabled={disabled}
              className="w-full px-3 py-2 text-sm text-left rounded-lg transition flex items-center gap-2 text-slate-200 hover:bg-white/5 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg className="w-4 h-4 flex-shrink-0 text-fuchsia-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              <span>+ Custom System Prompt</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default PersonaSelectorDropdown;
