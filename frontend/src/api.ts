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
  mastery: number;
  created_at: string;
}

export interface Stats {
  total: number;
  due_today: number;
  mastered: number;
  added_this_week: number;
}

export type ReviewResult = "again" | "hard" | "good" | "easy";

const TOKEN_KEY = "wordglass.token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
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
    throw new Error(detail);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export const api = {
  health: () => request<{ ok: boolean }>("/api/health"),
  stats: () => request<Stats>("/api/stats"),

  addWord: (text: string) =>
    request<WordOut>("/api/words", { method: "POST", body: JSON.stringify({ text }) }),
  listWords: (params: { q?: string; mastery?: number; limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && q.set(k, String(v)));
    const suffix = q.toString() ? `?${q}` : "";
    return request<WordBrief[]>(`/api/words${suffix}`);
  },
  getWord: (id: number) => request<WordOut>(`/api/words/${id}`),
  deleteWord: (id: number) =>
    request<{ ok: boolean }>(`/api/words/${id}`, { method: "DELETE" }),

  dueWords: (limit = 50) => request<WordOut[]>(`/api/review/due?limit=${limit}`),
  submitReview: (word_id: number, mode: string, result: ReviewResult) =>
    request<{ ok: boolean; mastery: number; next_review_at: string }>("/api/review", {
      method: "POST",
      body: JSON.stringify({ word_id, mode, result }),
    }),
};
