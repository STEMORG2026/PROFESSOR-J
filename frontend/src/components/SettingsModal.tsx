"use client";

import { useState } from "react";
import { PROVIDERS } from "@/components/ProviderSelector";
import { usePersonas } from "@/hooks/usePersonas";
import { useGlobalSettings } from "@/hooks/useGlobalSettings";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentSessionId: string | null;
  onSessionUpdate: (updates: {
    provider?: string;
    model?: string;
    system_prompt?: string | undefined;
  }) => void;
}

export function SettingsModal({
  isOpen,
  onClose,
  currentSessionId,
  onSessionUpdate,
}: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<"general" | "providers" | "personas">("general");
  const [newPersonaName, setNewPersonaName] = useState("");
  const [newPersonaPrompt, setNewPersonaPrompt] = useState("");
  const [newPersonaDesc, setNewPersonaDesc] = useState("");
  const [editingPersonaId, setEditingPersonaId] = useState<string | null>(null);
  const [editPersonaName, setEditPersonaName] = useState("");
  const [editPersonaPrompt, setEditPersonaPrompt] = useState("");
  const [editPersonaDesc, setEditPersonaDesc] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // API Key visibility states
  const [showApiKeys, setShowApiKeys] = useState<Record<string, boolean>>({});
  // Test connection states
  const [testingKeys, setTestingKeys] = useState<Record<string, boolean>>({});
  const [keyTestResults, setKeyTestResults] = useState<Record<string, { success: boolean; message: string }>>({});

  const { personas, loading: personasLoading, createPersona, updatePersona, deletePersona } = usePersonas();
  const { defaults, providerKeys, loading: settingsLoading, updateDefault, updateProviderKey, refetch: refetchSettings } = useGlobalSettings();

  const clearMessages = () => {
    setError(null);
    setSuccess(null);
  };

  const handleCreatePersona = async () => {
    if (!newPersonaName.trim() || !newPersonaPrompt.trim()) {
      setError("Name and system prompt are required");
      return;
    }
    clearMessages();
    try {
      await createPersona(newPersonaName.trim(), newPersonaPrompt.trim(), newPersonaDesc.trim() || undefined);
      setSuccess(`Persona "${newPersonaName}" created`);
      setNewPersonaName("");
      setNewPersonaPrompt("");
      setNewPersonaDesc("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create persona");
    }
  };

  const handleEditPersona = (persona: { persona_id: string; name: string; system_prompt: string; description?: string | null }) => {
    setEditingPersonaId(persona.persona_id);
    setEditPersonaName(persona.name);
    setEditPersonaPrompt(persona.system_prompt);
    setEditPersonaDesc(persona.description || "");
  };

  const handleSaveEditPersona = async () => {
    if (!editingPersonaId || !editPersonaName.trim() || !editPersonaPrompt.trim()) {
      setError("Name and system prompt are required");
      return;
    }
    clearMessages();
    try {
      await updatePersona(editingPersonaId, {
        name: editPersonaName.trim(),
        system_prompt: editPersonaPrompt.trim(),
        description: editPersonaDesc.trim() || undefined,
      });
      setSuccess(`Persona "${editPersonaName}" updated`);
      setEditingPersonaId(null);
      setEditPersonaName("");
      setEditPersonaPrompt("");
      setEditPersonaDesc("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update persona");
    }
  };

  const handleDeletePersona = async (personaId: string, personaName: string) => {
    if (!confirm(`Delete persona "${personaName}"?`)) return;
    clearMessages();
    try {
      await deletePersona(personaId);
      setSuccess(`Persona "${personaName}" deleted`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete persona");
    }
  };

  const handleProviderKeyChange = async (configKey: string, value: string) => {
    clearMessages();
    try {
      await updateProviderKey(configKey, value);
      setSuccess("API key saved");
      // Clear test result when key changes
      setKeyTestResults(prev => {
        const next = { ...prev };
        delete next[configKey];
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save API key");
    }
  };

  const handleDefaultChange = async (key: "provider" | "model" | "system_prompt" | "base_url", value: string | null) => {
    clearMessages();
    try {
      await updateDefault(key, value);
      setSuccess(`Default ${key} updated`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update default");
    }
  };

  const handleApplyToSession = () => {
    if (!currentSessionId) return;
    onSessionUpdate({
      provider: defaults.provider || undefined,
      model: defaults.model || undefined,
      system_prompt: defaults.system_prompt || undefined,
    });
    setSuccess("Applied global defaults to current session");
  };

  // Test API key
  const handleTestKey = async (providerId: string, configKey: string) => {
    const key = providerKeys[configKey];
    if (!key) {
      setError("No API key to test");
      return;
    }

    setTestingKeys(prev => ({ ...prev, [configKey]: true }));
    setKeyTestResults(prev => {
      const next = { ...prev };
      delete next[configKey];
      return next;
    });

    try {
      const res = await fetch("/api/voice/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ test_provider: providerId, api_key: key }),
      });
      const data = await res.json();
      setKeyTestResults(prev => ({
        ...prev,
        [configKey]: { success: data.ok, message: data.message || (data.ok ? "Connection successful" : "Connection failed") }
      }));
    } catch (err) {
      setKeyTestResults(prev => ({
        ...prev,
        [configKey]: { success: false, message: err instanceof Error ? err.message : "Test failed" }
      }));
    } finally {
      setTestingKeys(prev => ({ ...prev, [configKey]: false }));
    }
  };

  // Toggle API key visibility
  const toggleKeyVisibility = (configKey: string) => {
    setShowApiKeys(prev => ({ ...prev, [configKey]: !prev[configKey] }));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 animate-in fade-in-0 duration-200" onClick={onClose}>
      <div
        className="w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-slate-950 rounded-2xl border border-white/10 shadow-2xl animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/10 sticky top-0 bg-slate-950/95 backdrop-blur-sm z-10">
          <h2 className="text-lg font-semibold text-slate-100">Settings</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-slate-100 transition"
            aria-label="Close settings"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-white/10 sticky top-14 bg-slate-950/95 backdrop-blur-sm z-10">
          {[
            { id: "general", label: "General", icon: <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg> },
            { id: "providers", label: "API Keys", icon: <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg> },
            { id: "personas", label: "Personas", icon: <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg> },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition whitespace-nowrap ${
                activeTab === tab.id
                  ? "text-cyan-300 border-b-2 border-cyan-500"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="p-4 space-y-5 pb-10">
          {/* General Tab */}
          {activeTab === "general" && (
            <div className="space-y-5">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">Default Provider</label>
                <select
                  value={defaults.provider || "singularity"}
                  onChange={(e) => handleDefaultChange("provider", e.target.value)}
                  disabled={settingsLoading}
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                >
                  {PROVIDERS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} {p.freeTier && "(Free)"}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">Default Model</label>
                <input
                  type="text"
                  value={defaults.model || "deepseek-v4-flash-0731"}
                  onChange={(e) => handleDefaultChange("model", e.target.value)}
                  disabled={settingsLoading}
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                  placeholder="e.g. deepseek-v4-flash-0731"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">Default System Prompt</label>
                <textarea
                  value={defaults.system_prompt || ""}
                  onChange={(e) => handleDefaultChange("system_prompt", e.target.value || null)}
                  disabled={settingsLoading}
                  rows={3}
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 font-mono focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                  placeholder="Global default system prompt"
                />
                <p className="mt-1 text-xs text-slate-500">Applies to all new sessions. Leave empty for built-in default.</p>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">Default Base URL</label>
                <input
                  type="url"
                  value={defaults.base_url || ""}
                  onChange={(e) => handleDefaultChange("base_url", e.target.value || null)}
                  disabled={settingsLoading}
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                  placeholder="https://api.openai.com/v1"
                />
                <p className="mt-1 text-xs text-slate-500">For OpenAI-compatible providers.</p>
              </div>

              {currentSessionId && (
                <button
                  onClick={handleApplyToSession}
                  disabled={settingsLoading}
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-300 hover:bg-white/10 transition"
                >
                  Apply Defaults to This Session
                </button>
              )}
            </div>
          )}

          {/* Providers Tab - API Keys */}
          {activeTab === "providers" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-400">Keys are stored globally and used for all sessions.</p>
                <button
                  onClick={async () => {
                    clearMessages();
                    try {
                      await refetchSettings();
                      setSuccess("Refreshed");
                    } catch (err) {
                      setError(err instanceof Error ? err.message : "Failed to refresh");
                    }
                  }}
                  disabled={settingsLoading}
                  className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5 text-sm transition"
                >
                  Refresh
                </button>
              </div>

              {PROVIDERS.filter((p) => p.apiKeyRequired).map((provider) => {
                const configKey = provider.configKey;
                const keyValue = providerKeys[configKey] || "";
                const isTesting = testingKeys[configKey];
                const testResult = keyTestResults[configKey];
                const showKey = showApiKeys[configKey];

                return (
                  <div key={provider.id} className="rounded-xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-indigo-500 flex items-center justify-center">
                          <span className="text-white font-bold text-lg">{provider.name.charAt(0)}</span>
                        </div>
                        <div>
                          <p className="font-medium text-slate-100">{provider.name}</p>
                          <p className="text-xs text-slate-500">{provider.baseUrl}</p>
                        </div>
                      </div>
                      {keyValue && (
                        <span className="px-2 py-1 rounded text-xs bg-green-500/20 text-green-400">✓ Configured</span>
                      )}
                    </div>

                    <div className="relative mb-3">
                      <input
                        type={showKey ? "text" : "password"}
                        value={keyValue}
                        onChange={(e) => handleProviderKeyChange(configKey, e.target.value)}
                        placeholder={`Enter ${provider.name} API key...`}
                        disabled={settingsLoading || isTesting}
                        className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 pr-12 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                      />
                      <button
                        type="button"
                        onClick={() => toggleKeyVisibility(configKey)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition"
                        aria-label={showKey ? "Hide key" : "Show key"}
                      >
                        {showKey ? (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                        )}
                      </button>
                      {keyValue && testResult && (
                        <div className="mt-2 flex items-center gap-2 text-xs">
                          {testResult.success ? (
                            <>
                              <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                              <span className="text-green-400">{testResult.message}</span>
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m-2 2l2 2m-2 2l-2-2" /></svg>
                              <span className="text-rose-400">{testResult.message}</span>
                            </>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleTestKey(provider.id, configKey)}
                        disabled={!keyValue || isTesting || settingsLoading}
                        className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 text-sm text-slate-300 hover:bg-white/10 transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
                      >
                        {isTesting ? (
                          <>
                            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                            <span>Testing...</span>
                          </>
                        ) : (
                          <>
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            <span>Test Connection</span>
                          </>
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (!confirm("Delete this API key?")) return;
                          handleProviderKeyChange(configKey, "");
                        }}
                        disabled={!keyValue || settingsLoading}
                        className="px-3 py-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 text-sm text-rose-300 hover:bg-rose-500/20 transition disabled:opacity-40"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                        <span>Delete</span>
                      </button>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">Get your API key from <a href={provider.baseUrl} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">{provider.baseUrl}</a></p>
                  </div>
              )})}

            {/* OpenAI Compatible Base URL */}
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <label className="mb-2 block text-sm font-medium text-slate-300">OpenAI Compatible Base URL</label>
              <input
                type="url"
                value={providerKeys.openai_compat_base_url || defaults.base_url || ""}
                onChange={(e) => handleProviderKeyChange("openai_compat_base_url", e.target.value)}
                disabled={settingsLoading}
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                placeholder="https://api.singularity.ai/v1 or http://localhost:11434/v1"
              />
              <p className="mt-1 text-xs text-slate-500">Used when &ldquo;OpenAI Compatible&rdquo; provider is selected.</p>
            </div>
          </div>
        )}

          {/* Personas Tab */}
          {activeTab === "personas" && (
            <div className="space-y-5">
              {/* Create New Persona */}
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <h3 className="text-sm font-medium text-slate-300 mb-3">Create Persona</h3>
                <div className="space-y-3">
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-slate-300">Name</label>
                    <input
                      type="text"
                      value={newPersonaName}
                      onChange={(e) => setNewPersonaName(e.target.value)}
                      placeholder="e.g. Code Reviewer, Creative Writer"
                      className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-slate-300">Description (optional)</label>
                    <input
                      type="text"
                      value={newPersonaDesc}
                      onChange={(e) => setNewPersonaDesc(e.target.value)}
                      placeholder="Brief description"
                      className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-slate-300">System Prompt</label>
                    <textarea
                      value={newPersonaPrompt}
                      onChange={(e) => setNewPersonaPrompt(e.target.value)}
                      placeholder="You are a..."
                      rows={4}
                      className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 font-mono focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                    />
                  </div>
                  <button
                    onClick={handleCreatePersona}
                    disabled={personasLoading || !newPersonaName.trim() || !newPersonaPrompt.trim()}
                    className="w-full rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 px-4 py-2.5 text-sm font-semibold text-white transition disabled:opacity-40"
                  >
                    Create Persona
                  </button>
                </div>
              </div>

              {/* Saved Personas */}
              <div>
                <h3 className="text-sm font-medium text-slate-300 mb-3">Saved Personas</h3>
                {personasLoading ? (
                  <div className="text-center text-slate-500 py-6">Loading...</div>
                ) : personas.length === 0 ? (
                  <div className="text-center text-slate-500 py-6">No personas saved</div>
                ) : (
                  <div className="space-y-2">
                    {personas.map((persona) => (
                      <div key={persona.persona_id} className="rounded-xl border border-white/10 bg-white/5 p-3">
                        {editingPersonaId === persona.persona_id ? (
                          <div className="space-y-2">
                            <input
                              type="text"
                              value={editPersonaName}
                              onChange={(e) => setEditPersonaName(e.target.value)}
                              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                            />
                            <textarea
                              value={editPersonaPrompt}
                              onChange={(e) => setEditPersonaPrompt(e.target.value)}
                              rows={3}
                              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 font-mono focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                            />
                            <div className="flex justify-end gap-2">
                              <button onClick={() => setEditingPersonaId(null)} className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5 text-sm">Cancel</button>
                              <button onClick={handleSaveEditPersona} className="px-3 py-1.5 rounded-lg bg-cyan-500 text-white hover:bg-cyan-600 text-sm">Save</button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-slate-100 truncate">{persona.name}</p>
                              {persona.description && <p className="text-xs text-slate-500 truncate">{persona.description}</p>}
                            </div>
                            <div className="flex items-center gap-1 flex-shrink-0">
                              <button onClick={() => handleEditPersona(persona)} className="p-1.5 rounded hover:bg-white/10 text-slate-400 hover:text-slate-100 transition" title="Edit">
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                              </button>
                              <button onClick={() => handleDeletePersona(persona.persona_id, persona.name)} className="p-1.5 rounded hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 transition" title="Delete">
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Error/Success */}
          {error && (
            <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</div>
          )}
          {success && (
            <div className="rounded-lg border border-green-500/40 bg-green-500/10 px-4 py-3 text-sm text-green-200">{success}</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default SettingsModal;
