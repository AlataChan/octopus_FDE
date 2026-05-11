import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import type { LLMConfigInput } from "../../lib/types";
import { Button } from "../ui/Button";
import { CardBody, CardHeader } from "../ui/Card";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";

type Props = {
  isSaving: boolean;
  open: boolean;
  onSubmit: (input: LLMConfigInput) => void;
};

export function LLMConfigModal({ isSaving, open, onSubmit }: Props) {
  const { t } = useTranslation();
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.deepseek.com/v1");
  const [model, setModel] = useState("deepseek-v4-flash");

  if (!open) {
    return null;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit({ api_key: apiKey, base_url: baseUrl, model });
  }

  return (
    <Modal labelledBy="llm-config-title" open={open}>
      <form
        onSubmit={submit}
      >
        <CardHeader
          subtitle={t("llmConfig.description")}
          title={<span id="llm-config-title">{t("llmConfig.title")}</span>}
        />
        <CardBody>
          <div className="grid gap-4">
            <label className="block text-sm font-medium text-fg-muted">
              {t("llmConfig.apiKey")}
              <Input
                className="mt-1"
                required
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
              />
            </label>
            <label className="block text-sm font-medium text-fg-muted">
              {t("llmConfig.baseUrl")}
              <Input
                className="mt-1"
                required
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
              />
            </label>
            <label className="block text-sm font-medium text-fg-muted">
              {t("llmConfig.model")}
              <Input
                className="mt-1"
                required
                value={model}
                onChange={(event) => setModel(event.target.value)}
              />
            </label>
          </div>
          <Button className="mt-6 w-full" loading={isSaving} type="submit" variant="primary">
            {isSaving ? t("llmConfig.saving") : t("llmConfig.save")}
          </Button>
        </CardBody>
      </form>
    </Modal>
  );
}
