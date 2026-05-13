import { computed, ref } from "vue";

const TOKEN_KEY = "wordglass.jwt";
const USER_KEY = "wordglass.user";

export interface CurrentUser {
  id: number;
  username: string;
  is_admin: boolean;
}

const _token = ref<string>(localStorage.getItem(TOKEN_KEY) || "");
const _user = ref<CurrentUser | null>(
  (() => {
    try {
      const raw = localStorage.getItem(USER_KEY);
      return raw ? (JSON.parse(raw) as CurrentUser) : null;
    } catch {
      return null;
    }
  })(),
);

export function useAuth() {
  return {
    token: computed(() => _token.value),
    user: computed(() => _user.value),
    isAuthed: computed(() => !!_token.value && !!_user.value),
    isAdmin: computed(() => !!_user.value?.is_admin),
    setSession(token: string, user: CurrentUser) {
      _token.value = token;
      _user.value = user;
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    },
    clearSession() {
      _token.value = "";
      _user.value = null;
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    },
  };
}
