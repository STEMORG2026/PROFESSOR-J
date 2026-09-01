import { useState, useEffect, useCallback } from "react";

export type GlobalDefaults = {
  provider: string | null;
  model: string | null;
  system_prompt: string | null;
  base_url: string | null;
};

export type ProviderApiKey = {
  key: string;
  value: string | null;
};

export function useGlobalSettings() {
  const [defaults, setDefaults] = useState<GlobalDefaults>({
    provider: null,
    model: null,
    system_prompt: null,
    base_url: null,
  });
  const [providerKeys, setProviderKeys] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDefaults = useCallback(async () => {
    try {
      const res = await fetch("/api/defaults");
      if (!res.ok) throw new Error("Failed to fetch defaults");
      const data = await res.json();
      const mapped: GlobalDefaults = {
        provider: null,
        model: null,
        system_prompt: null,
        base_url: null,
      };
      data.forEach((item: { key: string; value: string | null }) => {
        if (item.key in mapped) {
          mapped[item.key as keyof GlobalDefaults] = item.value;
        }
      });
      setDefaults(mapped);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }, []);

  const fetchProviderKeys = useCallback(async () => {
    try {
      const res = await fetch("/api/settings");
      if (!res.ok) throw new Error("Failed to fetch provider keys");
      const data = await res.json();
      const mapped: Record<string, string> = {};
      data.forEach((item: { key: string; value: string | null }) => {
        if (item.value) mapped[item.key] = item.value;
      });
      setProviderKeys(mapped);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }, []);

  useEffect(() => {
    Promise.all([fetchDefaults(), fetchProviderKeys()]).finally(() => setLoading(false));
  }, [fetchDefaults, fetchProviderKeys]);

  const updateDefault = async (key: keyof GlobalDefaults, value: string | null) => {
    const res = await fetch("/api/defaults", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, value }),
    });
    if (!res.ok) throw new Error("Failed to update default");
    setDefaults((prev) => ({ ...prev, [key]: value }));
  };

  const updateProviderKey = async (configKey: string, value: string) => {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: configKey, value }),
    });
    if (!res.ok) throw new Error("Failed to update provider key");
    setProviderKeys((prev) => ({ ...prev, [configKey]: value }));
  };

  return {
    defaults,
    providerKeys,
    loading,
    error,
    refetch: () => Promise.all([fetchDefaults(), fetchProviderKeys()]),
    updateDefault,
    updateProviderKey,
  };
}
