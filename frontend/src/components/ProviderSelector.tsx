"use client";

export type ProviderDef = {
  id: string;
  name: string;
  models: string[];
  description: string;
  freeTier: boolean;
  apiKeyRequired: boolean;
  configKey: string;
  baseUrl?: string;
  customBaseUrl?: boolean;
};

const PROVIDERS: ProviderDef[] = [
  {
    id: "openrouter",
    name: "OpenRouter",
    models: [
      "openrouter/auto",
      "anthropic/claude-3.5-sonnet",
      "anthropic/claude-sonnet-4-20250514",
      "anthropic/claude-3-opus",
      "google/gemini-2.5-pro-exp-03-25",
      "google/gemini-2.5-flash-exp-08-27",
      "google/gemini-pro-1.5",
      "meta-llama/llama-4-scout-17b-16e-instruct",
      "meta-llama/llama-3.1-405b",
      "meta-llama/llama-3.3-70b-instruct",
      "mistralai/mistral-large-2411",
      "mistralai/mistral-saba-2502",
      "deepseek/deepseek-chat",
      "deepseek/deepseek-r1",
      "qwen/qwen-2.5-72b-instruct",
    ],
    description: "Access 100+ models via single API key",
    freeTier: true,
    apiKeyRequired: true,
    configKey: "openrouter_api_key",
    baseUrl: "https://openrouter.ai/api/v1",
  },
  {
    id: "nvidia_nim",
    name: "NVIDIA NIM",
    models: [
      "nvidia/nemotron-3-ultra",
      "nvidia/llama-3.1-nemotron-70b",
      "meta/llama-3.1-405b-instruct",
      "meta/llama-3.3-70b-instruct",
    ],
    description: "NVIDIA optimized models with NIM microservices",
    freeTier: true,
    apiKeyRequired: true,
    configKey: "nvidia_nim_api_key",
    baseUrl: "https://integrate.api.nvidia.com/v1",
  },
  {
    id: "google_ai",
    name: "Google AI (Gemini)",
    models: [
      "gemini-2.5-pro-exp-03-25",
      "gemini-2.5-flash-exp-08-27",
      "gemini-1.5-pro",
      "gemini-1.5-flash",
      "gemini-1.0-pro",
    ],
    description: "Google's Gemini models with free tier",
    freeTier: true,
    apiKeyRequired: true,
    configKey: "google_ai_api_key",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta",
  },
  {
    id: "openai_compat",
    name: "OpenAI Compatible",
    models: [
      "gpt-4o",
      "gpt-4o-mini",
      "gpt-4-turbo",
      "gpt-3.5-turbo",
      "claude-3-5-sonnet-20241022",
      "claude-3-opus-20240229",
      "deepseek-chat",
      "deepseek-r1",
    ],
    description:
      "Any OpenAI-compatible endpoint (Singularity, Ollama, vLLM, llama.cpp, etc.)",
    freeTier: false,
    apiKeyRequired: true,
    configKey: "openai_api_key",
    baseUrl: "",
    customBaseUrl: true,
  },
  {
    id: "mock",
    name: "Mock (Offline)",
    models: ["mock-model"],
    description:
      "Deterministic offline provider — no API key needed, for testing",
    freeTier: true,
    apiKeyRequired: false,
    configKey: "",
  },
] as ProviderDef[];

export function ProviderSelector({
  selectedProvider,
  onProviderChange,
  selectedModel,
  onModelChange,
  apiKeys,
  onApiKeyChange,
  baseUrl,
  onBaseUrlChange,
  isLoading = false,
}: {
  selectedProvider: string;
  onProviderChange: (providerId: string) => void;
  selectedModel: string;
  onModelChange: (model: string) => void;
  apiKeys: Record<string, string>;
  onApiKeyChange: (configKey: string, key: string) => void;
  baseUrl: string;
  onBaseUrlChange: (url: string) => void;
  isLoading?: boolean;
}) {
  const provider =
    PROVIDERS.find((p) => p.id === selectedProvider) ?? PROVIDERS[0];

  return (
    <div className="space-y-5">
      {/* Provider Selection */}
      <div>
        <label className="mb-2 block text-sm font-medium text-slate-300">
          Provider
        </label>
        <select
          value={selectedProvider}
          onChange={(e) => onProviderChange(e.target.value)}
          disabled={isLoading}
          className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-slate-100 transition-all focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
        >
          {PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}{" "}
              {p.freeTier ? "(Free tier)" : null}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-slate-500">{provider.description}</p>
      </div>

      {/* Base URL (only for openai_compat) */}
      {provider.customBaseUrl && (
        <div>
          <label className="mb-2 block text-sm font-medium text-slate-300">
            Base URL
          </label>
          <input
            type="url"
            value={baseUrl}
            onChange={(e) => onBaseUrlChange(e.target.value)}
            placeholder="https://api.openai.com/v1"
            disabled={isLoading}
            className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-slate-100 placeholder-slate-500 transition-all focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
          />
          <p className="mt-1 text-xs text-slate-500">
            e.g.{" "}
            <code className="rounded bg-white/10 px-1 text-cyan-300">
              https://api.singularity.ai/v1
            </code>{" "}
            or{" "}
            <code className="rounded bg-white/10 px-1 text-cyan-300">
              http://localhost:11434/v1
            </code>
          </p>
        </div>
      )}

      {/* Model Selection */}
      <div>
        <label className="mb-2 block text-sm font-medium text-slate-300">
          Model
        </label>
        <select
          value={selectedModel}
          onChange={(e) => onModelChange(e.target.value)}
          disabled={isLoading}
          className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-slate-100 transition-all focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
        >
          {provider.models.map((model) => (
            <option key={model} value={model}>
              {model}
            </option>
          ))}
        </select>
      </div>

      {/* API Key Management */}
      {provider.apiKeyRequired && (
        <div className="border-t border-white/10 pt-4">
          <label className="mb-2 block text-sm font-medium text-slate-300">
            API Key
          </label>
          <div className="relative">
            <input
              type="password"
              value={apiKeys[provider.configKey] ?? ""}
              onChange={(e) =>
                onApiKeyChange(provider.configKey, e.target.value)
              }
              placeholder={`Enter ${provider.name} API key...`}
              disabled={isLoading}
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-slate-100 placeholder-slate-500 transition-all focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            />
            {(apiKeys[provider.configKey] ?? "").length > 0 && (
              <p className="mt-1 text-xs text-green-400">
                API key configured ✓
              </p>
            )}
          </div>
        </div>
      )}

      {provider.freeTier && !provider.apiKeyRequired && (
        <div className="pt-4 text-center">
          <p className="text-sm text-green-400">
            ✓ {provider.name} — no API key required
          </p>
        </div>
      )}
    </div>
  );
}

export { PROVIDERS };
export default ProviderSelector;
