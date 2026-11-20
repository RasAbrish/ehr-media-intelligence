import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  applyTheme,
  readStoredPreference,
  resolveTheme,
  storePreference,
  systemPrefersDark,
  watchSystemTheme,
  type ThemePreference,
} from "@/app/theme";
import { ThemeContext } from "@/app/theme-context";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(readStoredPreference);
  const [prefersDark, setPrefersDark] = useState<boolean>(systemPrefersDark);

  useEffect(() => watchSystemTheme(setPrefersDark), []);

  const resolved = resolveTheme(preference, prefersDark);

  // Syncing an external system (the <html> class), not fetching data.
  useEffect(() => {
    applyTheme(resolved);
  }, [resolved]);

  const value = useMemo(
    () => ({
      preference,
      resolved,
      setPreference: (next: ThemePreference) => {
        storePreference(next);
        setPreferenceState(next);
      },
    }),
    [preference, resolved],
  );

  return <ThemeContext value={value}>{children}</ThemeContext>;
}
