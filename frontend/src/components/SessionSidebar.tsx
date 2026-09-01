"use client";

import { useEffect, useState, useCallback } from "react";

export type Session = {
  session_id: string;
  learner_id: string;
  title: string | null;
  status: string;
  provider: string | null;
  model: string | null;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
};

const LEARNER_ID = "default";

interface SessionSidebarProps {
  currentSessionId: string | null;
  onSessionSelect: (sessionId: string) => void;
  onNewSession: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function SessionSidebar({
  currentSessionId,
  onSessionSelect,
  onNewSession,
  isCollapsed = false,
  onToggleCollapse,
}: SessionSidebarProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showNewSessionModal, setShowNewSessionModal] = useState(false);
  const [newSessionTitle, setNewSessionTitle] = useState("");
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");

  const loadSessions = useCallback(async () => {
    try {
      const res = await fetch(`/api/sessions?learner_id=${LEARNER_ID}&limit=50`);
      if (!res.ok) throw new Error("Failed to load sessions");
      const data = await res.json();
      setSessions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleCreateSession = async () => {
    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          learner_id: LEARNER_ID,
          title: newSessionTitle || "New Chat",
        }),
      });
      if (!res.ok) throw new Error("Failed to create session");
      const session = await res.json();
      setShowNewSessionModal(false);
      setNewSessionTitle("");
      await loadSessions();
      onSessionSelect(session.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create session");
    }
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this session?")) return;
    try {
      const res = await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete session");
      await loadSessions();
      if (currentSessionId === sessionId) {
        onNewSession();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete session");
    }
  };

  const handleStartRename = (session: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingSessionId(session.session_id);
    setRenameTitle(session.title || "");
  };

  const handleSaveRename = async (sessionId: string) => {
    try {
      const res = await fetch(`/api/sessions/${sessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: renameTitle }),
      });
      if (!res.ok) throw new Error("Failed to rename session");
      setRenamingSessionId(null);
      setRenameTitle("");
      await loadSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename session");
    }
  };

  const handleCancelRename = () => {
    setRenamingSessionId(null);
    setRenameTitle("");
  };

  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (isCollapsed) {
    return (
      <aside className="w-14 flex flex-col border-r border-white/10 bg-white/[0.02] h-full overflow-y-auto">
        <div className="p-3 border-b border-white/10 flex justify-center">
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-slate-100 transition"
            aria-label="Expand sidebar"
            title="Expand sidebar"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
        <div className="flex-1 p-2 space-y-1 overflow-y-auto">
          {sessions.map((session) => (
            <button
              key={session.session_id}
              onClick={() => onSessionSelect(session.session_id)}
              className={`w-full p-2 rounded-xl transition flex items-center justify-center ${
                currentSessionId === session.session_id
                  ? "bg-cyan-500/10 text-cyan-300"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
              }`}
              title={session.title || "Untitled"}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </button>
          ))}
        </div>
        <div className="p-2 border-t border-white/10">
          <button
            onClick={() => setShowNewSessionModal(true)}
            className="w-full p-2 rounded-xl text-slate-400 hover:bg-white/5 hover:text-slate-100 transition flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
          </button>
        </div>
      </aside>
    );
  }

  if (loading) {
    return (
      <aside className="w-72 flex flex-col border-r border-white/10 bg-white/[0.02] h-full overflow-y-auto">
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <h2 className="font-semibold text-slate-100">Chats</h2>
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-slate-100 transition"
            aria-label="Collapse sidebar"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        </div>
        <div className="flex-1 p-4 text-center text-slate-500">Loading...</div>
      </aside>
    );
  }

  return (
    <aside className="w-72 flex flex-col border-r border-white/10 bg-white/[0.02] h-full overflow-y-auto">
      <div className="p-4 border-b border-white/10 flex items-center justify-between">
        <h2 className="font-semibold text-slate-100">Chats</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-slate-100 transition"
            aria-label="Collapse sidebar"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <button
            onClick={() => setShowNewSessionModal(true)}
            className="text-sm px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 transition flex items-center gap-1.5"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            New
          </button>
        </div>
      </div>

      {error && (
        <div className="m-3 p-2 rounded-lg border border-rose-500/40 bg-rose-500/10 text-sm text-rose-200">
          {error}
        </div>
      )}

      <div className="flex-1 p-3 space-y-1 overflow-y-auto">
        {sessions.length === 0 && (
          <div className="text-center text-sm text-slate-500 mt-8 flex flex-col items-center gap-2">
            <svg className="w-12 h-12 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p>No chats yet</p>
            <button
              onClick={() => setShowNewSessionModal(true)}
              className="text-sm px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 transition"
            >
              Create your first chat
            </button>
          </div>
        )}
        {sessions.map((session) => {
          const isActive = currentSessionId === session.session_id;
          const isRenaming = renamingSessionId === session.session_id;

          return (
            <div
              key={session.session_id}
              className={`group relative ${
                isActive ? "bg-cyan-500/5" : "hover:bg-white/3"
              } rounded-xl transition`}
            >
              {isRenaming ? (
                <div className="p-2.5 flex items-center gap-2">
                  <input
                    type="text"
                    value={renameTitle}
                    onChange={(e) => setRenameTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleSaveRename(session.session_id);
                      if (e.key === "Escape") handleCancelRename();
                    }}
                    autoFocus
                    className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-slate-100 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                    placeholder="Session title"
                  />
                  <button
                    onClick={() => handleSaveRename(session.session_id)}
                    className="p-1.5 rounded hover:bg-white/10 text-slate-400 hover:text-slate-100 transition"
                    title="Save"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  </button>
                  <button
                    onClick={handleCancelRename}
                    className="p-1.5 rounded hover:bg-white/10 text-slate-400 hover:text-slate-100 transition"
                    title="Cancel"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
              ) : (
                <div
                  onClick={() => onSessionSelect(session.session_id)}
                  className={`w-full flex items-center gap-3 p-2.5 rounded-xl cursor-pointer transition ${
                    isActive
                      ? "bg-cyan-500/5 border border-cyan-500/20"
                      : "hover:bg-white/3"
                  }`}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSessionSelect(session.session_id);
                    }
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate ${isActive ? "text-slate-100" : "text-slate-300"}`}>
                      {session.title || "Untitled"}
                    </p>
                    <p className="text-xs text-slate-500 truncate">{formatTime(session.updated_at)}</p>
                  </div>
                  <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition">
                    <button
                      onClick={(e) => handleStartRename(session, e)}
                      className="p-1.5 rounded hover:bg-white/10 text-slate-400 hover:text-slate-100 transition"
                      title="Rename"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                    </button>
                    <button
                      onClick={(e) => handleDeleteSession(session.session_id, e)}
                      className="p-1.5 rounded hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 transition"
                      title="Delete"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* New Session Modal */}
      {showNewSessionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 animate-in fade-in-0" onClick={() => setShowNewSessionModal(false)}>
          <div className="bg-slate-900 rounded-xl p-6 w-full max-w-md border border-white/10 animate-in zoom-in-95" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">New Chat Session</h3>
            <input
              type="text"
              value={newSessionTitle}
              onChange={(e) => setNewSessionTitle(e.target.value)}
              placeholder="Session title (optional)"
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 mb-4"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowNewSessionModal(false)}
                className="px-4 py-2 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateSession}
                className="px-4 py-2 rounded-lg bg-cyan-500 text-white hover:bg-cyan-600"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

export default SessionSidebar;
