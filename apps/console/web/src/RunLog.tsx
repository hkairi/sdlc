import { useEffect, useState } from "react";

type RunLogProps = {
  runId: string;
};

type RunLogPayload = {
  text?: string;
  status?: string;
  exit_code?: number | null;
};

const TERMINAL = new Set(["done", "failed", "timeout", "cancelled"]);

export default function RunLog({ runId }: RunLogProps) {
  const [text, setText] = useState("");
  const [status, setStatus] = useState("connexion…");

  useEffect(() => {
    setText("");
    setStatus("connexion…");
    if (typeof EventSource === "undefined") {
      setStatus("SSE indisponible");
      return;
    }
    const source = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events`);
    const onLog = (event: Event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as RunLogPayload;
        if (typeof payload.text === "string") {
          setText((current) => current + payload.text);
        }
      } catch {
        setStatus("journal illisible");
      }
    };
    const onStatus = (event: Event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as RunLogPayload;
        if (typeof payload.status === "string") {
          setStatus(payload.status);
          if (TERMINAL.has(payload.status)) {
            source.close();
          }
        }
      } catch {
        setStatus("état illisible");
      }
    };
    const onError = () => setStatus("connexion interrompue");
    source.addEventListener("run.log", onLog);
    source.addEventListener("run.status", onStatus);
    source.addEventListener("error", onError);
    return () => {
      source.removeEventListener("run.log", onLog);
      source.removeEventListener("run.status", onStatus);
      source.removeEventListener("error", onError);
      source.close();
    };
  }, [runId]);

  return (
    <section className="card" aria-labelledby="run-log-title">
      <div className="card-head">
        <h2 id="run-log-title">Journal du run</h2>
        <p className="muted" role="status" aria-live="polite">
          {status}
        </p>
      </div>
      <pre
        className="run-log"
        aria-live="polite"
        aria-atomic="false"
        aria-label="Journal du run en texte brut"
        tabIndex={0}
      >
        {text || "En attente du journal…"}
      </pre>
    </section>
  );
}
