import { KeyboardIcon, XIcon } from "lucide-react";
import { Fragment, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Kbd } from "@/components/ui/kbd";
import { copy } from "@/lib/copy";
import { isTypingTarget } from "@/lib/keyboard";
import { modalOpen } from "@/lib/modal";

/** Top bar button and "?" dialog listing the keyboard model (docs/06 sections 6.1 and 8.4). */
export function ShortcutsDialog() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "?" || isTypingTarget(event.target) || modalOpen("dialog")) return;
      event.preventDefault();
      setOpen(true);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, []);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="hidden size-9 md:inline-flex"
            aria-label={copy.shortcuts.open}
          />
        }
      >
        <KeyboardIcon aria-hidden strokeWidth={1.75} />
      </DialogTrigger>
      <DialogContent
        showCloseButton={false}
        className="max-h-[calc(100dvh-2rem)] overflow-y-auto shadow-overlay sm:max-w-md"
      >
        <div className="flex items-start gap-2">
          <DialogHeader className="flex-1 gap-1">
            <DialogTitle className="text-heading">{copy.shortcuts.title}</DialogTitle>
            <DialogDescription>{copy.shortcuts.body}</DialogDescription>
          </DialogHeader>
          <DialogClose
            render={
              <Button
                variant="ghost"
                size="icon"
                className="max-md:size-11"
                aria-label={copy.shortcuts.close}
              />
            }
          >
            <XIcon aria-hidden />
          </DialogClose>
        </div>
        <dl className="divide-y text-small">
          {copy.shortcuts.rows.map((row) => (
            <div key={row.action} className="flex items-center justify-between gap-4 py-2">
              <dt>
                {row.action}
                <span className="block text-meta text-muted-foreground">{row.context}</span>
              </dt>
              <dd className="flex shrink-0 items-center gap-1">
                {row.keys.map((key, index) => (
                  <Fragment key={key}>
                    {index ? (
                      <span className="text-meta text-muted-foreground">{copy.shortcuts.or}</span>
                    ) : null}
                    <Kbd className="text-foreground">{key}</Kbd>
                  </Fragment>
                ))}
              </dd>
            </div>
          ))}
        </dl>
      </DialogContent>
    </Dialog>
  );
}
