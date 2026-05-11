import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { createSession, listSessions } from "../../lib/api";

export default function SessionListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions
  });
  const create = useMutation({
    mutationFn: createSession,
    onSuccess: async (row) => {
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
      navigate(`/sessions/${row.session_id}`);
    }
  });

  return (
    <section className="mx-auto max-w-5xl px-6 py-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-950">{t("sessions.title")}</h1>
          <p className="mt-1 text-sm text-slate-600">{t("sessions.subtitle")}</p>
        </div>
        <button
          className="rounded-md bg-slate-950 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-400"
          disabled={create.isPending}
          type="button"
          onClick={() => create.mutate()}
        >
          {create.isPending ? t("sessions.creating") : t("sessions.create")}
        </button>
      </div>
      <div className="mt-6 overflow-hidden rounded-lg border border-slate-200 bg-white">
        {sessions.isPending ? (
          <p className="p-4 text-sm text-slate-500">{t("sessions.loading")}</p>
        ) : sessions.isError ? (
          <p className="p-4 text-sm text-rose-600">{t("sessions.error")}</p>
        ) : sessions.data.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">{t("sessions.empty")}</p>
        ) : (
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">{t("sessions.id")}</th>
                <th className="px-4 py-3">{t("sessions.state")}</th>
                <th className="px-4 py-3">{t("sessions.ir")}</th>
                <th className="px-4 py-3">{t("sessions.updated")}</th>
              </tr>
            </thead>
            <tbody>
              {sessions.data.map((session) => (
                <tr className="border-t border-slate-200" key={session.session_id}>
                  <td className="px-4 py-3 font-mono text-xs">
                    <Link className="text-slate-950 underline" to={`/sessions/${session.session_id}`}>
                      {session.session_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{session.state}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {session.latest_ir_sha256?.slice(0, 12) || t("sessions.noIr")}
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {new Date(session.updated_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
