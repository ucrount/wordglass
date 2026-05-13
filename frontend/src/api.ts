// Tiny fetch-based API client. Adds auth token if present, normalizes errors.

export interface Example {
  id: number;
  en: string;
  zh: string;
}

export interface WordOut {
  id: number;
  text: string;
  phonetic: string;
  pos: string;
  translation: string;
  category: string;
  mastery: number;
  review_count: number;
  correct_count: number;
  created_at: string;
  next_review_at: string;
  examples: Example[];
}

export interface WordBrief {
  id: number;
  text: string;
  phonetic: string;
  translation: string;
  category: string;
  mastery: number;
  created_at: string;
}

export interface CategoriesOut {
  counts: Record<string, number>;
  order: string[];
}

export type WordPreview =
  | { found: true; text: string; phonetic: string; pos: string; translation: string; already_saved: boolean }
  | { found: false; text: string };

export interface Stats {
  total: number;
  due_today: number;
  mastered: number;
  added_this_week: number;
}

export interface HeatmapData {
  days: Record<string, number>; // "YYYY-MM-DD" → count
  since: string;
}

export type ReviewResult = "again" | "hard" | "good" | "easy";

export type ProviderType = "openai" | "anthropic" | "google";

export interface SettingsOut {
  provider_type: ProviderType;
  base_url: string;
  api_key_set: boolean;
  api_key_preview: string;
  model: string;
  auth_token_set: boolean;
  configured: boolean;
}

export interface SettingsIn {
  provider_type?: ProviderType;
  base_url?: string;
  api_key?: string;
  model?: string;
  auth_token?: string;
}

export interface ProviderPreset {
  id: ProviderType;
  label: string;
  description: string;
  examples: { name: string; base_url: string; model: string }[];
}

export interface TestResult {
  ok: boolean;
  echo?: string;
  error?: string;
}

export interface TestResultV2 {
  ok: boolean;
  category: "ok" | "dns" | "connect" | "timeout" | "auth" | "not_found" | "rate_limit" | "upstream" | "unknown" | string;
  detail: string;
  raw: string;
  echo: string;
  ms: number;
}

export interface AiCallRecord {
  id: number;
  ts: number;
  kind: "chat" | "stream";
  provider: string;
  model: string;
  base_url: string;
  system: string;
  user: string;
  response: string;
  status: "ok" | "error";
  error?: string | null;
  http_status?: number | null;
  json_mode?: boolean | null;
  max_tokens?: number | null;
  chunks?: number | null;
  first_chunk_ms?: number | null;
  ms: number;
}

export interface SystemLogRecord {
  id: number;
  ts: number;
  event: string;
  [key: string]: unknown;
}

export interface CurlReq {
  provider_type: ProviderType;
  base_url: string;
  api_key: string;
  model: string;
  reveal_key: boolean;
}

const TOKEN_KEY = "wordglass.token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(path, { ...init, headers });
  if (!resp.ok) {
    let detail = `${resp.status}`;
    try {
      const body = await resp.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      detail = await resp.text();
    }
    // Let global UI react (e.g. show the token dialog on 401)
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("wordglass:api-error", { detail: { status: resp.status, message: detail } })
      );
    }
    throw new ApiError(detail, resp.status);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

async function streamSSE(
  path: string,
  body: unknown,
  onDelta: (text: string) => void,
  onError: (msg: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers = new Headers({ "Content-Type": "application/json" });
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  try {
    const resp = await fetch(path, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal,
    });
    if (!resp.ok) {
      let detail = `${resp.status}`;
      try {
        const j = await resp.json();
        detail = j.detail ?? JSON.stringify(j);
      } catch {
        try { detail = await resp.text(); } catch { /* keep status */ }
      }
      onError(detail);
      return;
    }
    if (!resp.body) {
      onError("流式响应不可读");
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        const rawEvent = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 2);
        if (!rawEvent.startsWith("data:")) continue;
        const payload = rawEvent.slice(5).trim();
        if (payload === "[DONE]") return;
        try {
          const obj = JSON.parse(payload);
          if (obj.error) { onError(obj.error); return; }
          if (typeof obj.delta === "string") onDelta(obj.delta);
        } catch { /* malformed chunk — ignore */ }
      }
    }
  } catch (e: unknown) {
    const err = e as { name?: string; message?: string };
    if (err?.name === "AbortError") return;
    onError(err?.message || "网络错误");
  }
}

