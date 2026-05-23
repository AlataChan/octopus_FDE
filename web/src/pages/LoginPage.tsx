import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LockKeyhole } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Card, CardBody } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { login } from "../lib/api";

type LocationState = {
  from?: { pathname?: string };
};

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: () => login(username, password),
    onSuccess: async (user) => {
      queryClient.setQueryData(["auth", "me"], user);
      const state = location.state as LocationState | null;
      navigate(state?.from?.pathname || "/sessions", { replace: true });
    }
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <section className="mx-auto flex min-h-[calc(100vh-56px)] max-w-md items-center px-4 py-10">
      <Card className="w-full">
        <CardBody className="space-y-5">
          <div>
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-fg">
              <LockKeyhole aria-hidden className="h-5 w-5" />
            </div>
            <h1 className="mt-4 text-2xl font-semibold text-fg">{t("auth.title")}</h1>
            <p className="mt-2 text-sm leading-6 text-fg-muted">{t("auth.subtitle")}</p>
          </div>
          <form className="space-y-4" onSubmit={submit}>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium text-fg">{t("auth.username")}</span>
              <Input
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </label>
            <label className="block space-y-1.5">
              <span className="text-sm font-medium text-fg">{t("auth.password")}</span>
              <Input
                autoComplete="current-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {mutation.isError ? (
              <p className="text-sm text-destructive">{t("auth.error.invalid_credentials")}</p>
            ) : null}
            <Button
              className="w-full"
              loading={mutation.isPending}
              type="submit"
              variant="primary"
              disabled={!username || !password}
            >
              {t("auth.submit")}
            </Button>
          </form>
        </CardBody>
      </Card>
    </section>
  );
}
