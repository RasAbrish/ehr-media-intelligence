import { Toaster } from "sonner";

import { useTheme } from "@/app/theme-context";

/** sonner toasts, bottom right, following the app theme (docs/06 section 6.11). */
export function AppToaster() {
  const { resolved } = useTheme();
  return (
    <Toaster
      theme={resolved}
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast: "!border-border !bg-popover !text-popover-foreground !text-small !shadow-overlay",
        },
      }}
    />
  );
}
