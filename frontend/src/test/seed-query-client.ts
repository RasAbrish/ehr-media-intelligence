import type { QueryClient } from "@tanstack/react-query";

import { keys } from "@/lib/query-keys";
import { fixtures } from "@/test/msw/fixtures";

/** Fill a cache with the docs/04 examples for the example patient (Storybook). */
export function seedQueryClient(client: QueryClient): void {
  const key = fixtures.patient.patient_key;
  client.setQueryData(keys.patients.detail(key), fixtures.patient);
  client.setQueryData(keys.patients.summary(key), fixtures.summary);
  client.setQueryData(keys.patients.resources(key), fixtures.resources);
}
