"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  intent?: string;
  provider?: string;
  sessionId?: string;
};

const SESSION_ID =
  typeof window !== "undefined" && window.sessionStorage.getItem("professor-session")
    ? (window.sessionStorage.getItem("professor-session") as string)
    : `sess-${Math.random().toString(36).slice(2, 10)}`;

if (typeof window !== "undefined") {
  window.sessionStorage.setItem("professor-session", SESSION_ID);
}

export default function ChatCanvas() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text, session_id: SESSION_ID }),
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`API ${res.status}: ${body.slice(0, 120)}`);
      }
      const data = await res.json();
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.response,
          intent: data.intent,
          provider: data.provider,
          sessionId: data.session_id,
        },
      ]);
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
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-4 py-6">
      <header className="mb-6">
        <h1 className="bg-gradient-to-r from-cyan-300 via-indigo-300 to-fuchsia-300 bg-clip-text text-3xl font-bold text-transparent">
          PROFESSOR-J
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Socratic STEM tutoring canvas — talks to the FastAPI backend via{" "}
          <code className="rounded bg-white/10 px-1.5 py-0.5 text-cyan-300">/api/chat</code>
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}

      <div className="flex-1 space-y-4 overflow-y-auto rounded-xl border border-white/10 bg-white/[0.03] p-4">
        {messages.length === 0 && !busy && (
          <p className="text-center text-sm text-slate-500">
            Ask anything — e.g. “teach me Newton’s second law”.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm ${
                m.role === "user"
                  ? "bg-indigo-500/80 text-white"
                  : "border border-white/10 bg-slate-800/60 text-slate-100"
              }`}
            >
              {m.content}
              {m.role === "assistant" && (m.intent || m.provider) && (
                <div className="mt-2 flex gap-2 text-[11px] text-slate-400">
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
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-cyan-400" />
            thinking…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={submit} className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          disabled={busy}
          className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-cyan-400/50"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-500 px-5 py-3 text-sm font-semibold text-white transition disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </main>
  );
}
