import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { copy } from "@/lib/copy";
import { keys } from "@/lib/query-keys";
import { healthQuery } from "@/lib/system-api";

/** An awake API answers well within this. Longer means the host is holding the request. */
const SLOW_MS = 2000;

/**
 * Public demo notice (docs/DEPLOY.md). A free host sleeps when idle, so this also says when
 * the API is waking and reloads what failed in the meantime once it answers.
 */
export function DemoBanner({ pollMs = 5000 }: { pollMs?: number }) {
  const client = useQueryClient();
  const health = useQuery({
    ...healthQuery(),
    refetchInterval: (query) => (query.state.status === "success" ? false : pollMs),
  });
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSlow(true);
    }, SLOW_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, []);
  const waking = !health.isSuccess && (health.isError || slow);
  const slept = useRef(false);
  useEffect(() => {
    if (waking) slept.current = true;
    if (health.isSuccess && slept.current) {
      slept.current = false;
      void client.invalidateQueries({ predicate: (query) => query.queryKey[0] !== keys.health[0] });
    }
  }, [client, waking, health.isSuccess]);
  return (
    <div
      role="region"
      aria-label={copy.demo.label}
      className="border-b border-warning/40 bg-warning/15 px-3 py-1.5 text-center text-meta text-warning-foreground dark:text-warning"
    >
      <p>{copy.demo.notice}</p>
      <p role="status">{waking ? <span>{copy.demo.waking}</span> : null}</p>
    </div>
  );
}
