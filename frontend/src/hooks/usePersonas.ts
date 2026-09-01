import { useState, useEffect, useCallback } from "react";

export type Persona = {
  persona_id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  created_at: string;
  updated_at: string;
};

export function usePersonas() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPersonas = useCallback(async () => {
    try {
      const res = await fetch("/api/personas");
      if (!res.ok) throw new Error("Failed to fetch personas");
      const data = await res.json();
      setPersonas(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPersonas();
  }, [fetchPersonas]);

  const createPersona = async (name: string, system_prompt: string, description?: string) => {
    const res = await fetch("/api/personas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, system_prompt, description }),
    });
    if (!res.ok) throw new Error("Failed to create persona");
    const persona = await res.json();
    setPersonas((prev) => [persona, ...prev]);
    return persona;
  };

  const updatePersona = async (personaId: string, updates: Partial<Persona>) => {
    const res = await fetch(`/api/personas/${personaId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error("Failed to update persona");
    const persona = await res.json();
    setPersonas((prev) => prev.map((p) => (p.persona_id === personaId ? persona : p)));
    return persona;
  };

  const deletePersona = async (personaId: string) => {
    const res = await fetch(`/api/personas/${personaId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete persona");
    setPersonas((prev) => prev.filter((p) => p.persona_id !== personaId));
  };

  return { personas, loading, error, fetchPersonas, createPersona, updatePersona, deletePersona };
}
