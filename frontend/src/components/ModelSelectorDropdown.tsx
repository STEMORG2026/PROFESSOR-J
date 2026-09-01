"use client";

import { useState, useRef, useEffect } from "react";
import { PROVIDERS } from "@/components/ProviderSelector";

interface ModelSelectorDropdownProps {
  selectedProvider: string;
  selectedModel: string;
  onChange: (providerId: string, modelId: string) => void;
  disabled?: boolean;
}

export function ModelSelectorDropdown({
  selectedProvider,
  selectedModel,
  onChange,
  disabled = false,
}: ModelSelectorDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const provider = PROVIDERS.find((p) => p.id === selectedProvider) ?? PROVIDERS[0];

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleModelSelect = (providerId: string, modelId: string) => {
    onChange(providerId, modelId);
    setIsOpen(false);
  };

  const getDisplayText = () => {
    return `${provider.name} / ${selectedModel}`;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 transition-all hover:border-cyan-500/50 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 disabled:opacity-40 disabled:cursor-not-allowed min-w-[200px]"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <span className="truncate max-w-[160px] font-medium">{getDisplayText()}</span>
        <svg className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-1.5 w-[320px] max-h-[480px] overflow-y-auto rounded-xl border border-white/10 bg-slate-900/95 backdrop-blur-sm shadow-xl ring-1 ring-white/5 z-50 animate-in fade-in-0 zoom-in-95 duration-150">
          {/* Search */}
          <div className="p-2 border-b border-white/10">
            <input
              type="text"
              placeholder="Search models..."
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              autoFocus
            />
          </div>

          {/* Provider Groups */}
          <div className="p-2">
            {PROVIDERS.map((p) => (
              <div key={p.id} className="group">
                <div className="px-3 py-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-500/50" />
                  {p.name} {p.freeTier && <span className="text-xs px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">Free</span>}
                </div>
                {p.models.map((model) => (
                  <button
                    key={`${p.id}:${model}`}
                    type="button"
                    onClick={() => handleModelSelect(p.id, model)}
                    disabled={disabled}
                    className={`w-full px-3 py-2 text-sm text-left rounded-lg transition flex items-center gap-2 ${
                      selectedProvider === p.id && selectedModel === model
                        ? "bg-cyan-500/20 text-cyan-300 font-medium"
                        : "text-slate-200 hover:bg-white/5"
                    } disabled:opacity-40 disabled:cursor-not-allowed`}
                  >
                    <span className="truncate flex-1">{model}</span>
                    {selectedProvider === p.id && selectedModel === model && (
                      <svg className="w-4 h-4 text-cyan-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    )}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ModelSelectorDropdown;
