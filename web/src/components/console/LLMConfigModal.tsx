import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import type { LLMConfigInput } from "../../lib/types";

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
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/35 px-4">
      <form
        className="w-full max-w-lg rounded-lg border border-slate-200 bg-white p-6 shadow-xl"
        onSubmit={submit}
      >
        <h2 className="text-lg font-semibold text-slate-950">{t("llmConfig.title")}</h2>
        <p className="mt-2 text-sm text-slate-600">{t("llmConfig.description")}</p>
        <label className="mt-5 block text-sm font-medium text-slate-700">
          {t("llmConfig.apiKey")}
          <input
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            required
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
          />
        </label>
        <label className="mt-4 block text-sm font-medium text-slate-700">
          {t("llmConfig.baseUrl")}
          <input
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            required
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
          />
        </label>
        <label className="mt-4 block text-sm font-medium text-slate-700">
          {t("llmConfig.model")}
          <input
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            required
            value={model}
            onChange={(event) => setModel(event.target.value)}
          />
        </label>
        <button
          className="mt-6 w-full rounded-md bg-slate-950 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-400"
          disabled={isSaving}
          type="submit"
        >
          {isSaving ? t("llmConfig.saving") : t("llmConfig.save")}
        </button>
      </form>
    </div>
  );
}
