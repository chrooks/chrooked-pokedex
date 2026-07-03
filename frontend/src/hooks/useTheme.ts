import { useCallback, useEffect, useState } from "react";

export type Theme = "dark" | "light";

const STORAGE_KEY = "chrooked-pokedex:theme";

function readStoredTheme(): Theme {
  return localStorage.getItem(STORAGE_KEY) === "light" ? "light" : "dark";
}

/** Persisted light/dark toggle. Dark is the tool's default identity (see
    DESIGN.md's handheld-screen scene); light is an explicit opt-in, never
    inferred from the OS. index.html sets the same attribute inline before
    paint so reloading in light mode doesn't flash dark first. */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(readStoredTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
  }, []);

  return [theme, toggleTheme];
}
