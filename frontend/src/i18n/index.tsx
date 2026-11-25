// This module colocates the provider component with its hooks/constants — a
// standard React context pattern. Fast-refresh's component-only rule is a
// false positive here (nothing in it is hot-reloaded as a component tree).
/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getToken } from "../api/session";
import { useApi } from "../hooks/useApi";
import {
  LANGUAGES,
  translate,
  type Lang,
  type StringKey,
} from "./strings";

const LANG_KEY = "chatbot_lang";

export type { Lang } from "./strings";
export { LANGUAGES, LANGUAGE_LABELS } from "./strings";

function isLang(v: string | null | undefined): v is Lang {
  return v != null && (LANGUAGES as readonly string[]).includes(v);
}

/** Initial language: localStorage cache → browser preference → English. The
 * server profile (fetched after auth) overrides this via {@link syncLanguage}. */
function detectInitialLang(): Lang {
  const stored = localStorage.getItem(LANG_KEY);
  if (isLang(stored)) return stored;
  const nav = navigator.language?.slice(0, 2).toLowerCase();
  return isLang(nav) ? nav : "en";
}

type TFunc = (key: StringKey, vars?: Record<string, string | number>) => string;

interface LanguageContextValue {
  lang: Lang;
  t: TFunc;
  /** User-initiated change: updates the UI, caches locally, and (when signed
   * in) persists to the server. */
  setLanguage: (lang: Lang) => void;
  /** Seed from the server profile: updates the UI + cache without re-persisting. */
  syncLanguage: (lang: Lang) => void;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const [lang, setLang] = useState<Lang>(detectInitialLang);

  const t = useCallback<TFunc>((key, vars) => translate(lang, key, vars), [lang]);

  const setLanguage = useCallback((next: Lang) => {
    setLang(next);
    localStorage.setItem(LANG_KEY, next);
    // Persist only when authenticated — on the auth page there's no token and
    // a PATCH would 401 → reload.
    if (getToken()) {
      // A failed save is silent: the UI and the local cache already have the
      // new language; only other devices miss it until the next switch.
      api.PATCH("/auth/me", { body: { language: next } }).catch(() => undefined);
    }
  }, [api]);

  const syncLanguage = useCallback((next: Lang) => {
    setLang(next);
    localStorage.setItem(LANG_KEY, next);
  }, []);

  const value = useMemo(
    () => ({ lang, t, setLanguage, syncLanguage }),
    [lang, t, setLanguage, syncLanguage]
  );

  return (
    <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within a LanguageProvider");
  return ctx;
}

/** Convenience hook when a component only needs the `t` function. */
export function useT(): TFunc {
  return useLanguage().t;
}
