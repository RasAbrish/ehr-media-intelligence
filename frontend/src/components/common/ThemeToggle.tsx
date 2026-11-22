import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react";

import { isThemePreference } from "@/app/theme";
import { useTheme } from "@/app/theme-context";
import { SIDEBAR_ITEM } from "@/components/common/nav-items";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", label: copy.theme.light, Icon: SunIcon },
  { value: "dark", label: copy.theme.dark, Icon: MoonIcon },
  { value: "system", label: copy.theme.system, Icon: MonitorIcon },
] as const;

export function ThemeToggle() {
  const { preference, resolved, setPreference } = useTheme();
  const TriggerIcon = resolved === "dark" ? MoonIcon : SunIcon;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className={cn("size-11 font-normal text-muted-foreground", SIDEBAR_ITEM)}
            aria-label={`${copy.theme.trigger} (${copy.theme[preference].toLowerCase()})`}
          />
        }
      >
        <TriggerIcon aria-hidden="true" strokeWidth={1.75} className="size-5" />
        <span className="max-md:sr-only">{copy.theme.label}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-36">
        <DropdownMenuGroup>
          <DropdownMenuLabel>{copy.theme.label}</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={preference}
            onValueChange={(value: unknown) => {
              if (isThemePreference(value)) setPreference(value);
            }}
          >
            {OPTIONS.map(({ value, label, Icon }) => (
              <DropdownMenuRadioItem key={value} value={value}>
                <Icon aria-hidden="true" strokeWidth={1.75} />
                {label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
