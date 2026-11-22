import { readStored, writeStored } from "@/lib/storage";

const KEY = "mi-client-id";
let memoryId: string | null = null;

/** randomUUID needs a secure context; plain HTTP on a LAN address has getRandomValues only. */
function randomId(): string {
  if ("randomUUID" in crypto) return crypto.randomUUID();
  const hex = Array.from((crypto as Crypto).getRandomValues(new Uint8Array(16)), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20),
  ].join("-");
}

/** Anonymous random id for one vote per browser (docs/04 section 1.1). The server stores a hash. */
export function clientId(): string {
  const stored = readStored(KEY);
  if (stored) return stored;
  memoryId ??= randomId();
  writeStored(KEY, memoryId);
  return memoryId;
}
