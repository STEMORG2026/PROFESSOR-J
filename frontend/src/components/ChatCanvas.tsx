"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { VoiceInputButton, MessageTTSButton } from "@/components/VoiceComponents";
import FileUpload from "@/components/FileUpload";
import SessionSidebar from "@/components/SessionSidebar";
import TopBar from "@/components/TopBar";
import { PROVIDERS } from "@/components/ProviderSelector";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  intent?: string;
  provider?: string;
  sessionId?: string;
  attachedFile?: {
    original_name: string;
    content_type: string;
    size: number;
  };
  // For edit/resend
  isEditing?: boolean;
  editContent?: string;
};

const LEARNER_ID = "default";

export default function ChatCanvas() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [currentSession, setCurrentSession] = useState<{
    session_id: string;
    title: string | null;
    provider: string | null;
    model: string | null;
    system_prompt: string | null;
    api_keys: Record<string, string> | null;
    base_url: string | null;
  } | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Provider / model / persona state
  const [selectedProvider, setSelectedProvider] = useState("singularity");
  const [selectedModel, setSelectedModel] = useState("deepseek-v4-flash-0731");
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [baseUrl, setBaseUrl] = useState("");

  // Persona state
  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(null);
  const [customSystemPrompt, setCustomSystemPrompt] = useState("");

  const [attachedFile, setAttachedFile] = useState<{
    original_name: string;
    content_type: string;
    size: number;
  } | null>(null);

  const [editingMessageIndex, setEditingMessageIndex] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Load session data when session changes
  const loadMessages = useCallback(async () => {
    if (!currentSessionId) return;
    try {
      const res = await fetch(`/api/sessions/${currentSessionId}/conversations`);
      if (!res.ok) throw new Error("Failed to load messages");
      const conversations = await res.json();
      if (conversations.length > 0) {
        const latestConv = conversations[0];
        setMessages(
          (latestConv.messages || []).map((m: Record<string, unknown>) => ({
            role: m.role as "user" | "assistant",
            content: m.content as string,
            intent: m.intent as string | undefined,
            provider: m.provider as string | undefined,
            sessionId: currentSessionId,
          }))
        );
      } else {
        setMessages([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load messages");
    }
  }, [currentSessionId]);

  useEffect(() => {
    if (currentSessionId) {
      fetch(`/api/sessions/${currentSessionId}`)
        .then((res) => {
          if (!res.ok) throw new Error("Failed to load session");
          return res.json();
        })
        .then((session) => {
          setCurrentSession(session);
          setSelectedProvider(session.provider || "singularity");
          setSelectedModel(session.model || "deepseek-v4-flash-0731");
          if (session.api_keys) {
            try {
              setApiKeys(JSON.parse(session.api_keys));
            } catch {
              setApiKeys({});
            }
          }
          setBaseUrl(session.base_url || "");
          // If session has a system prompt, check if it matches a saved persona
          if (session.system_prompt) {
            // For now, treat as custom prompt
            setCustomSystemPrompt(session.system_prompt);
            setSelectedPersonaId("custom");
          }
          loadMessages();
        })
        .catch((err) => {
          setError(err.message);
        });
    }
  }, [currentSessionId, loadMessages]);

  // Auto-save messages to conversation
  const saveMessages = useCallback(async (newMessages: ChatMessage[]) => {
    if (!currentSessionId) return;
    try {
      const res = await fetch(`/api/sessions/${currentSessionId}/conversations`);
      const conversations = await res.json();
      let conversationId: string;

      if (conversations.length > 0) {
        conversationId = conversations[0].conversation_id;
        await fetch(`/api/conversations/${conversationId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: newMessages.map((m) => ({
              role: m.role,
              content: m.content,
              intent: m.intent,
              provider: m.provider,
            })),
          }),
        });
      } else {
        const createRes = await fetch("/api/conversations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: currentSessionId,
            messages: newMessages.map((m) => ({
              role: m.role,
              content: m.content,
              intent: m.intent,
              provider: m.provider,
            })),
          }),
        });
        const conv = await createRes.json();
        conversationId = conv.conversation_id;
      }
    } catch (err) {
      console.error("Failed to save messages:", err);
    }
  }, [currentSessionId]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  // Reset model when provider changes (from ModelSelectorDropdown)
  const handleModelChange = useCallback((providerId: string, modelId: string) => {
    setSelectedProvider(providerId);
    setSelectedModel(modelId);
  }, []);

  // Handle persona change
  const handlePersonaChange = useCallback((personaId: string | null, customPrompt?: string) => {
    setSelectedPersonaId(personaId);
    if (personaId === "custom" && customPrompt !== undefined) {
      setCustomSystemPrompt(customPrompt);
    } else if (personaId !== "custom") {
      setCustomSystemPrompt("");
    }
  }, []);

  const handleNewSession = useCallback(async () => {
    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          learner_id: LEARNER_ID,
          title: "New Chat",
        }),
      });
      if (!res.ok) throw new Error("Failed to create session");
      const session = await res.json();
      setCurrentSessionId(session.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create session");
    }
  }, []);

  const handleSessionSelect = useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId);
  }, []);

  // Edit message
  const handleEditMessage = useCallback((index: number) => {
    const msg = messages[index];
    if (msg.role !== "user") return;
    setEditingMessageIndex(index);
  }, [messages]);

  // Save edit and resend
  const handleSaveEdit = useCallback(async (index: number, newContent: string) => {
    if (!newContent.trim()) return;

    // Update the message content
    const updatedMessages = [...messages];
    updatedMessages[index] = { ...updatedMessages[index], content: newContent, isEditing: false };
    setMessages(updatedMessages);
    setEditingMessageIndex(null);
    await saveMessages(updatedMessages);

    // Resend from this message (remove all messages after this index)
    const messagesToResend = updatedMessages.slice(0, index + 1);
    setMessages(messagesToResend);
    await saveMessages(messagesToResend);

    // Create abort controller for this request
    const abortController = new AbortController();
    (window as Window & { __currentAbortController?: AbortController }).__currentAbortController = abortController;

    // Send the edited message
    setBusy(true);
    try {
      const text = newContent.trim();
      const body: Record<string, unknown> = {
        prompt: text,
        session_id: currentSessionId,
        provider: selectedProvider,
        model: selectedModel.trim() || undefined,
      };

      const providerDef = PROVIDERS.find((p) => p.id === selectedProvider);
      if (providerDef?.apiKeyRequired) {
        const key = apiKeys[providerDef.configKey] ?? "";
        if (key.trim()) {
          body.api_key = key.trim();
        }
      }

      if (selectedProvider === "openai_compat" && baseUrl.trim()) {
        body.base_url = baseUrl.trim();
      }

      const effectiveSystemPrompt = selectedPersonaId === "custom"
        ? customSystemPrompt.trim()
        : undefined;
      if (effectiveSystemPrompt) {
        body.system_prompt = effectiveSystemPrompt;
      }

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: abortController.signal,
      });
      if (!res.ok) {
        const b = await res.text();
        throw new Error(`API ${res.status}: ${b.slice(0, 120)}`);
      }
      const data = await res.json();

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: data.response,
        intent: data.intent,
        provider: data.provider,
        sessionId: data.session_id,
      };
      const newMsgs = [...messagesToResend, assistantMsg];
      setMessages(newMsgs);
      await saveMessages(newMsgs);
    } catch (err) {
      const ex = err as Error;
      setError(
        ex.message ||
          "Could not reach the PROFESSOR-J backend. Start it with: " +
            "uvicorn app.adapters.api:app --port 8000",
      );
    } finally {
      setBusy(false);
    }
  }, [messages, currentSessionId, selectedProvider, selectedModel, apiKeys, baseUrl, selectedPersonaId, customSystemPrompt]);

  // Cancel edit
  const handleCancelEdit = useCallback(() => {
    setEditingMessageIndex(null);
  }, []);

  // Resend message (without editing)
  const handleResend = useCallback(async (index: number) => {
    await handleSaveEdit(index, messages[index].content);
  }, [handleSaveEdit]);

  // Update session settings (provider, model, system_prompt)
  const handleSessionUpdate = useCallback(async (updates: {
    provider?: string;
    model?: string;
    system_prompt?: string | undefined;
  }) => {
    if (!currentSessionId) return;
    try {
      const res = await fetch(`/api/sessions/${currentSessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (res.ok) {
        // Update local state
        setCurrentSession((prev) => prev ? { ...prev, ...updates } : null);
        if (updates.provider) setSelectedProvider(updates.provider);
        if (updates.model) setSelectedModel(updates.model);
        if (updates.system_prompt !== undefined) {
          setCustomSystemPrompt(updates.system_prompt || "");
          setSelectedPersonaId(updates.system_prompt ? "custom" : null);
        }
      }
    } catch (err) {
      console.error("Failed to update session:", err);
    }
  }, [currentSessionId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text && !attachedFile) return;
    if (busy) return;

    // Create abort controller for this request
    const abortController = new AbortController();
    // Store globally so we can cancel
    (window as Window & { __currentAbortController?: AbortController }).__currentAbortController = abortController;

    setInput("");
    setError(null);

    const userMsg: ChatMessage = {
      role: "user",
      content: text,
      attachedFile: attachedFile || undefined,
    };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    await saveMessages(newMessages);

    // Clear attachment after sending
    setAttachedFile(null);

    setBusy(true);
    try {
      const body: Record<string, unknown> = {
        prompt: text,
        session_id: currentSessionId,
        provider: selectedProvider,
        model: selectedModel.trim() || undefined,
      };

      // Send API key
      const providerDef = PROVIDERS.find((p) => p.id === selectedProvider);
      if (providerDef?.apiKeyRequired) {
        const key = apiKeys[providerDef.configKey] ?? "";
        if (key.trim()) {
          body.api_key = key.trim();
        }
      }

      // Send base URL for openai_compat
      if (selectedProvider === "openai_compat" && baseUrl.trim()) {
        body.base_url = baseUrl.trim();
      }

      // Send system prompt (custom or from persona)
      const effectiveSystemPrompt = selectedPersonaId === "custom"
        ? customSystemPrompt.trim()
        : undefined;
      if (effectiveSystemPrompt) {
        body.system_prompt = effectiveSystemPrompt;
      }

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: abortController.signal,
      });
      if (!res.ok) {
        const b = await res.text();
        throw new Error(`API ${res.status}: ${b.slice(0, 120)}`);
      }
      const data = await res.json();

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: data.response,
        intent: data.intent,
        provider: data.provider,
        sessionId: data.session_id,
      };
      const updatedMessages = [...newMessages, assistantMsg];
      setMessages(updatedMessages);
      await saveMessages(updatedMessages);
    } catch (err) {
      const ex = err as Error;
      setError(
        ex.message ||
          "Could not reach the PROFESSOR-J backend. Start it with: " +
            "uvicorn app.adapters.api:app --port 8000",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-screen w-full bg-slate-950">
      {/* Session Sidebar */}
      <SessionSidebar
        currentSessionId={currentSessionId}
        onSessionSelect={handleSessionSelect}
        onNewSession={handleNewSession}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <TopBar
          sessionTitle={currentSession?.title ?? null}
          onTitleClick={() => {
            // Could add rename inline here
          }}
          onNewSession={handleNewSession}
          selectedProvider={selectedProvider}
          selectedModel={selectedModel}
          onModelChange={handleModelChange}
          selectedPersonaId={selectedPersonaId}
          selectedCustomPrompt={customSystemPrompt}
          onPersonaChange={handlePersonaChange}
          onCustomPromptChange={setCustomSystemPrompt}
          currentSessionId={currentSessionId}
          onSessionUpdate={handleSessionUpdate}
          busy={busy}
        />

        {/* Chat Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {error && (
            <div className="mx-4 rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200 animate-in slide-in-from-top-2">
              {error}
            </div>
          )}
          {messages.length === 0 && !busy && (
            <div className="flex flex-col items-center justify-center h-full min-h-[60vh] text-center">
              <svg className="w-16 h-16 text-slate-700 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <h2 className="text-xl font-medium text-slate-300 mb-2">Welcome to PROFESSOR-J</h2>
              <p className="text-slate-500 max-w-md">
                Ask me anything — explain a concept, solve a problem, write code, or just chat.
              </p>
              <div className="mt-6 flex flex-wrap gap-2 justify-center text-sm">
                <span className="px-3 py-1.5 rounded-full border border-white/10 bg-white/5 text-slate-400">&ldquo;Teach me Newton&rsquo;s second law&rdquo;</span>
                <span className="px-3 py-1.5 rounded-full border border-white/10 bg-white/5 text-slate-400">&ldquo;Debug this Python code&rdquo;</span>
                <span className="px-3 py-1.5 rounded-full border border-white/10 bg-white/5 text-slate-400">&ldquo;Explain quantum entanglement&rdquo;</span>
                <span className="px-3 py-1.5 rounded-full border border-white/10 bg-white/5 text-slate-400">&ldquo;Write a React component&rdquo;</span>
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                  m.role === "user"
                    ? "bg-indigo-500/80 text-white rounded-br-md"
                    : "border border-white/10 bg-slate-800/60 text-slate-100 rounded-bl-md"
                }`}
              >
                {m.isEditing && m.role === "user" && editingMessageIndex === i ? (
                  <div className="flex flex-col gap-2">
                    <textarea
                      value={m.editContent || m.content}
                      onChange={(e) => {
                        const updated = [...messages];
                        updated[i] = { ...updated[i], editContent: e.target.value, isEditing: true };
                        setMessages(updated);
                      }}
                      className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 font-mono focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 min-h-[60px] resize-y"
                      autoFocus
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => handleCancelEdit()}
                        className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5 text-sm"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleSaveEdit(i, messages[i].editContent || messages[i].content)}
                        className="px-3 py-1.5 rounded-lg bg-cyan-500 text-white hover:bg-cyan-600 text-sm"
                        disabled={busy}
                      >
                        Save & Resend
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="whitespace-pre-wrap">{m.content}</div>
                    {m.role === "assistant" && (m.intent || m.provider) && (
                      <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-400">
                        {m.intent && (
                          <span className="rounded-full bg-cyan-500/20 px-2 py-0.5 text-cyan-300">
                            intent: {m.intent}
                          </span>
                        )}
                        {m.provider && (
                          <span className="rounded-full bg-fuchsia-500/20 px-2 py-0.5 text-fuchsia-300">
                            {m.provider}
                          </span>
                        )}
                        <MessageTTSButton text={m.content} />
                      </div>
                    )}
                    {m.role === "user" && !m.isEditing && (
                      <div className="mt-2 flex justify-end gap-1">
                        <button
                          onClick={() => handleEditMessage(i)}
                          className="p-1.5 rounded hover:bg-white/10 text-slate-400 hover:text-slate-100 transition text-[11px]"
                          title="Edit & Resend"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                        </button>
                        <button
                          onClick={() => handleResend(i)}
                          className="p-1.5 rounded hover:bg-white/10 text-slate-400 hover:text-slate-100 transition text-[11px]"
                          title="Resend"
                          disabled={busy}
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}

          {busy && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-2xl border border-white/10 bg-slate-800/60 text-slate-100 rounded-bl-md px-4 py-3 text-sm">
                <div className="flex items-center gap-2 text-slate-400">
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-cyan-400" />
                  <span>Thinking...</span>
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-cyan-400" style={{ animationDelay: "100ms" }} />
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-cyan-400" style={{ animationDelay: "200ms" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* File Attachment Preview (floating above input) */}
        {attachedFile && (
          <div className="mx-4 mb-2 animate-in slide-in-from-bottom-2">
            <div className="flex items-center gap-2 p-3 rounded-xl border border-white/10 bg-white/5 max-w-2xl">
              <span className="text-cyan-400">📎</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-100 truncate">
                  {attachedFile.original_name}
                </p>
                <p className="text-xs text-slate-500">
                  {attachedFile.content_type} • {(attachedFile.size / 1024).toFixed(1)} KB
                </p>
              </div>
              <button
                onClick={() => setAttachedFile(null)}
                className="p-1.5 rounded hover:bg-white/10 text-slate-400 hover:text-slate-100 transition"
                title="Remove attachment"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="p-4 border-t border-white/10 bg-slate-950/80 backdrop-blur-sm">
          <FileUpload onFileUpload={setAttachedFile} />
          <form onSubmit={submit} className="flex flex-col gap-2">
            <div className="flex gap-2 items-flex-end">
              <VoiceInputButton
                onTranscript={(text) => {
                  setInput((prev) => prev + (prev ? " " : "") + text);
                }}
                disabled={busy || !currentSessionId}
                className="flex-shrink-0"
              />
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a message..."
                disabled={busy || !currentSessionId}
                rows={1}
                className="flex-1 min-h-[44px] max-h-[200px] resize-none rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-cyan-400/50 transition"
                style={{ overflow: "auto" }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submit(e as unknown as React.FormEvent);
                  }
                }}
              />
              <button
                type="submit"
                disabled={busy || (!input.trim() && !attachedFile) || !currentSessionId}
                className="flex-shrink-0 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 px-5 py-3 text-sm font-semibold text-white transition disabled:opacity-40 hover:from-cyan-600 hover:to-indigo-600"
                aria-label="Send message"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
              {busy && (
                <button
                  type="button"
                  onClick={() => {
                    (window as Window & { __currentAbortController?: AbortController }).__currentAbortController?.abort();
                    setBusy(false);
                    setError("Request cancelled");
                  }}
                  className="flex-shrink-0 rounded-xl border border-rose-500/50 bg-rose-500/10 px-5 py-3 text-sm font-semibold text-rose-300 hover:bg-rose-500/20 transition"
                  aria-label="Cancel request"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          </form>
          {!currentSessionId && (
            <p className="mt-2 text-center text-sm text-slate-500">
              Select or create a session from the sidebar to start chatting.
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
