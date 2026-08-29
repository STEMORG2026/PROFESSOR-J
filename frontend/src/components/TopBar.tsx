import { useState } from "react";
import { ModelSelectorDropdown } from "@/components/ModelSelectorDropdown";
import { PersonaSelectorDropdown } from "@/components/PersonaSelectorDropdown";
import { SettingsModal } from "@/components/SettingsModal";
import { useGlobalSettings } from "@/hooks/useGlobalSettings";

interface TopBarProps {
  sessionTitle: string | null;
  onTitleClick: () => void;
  onNewSession: () => void;
  selectedProvider: string;
  selectedModel: string;
  onModelChange: (providerId: string, modelId: string) => void;
  selectedPersonaId: string | null;
  selectedCustomPrompt: string;
  onPersonaChange: (personaId: string | null, customPrompt?: string) => void;
  onCustomPromptChange: (prompt: string) => void;
  currentSessionId: string | null;
  onSessionUpdate: (updates: { provider?: string; model?: string; system_prompt?: string | undefined }) => void;
  busy?: boolean;
}

export function TopBar({
  sessionTitle,
  onTitleClick,
  onNewSession,
  selectedProvider,
  selectedModel,
  onModelChange,
  selectedPersonaId,
  selectedCustomPrompt,
  onPersonaChange,
  onCustomPromptChange,
  currentSessionId,
  onSessionUpdate,
  busy = false,
}: TopBarProps) {
  const [showSettings, setShowSettings] = useState(false);
  const { providerKeys, loading: settingsLoading } = useGlobalSettings();

  // Check if any API keys are configured
  const hasAnyApiKey = Object.values(providerKeys).some((v) => v && v.length > 0);

  return (
    <header className="flex items-center justify-between h-16 px-4 border-b border-white/10 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-40">
      {/* Left: Logo + Session Title + New Chat */}
      <div className="flex items-center gap-4 min-w-0 flex-1">
        <button
          onClick={onNewSession}
          className="flex-shrink-0 p-2 rounded-xl hover:bg-white/10 text-slate-400 hover:text-slate-100 transition"
          aria-label="New chat"
          title="New Chat (⌘N)"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
        </button>
        <div
          onClick={onTitleClick}
          className="flex-shrink-0 cursor-pointer select-none group"
          title="Click to rename"
        >
          <h1 className="bg-gradient-to-r from-cyan-300 via-indigo-300 to-fuchsia-300 bg-clip-text text-xl font-bold text-transparent group-hover:from-cyan-400 group-hover:to-fuchsia-400 transition">
            PROFESSOR-J
          </h1>
          {sessionTitle && (
            <p className="text-sm text-slate-400 truncate max-w-[200px] group-hover:text-slate-300 transition">
              {sessionTitle}
            </p>
          )}
        </div>
      </div>

      {/* Center: Model Selector + Persona Selector */}
      <div className="flex items-center gap-3">
        <ModelSelectorDropdown
          selectedProvider={selectedProvider}
          selectedModel={selectedModel}
          onChange={onModelChange}
          disabled={busy}
        />
        <PersonaSelectorDropdown
          selectedPersonaId={selectedPersonaId}
          selectedCustomPrompt={selectedCustomPrompt}
          onPersonaSelect={onPersonaChange}
          onCustomPromptChange={onCustomPromptChange}
          disabled={busy}
        />
      </div>

      {/* Right: API Key Warning + Settings */}
      <div className="flex items-center gap-2">
        {/* API Key Warning Banner */}
        {!hasAnyApiKey && !settingsLoading && (
          <button
            onClick={() => setShowSettings(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/20 border border-amber-500/50 text-amber-300 text-sm font-medium hover:bg-amber-500/30 transition"
            title="No API keys configured - click to add"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 16h.01" />
            </svg>
            <span>Add API Key</span>
          </button>
        )}

        {/* Settings Button */}
        <button
          onClick={() => setShowSettings(true)}
          disabled={busy}
          className="p-2 rounded-xl border border-white/10 bg-white/5 text-slate-400 hover:border-cyan-500/50 hover:text-cyan-300 hover:bg-cyan-500/10 transition disabled:opacity-40"
          aria-label="Settings"
          title="Settings (⌘,)"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        currentSessionId={currentSessionId}
        onSessionUpdate={onSessionUpdate}
      />
    </header>
  );
}

export default TopBar;
