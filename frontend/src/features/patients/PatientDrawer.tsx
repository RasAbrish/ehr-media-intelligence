import { ArrowLeftIcon } from "lucide-react";
import { lazy, Suspense, useState, type RefObject } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { DrawerSkeleton } from "@/features/patients/DrawerSkeleton";
import { loadDrawerBody } from "@/features/patients/drawer-chunk";
import { copy } from "@/lib/copy";

const DrawerBody = lazy(() => loadDrawerBody().then((m) => ({ default: m.DrawerBody })));

interface PatientDrawerProps {
  patientKey: string | null;
  onClose: () => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
}

/** Shown while the drawer's chunk loads. */
function LoadingBody() {
  return (
    <div>
      <div className="flex items-center gap-2 border-b px-5 pt-4 pb-3">
        <SheetClose
          render={
            <Button
              variant="ghost"
              size="icon"
              className="-ml-2 size-11 md:hidden"
              aria-label={copy.drawer.back}
            />
          }
        >
          <ArrowLeftIcon aria-hidden />
        </SheetClose>
        <SheetTitle className="text-title">{copy.drawer.loading}</SheetTitle>
      </div>
      <DrawerSkeleton />
    </div>
  );
}

/** Patient drawer driven by `?patient=` (docs/06 sections 6.7 and 7.2). */
export function PatientDrawer({ patientKey, onClose, returnFocusRef }: PatientDrawerProps) {
  const [shownKey, setShownKey] = useState(patientKey);
  if (patientKey !== null && patientKey !== shownKey) setShownKey(patientKey);
  return (
    <Sheet
      open={patientKey !== null}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <SheetContent
        side="right"
        showCloseButton={false}
        finalFocus={returnFocusRef}
        className="w-full gap-0 overflow-x-hidden overflow-y-auto p-0 shadow-overlay data-[side=right]:w-full data-[side=right]:sm:max-w-none md:data-[side=right]:w-120 lg:data-[side=right]:w-140 2xl:data-[side=right]:w-160"
      >
        {/* Keyed: switching patients starts on the Summary tab with no stale highlight.
            The last patient stays rendered while the sheet slides out. */}
        {shownKey ? (
          <Suspense fallback={<LoadingBody />}>
            <DrawerBody key={shownKey} patientKey={shownKey} />
          </Suspense>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
