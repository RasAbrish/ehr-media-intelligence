import { CopyIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface CopyButtonProps {
  value: string;
  label: string;
  confirmation: string;
  className?: string;
}

/** Icon button that copies a value and confirms with a toast. */
export function CopyButton({ value, label, confirmation, className }: CopyButtonProps) {
  const onCopy = async (event: React.MouseEvent) => {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(value);
      toast(confirmation);
    } catch {
      // Clipboard blocked (insecure context): nothing to confirm.
    }
  };
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label={label}
      className={cn("text-muted-foreground max-md:size-11", className)}
      onClick={(event) => void onCopy(event)}
    >
      <CopyIcon aria-hidden />
    </Button>
  );
}
