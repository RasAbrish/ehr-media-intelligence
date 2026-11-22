/** docs/04 section 3a. */
import { z } from "@/lib/zod";

export const CurrentUserSchema = z.strictObject({
  email: z.string(),
  display_name: z.string(),
});

export const LoginRequestSchema = z.strictObject({
  email: z.string().min(3).max(254),
  password: z.string().min(1).max(256),
});

export type CurrentUser = z.infer<typeof CurrentUserSchema>;
export type LoginRequest = z.infer<typeof LoginRequestSchema>;
