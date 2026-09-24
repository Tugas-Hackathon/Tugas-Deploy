import { useState, useEffect } from "react"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { faWandMagicSparkles, faCircleCheck, faTriangleExclamation } from "@fortawesome/free-solid-svg-icons"
import { api } from "../lib/api"
import { Pill } from "../App"

export function SettingsPage() {
  const [state, setState] = useState<any>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    api.settings().then(setState).catch(e => setError(e.message))
  }, [])

  const ready = state?.ai_ready

  return (
    <div className="max-w-2xl mx-auto px-8 py-10">
      <h2 className="text-xl font-semibold mb-1" style={{ color: "var(--text)" }}>Settings</h2>
      <p className="text-sm mb-8" style={{ color: "var(--text-dim)" }}>
        How this workspace is configured.
      </p>

      <div className="rounded-2xl p-6"
        style={{ background: "var(--surface)", border: "1px solid var(--surface-border)" }}>
        <div className="flex items-center gap-2 mb-3">
          <FontAwesomeIcon icon={faWandMagicSparkles} className="text-xs"
            style={{ color: "var(--accent-bright)" }} />
          <h3 className="text-sm font-semibold" style={{ color: "var(--text)" }}>AI engine</h3>
          {state && (
            <Pill tone={ready ? "teal" : "dim"}>
              {ready ? "ready" : "not configured"}
            </Pill>
          )}
        </div>

        {state ? (
          <>
            <div className="flex items-center gap-2.5 mb-4">
              <FontAwesomeIcon icon={ready ? faCircleCheck : faTriangleExclamation}
                style={{ color: ready ? "var(--teal)" : "var(--amber)" }} />
              <span className="text-sm" style={{ color: "var(--text)" }}>
                {state.provider}
              </span>
            </div>

            <p className="text-xs leading-relaxed" style={{ color: "var(--text-dim)" }}>
              {ready
                ? "The tutor, milestone planner, rubric check and quiz generator are all live. Nothing to set up — no key to paste, no account to create. Just use it."
                : "GEMINI_API_KEY is not set on the server, so AI features are unavailable. Everything else still works."}
            </p>
          </>
        ) : (
          <p className="text-xs" style={{ color: "var(--text-faint)" }}>Checking…</p>
        )}

        {error && <p className="text-xs mt-3" style={{ color: "var(--red)" }}>{error}</p>}
      </div>

      <div className="rounded-2xl p-6 mt-5"
        style={{ background: "var(--surface)", border: "1px solid var(--surface-border)" }}>
        <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text)" }}>Proof of learning</h3>
        <p className="text-xs leading-relaxed mb-4" style={{ color: "var(--text-dim)" }}>
          Milestones are hashed and anchored on BOT Chain from your own wallet. The draft itself
          never leaves this device — only its hash goes on-chain, so the work stays private while
          the timestamp stays public.
        </p>
        <div className="text-[10px] font-mono space-y-1" style={{ color: "var(--text-faint)" }}>
          <div>network · BOT Chain Testnet (968)</div>
          <div className="truncate">ledger · {import.meta.env.VITE_LEDGER_ADDRESS ?? "not configured"}</div>
        </div>
      </div>
    </div>
  )
}
