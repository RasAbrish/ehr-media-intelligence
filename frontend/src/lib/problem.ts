/** RFC 9457 problem details (docs/04 sections 2.3 and 2.4) and the client's error types. */
import { z } from "zod";

export const FieldErrorSchema = z.strictObject({
  loc: z.string(),
  message: z.string(),
  type: z.string(),
});

export const ProblemSchema = z.strictObject({
  type: z.string(),
  title: z.string(),
  status: z.number().int(),
  detail: z.string(),
  instance: z.string(),
  code: z.string(),
  request_id: z.string(),
  errors: z.array(FieldErrorSchema),
});

export type Problem = z.infer<typeof ProblemSchema>;

/** An HTTP error from the API, with the parsed problem when the body was problem+json. */
export class ApiError extends Error {
  readonly status: number;
  readonly problem: Problem | null;
  readonly retryAfterSeconds: number | null;

  constructor(status: number, problem: Problem | null, retryAfterSeconds: number | null = null) {
    super(problem?.detail ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
    this.retryAfterSeconds = retryAfterSeconds;
  }

  get code(): string | null {
    return this.problem?.code ?? null;
  }

  get requestId(): string | null {
    return this.problem?.request_id ?? null;
  }
}

/** The server could not be reached (offline, refused, CORS). */
export class NetworkError extends Error {
  constructor(cause: unknown) {
    super("Network request failed", { cause });
    this.name = "NetworkError";
  }
}

/** The server answered with a body that does not match the contract. */
export class ContractError extends Error {
  constructor(path: string, cause: unknown) {
    super(`Response from ${path} does not match the API contract`, { cause });
    this.name = "ContractError";
  }
}
