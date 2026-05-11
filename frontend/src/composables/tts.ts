// Thin wrapper around the browser's Web Speech API. No-op if unsupported
// (older browsers, some embedded webviews). Picks the best available
// US-English voice once and caches it.

let cachedVoice: SpeechSynthesisVoice | null = null;
let voicesLoaded = false;

function loadVoice(): SpeechSynthesisVoice | null {
  if (cachedVoice) return cachedVoice;
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (voices.length === 0) return null;
  // Prefer Google / Samantha / Alex / Microsoft natural voices, en-US
  const preferred =
    voices.find((v) => /en-US/i.test(v.lang) && /(Google|Samantha|Microsoft.*Natural)/i.test(v.name)) ||
    voices.find((v) => /en-US/i.test(v.lang)) ||
    voices.find((v) => /^en/i.test(v.lang)) ||
    voices[0];
  cachedVoice = preferred;
  voicesLoaded = true;
  return cachedVoice;
}

if (typeof window !== "undefined" && "speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = () => {
    cachedVoice = null;
    loadVoice();
  };
  // Try once now in case voices are already loaded
  loadVoice();
}

export function isSpeechSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function speak(text: string, opts: { rate?: number; lang?: string } = {}) {
  if (!isSpeechSupported() || !text.trim()) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const voice = loadVoice();
  if (voice) u.voice = voice;
  u.lang = opts.lang ?? "en-US";
  u.rate = opts.rate ?? 0.9;
  u.pitch = 1;
  synth.speak(u);
}

export function stopSpeaking() {
  if (!isSpeechSupported()) return;
  window.speechSynthesis.cancel();
}

// Mark voicesLoaded as referenced (used in some debugging contexts)
export const _voicesLoaded = () => voicesLoaded;
