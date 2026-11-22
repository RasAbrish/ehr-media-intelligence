import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";

import { signOut } from "@/features/auth/api";
import { keys } from "@/lib/query-keys";

/** Ends the session, forgets every cached response and returns to sign-in. */
export function useSignOut() {
  const client = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: signOut,
    onSettled: () => {
      client.clear();
      client.setQueryData(keys.me, null);
      void navigate({ to: "/signin" });
    },
  });
}