export const api = {
  health: () => request<{ ok: boolean }>("/api/health"),
  stats: () => request<Stats>("/api/stats"),
  heatmap: (days = 35) => request<HeatmapData>(`/api/stats/heatmap?days=${days}`),

  addWord: (text: string) =>
    request<WordOut>("/api/words", { method: "POST", body: JSON.stringify({ text }) }),
  listWords: (params: { q?: string; category?: string; mastery?: number; limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && q.set(k, String(v)));
    const suffix = q.toString() ? `?${q}` : "";
    return request<WordBrief[]>(`/api/words${suffix}`);
  },
  getWord: (id: number) => request<WordOut>(`/api/words/${id}`),
  deleteWord: (id: number) =>
    request<{ ok: boolean }>(`/api/words/${id}`, { method: "DELETE" }),
  listCategories: () => request<CategoriesOut>("/api/words/categories"),
  recategorize: () =>
    request<{ updated: number; total: number }>("/api/words/recategorize", { method: "POST" }),
  offlineStatus: () =>
    request<{ ecdict: boolean; tatoeba: boolean }>("/api/words/offline-status"),
  previewWord: (text: string) =>
    request<WordPreview>(`/api/words/preview?text=${encodeURIComponent(text)}`),
  translateText: (text: string, target_lang: "zh" | "en" = "zh") =>
    request<{ translation: string }>("/api/translate", {
      method: "POST",
      body: JSON.stringify({ text, target_lang }),
    }),
  translateTextStream: (
    text: string,
    target_lang: "zh" | "en",
    onDelta: (t: string) => void,
    onError: (m: string) => void,
    signal?: AbortSignal,
  ) => streamSSE("/api/translate/stream", { text, target_lang }, onDelta, onError, signal),

  wordUsageStream: (
    text: string,
    onDelta: (t: string) => void,
    onError: (m: string) => void,
    signal?: AbortSignal,
  ) => streamSSE("/api/words/usage", { text }, onDelta, onError, signal),

  dueWords: (limit = 50) => request<WordOut[]>(`/api/review/due?limit=${limit}`),
  submitReview: (word_id: number, mode: string, result: ReviewResult) =>
    request<{ ok: boolean; mastery: number; next_review_at: string }>("/api/review", {
      method: "POST",
      body: JSON.stringify({ word_id, mode, result }),
    }),

  // Settings
  getSettings: () => request<SettingsOut>("/api/settings"),
  listPresets: () => request<{ presets: ProviderPreset[] }>("/api/settings/presets"),
  saveSettings: (payload: SettingsIn) =>
    request<SettingsOut>("/api/settings", { method: "PUT", body: JSON.stringify(payload) }),
  testSettings: (payload: SettingsIn) =>
    request<TestResult>("/api/settings/test", { method: "POST", body: JSON.stringify(payload) }),
  listModels: (payload: SettingsIn) =>
    request<{ models: string[] }>("/api/settings/models", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // ── Settings v2 ──────────────────────────────────────────────────
  testSettingsV2: (payload: SettingsIn) =>
    request<TestResultV2>("/api/settings/test", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  generateCurl: (payload: CurlReq) =>
    request<{ command: string }>("/api/settings/curl", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listAiLogs: (kind?: string, limit = 50) => {
    const q = new URLSearchParams();
    q.set("limit", String(limit));
    if (kind) q.set("kind", kind);
    return request<{ items: AiCallRecord[] }>(`/api/settings/logs/ai?${q}`);
  },

  clearAiLogs: () =>
    request<{ ok: boolean }>("/api/settings/logs/ai/clear", { method: "POST" }),

  listSystemLogs: (event_prefix?: string, limit = 200) => {
    const q = new URLSearchParams();
    q.set("limit", String(limit));
    if (event_prefix) q.set("event_prefix", event_prefix);
    return request<{ items: SystemLogRecord[] }>(`/api/settings/logs/system?${q}`);
  },

  clearSystemLogs: () =>
    request<{ ok: boolean }>("/api/settings/logs/system/clear", { method: "POST" }),

  streamSystemLogs: (
    onRecord: (r: SystemLogRecord) => void,
    onError: (m: string) => void,
    signal?: AbortSignal,
  ) =>
    streamSSE(
      "/api/settings/logs/system/stream",
      {},
      (delta) => {
        try {
          const obj = JSON.parse(delta) as SystemLogRecord;
          onRecord(obj);
        } catch { /* ignore malformed */ }
      },
      onError,
      signal,
    ),
};
