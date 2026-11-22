import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { CircleAlertIcon, EyeIcon, EyeOffIcon } from "lucide-react";
import { useId, useState, type SyntheticEvent } from "react";

import { DemoBanner } from "@/components/common/DemoBanner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { safeNext, signIn } from "@/features/auth/api";
import { SignInPhoto } from "@/features/auth/SignInPhoto";
import { copy } from "@/lib/copy";
import { ApiError } from "@/lib/problem";
import { keys } from "@/lib/query-keys";

function demoLogin(): { email: string; password: string } | null {
  const email: unknown = import.meta.env.VITE_DEMO_EMAIL;
  const password: unknown = import.meta.env.VITE_DEMO_PASSWORD;
  return typeof email === "string" && email && typeof password === "string" && password
    ? { email, password }
    : null;
}

/** Sign-in (docs/06 section 6.1a): photo half, form half. */
export function SignInPage() {
  const { next } = useSearch({ from: "/signin" });
  const navigate = useNavigate();
  const client = useQueryClient();
  const ids = { email: useId(), password: useId(), error: useId() };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const demo = demoLogin();

  const login = useMutation({
    mutationFn: signIn,
    onSuccess: (user) => {
      client.setQueryData(keys.me, user);
      void navigate({ href: safeNext(next) });
    },
  });
  const failed = login.error instanceof ApiError && login.error.status === 401;

  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    login.mutate({ email: email.trim(), password });
  };

  return (
    <div className="grid min-h-dvh bg-background lg:grid-cols-2">
      <SignInPhoto />
      <main id="main" tabIndex={-1} className="flex flex-col outline-none">
        {import.meta.env.VITE_DEMO_MODE === "true" ? <DemoBanner /> : null}
        <div className="flex flex-1 items-center justify-center px-4 py-10 md:px-6">
          <div className="flex w-full max-w-sm flex-col gap-6">
            <div className="flex flex-col gap-1">
              <h1 className="text-display">{copy.auth.title}</h1>
              <p className="text-muted-foreground">{copy.auth.body}</p>
            </div>
            {login.isError ? (
              <Alert variant="destructive" id={ids.error} className="border-destructive/40">
                <CircleAlertIcon aria-hidden />
                <AlertDescription>
                  <p>{failed ? copy.auth.failed : copy.auth.error}</p>
                </AlertDescription>
              </Alert>
            ) : null}
            <form className="flex flex-col gap-4" onSubmit={submit} noValidate={false}>
              <div className="flex flex-col gap-1.5">
                <label htmlFor={ids.email} className="text-small font-medium">
                  {copy.auth.email}
                </label>
                <Input
                  id={ids.email}
                  type="email"
                  autoComplete="username"
                  required
                  maxLength={254}
                  value={email}
                  aria-invalid={failed || undefined}
                  aria-describedby={login.isError ? ids.error : undefined}
                  onChange={(event) => {
                    setEmail(event.target.value);
                  }}
                  className="h-11 bg-card"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor={ids.password} className="text-small font-medium">
                  {copy.auth.password}
                </label>
                <div className="relative">
                  <Input
                    id={ids.password}
                    type={visible ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    maxLength={256}
                    value={password}
                    aria-invalid={failed || undefined}
                    aria-describedby={login.isError ? ids.error : undefined}
                    onChange={(event) => {
                      setPassword(event.target.value);
                    }}
                    className="h-11 bg-card pr-12"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={copy.auth.show}
                    aria-pressed={visible}
                    title={visible ? copy.auth.hide : copy.auth.show}
                    onClick={() => {
                      setVisible((value) => !value);
                    }}
                    className="absolute top-0 right-0 size-11 text-muted-foreground"
                  >
                    {visible ? <EyeOffIcon aria-hidden /> : <EyeIcon aria-hidden />}
                  </Button>
                </div>
              </div>
              <Button type="submit" className="h-11 w-full" disabled={login.isPending}>
                {login.isPending ? copy.auth.pending : copy.auth.submit}
              </Button>
            </form>
            {demo ? (
              <section
                aria-label={copy.auth.demoTitle}
                className="flex flex-col gap-3 rounded-xl border bg-muted/50 p-4 text-small"
              >
                <div>
                  <h2 className="text-heading">{copy.auth.demoTitle}</h2>
                  <p className="text-muted-foreground">{copy.auth.demoBody}</p>
                </div>
                <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1">
                  <dt className="text-muted-foreground">{copy.auth.email}</dt>
                  <dd className="font-mono text-mono wrap-anywhere">{demo.email}</dd>
                  <dt className="text-muted-foreground">{copy.auth.password}</dt>
                  <dd className="font-mono text-mono wrap-anywhere">{demo.password}</dd>
                </dl>
                <Button
                  type="button"
                  variant="outline"
                  className="h-11"
                  onClick={() => {
                    setEmail(demo.email);
                    setPassword(demo.password);
                  }}
                >
                  {copy.auth.useDemo}
                </Button>
              </section>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}
