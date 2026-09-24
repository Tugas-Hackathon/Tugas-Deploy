import { useState } from "react"
import { useWriteContract, useChainId, useSwitchChain } from "wagmi"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { faArrowUpRightFromSquare, faWandMagicSparkles } from "@fortawesome/free-solid-svg-icons"
import { api } from "../lib/api"
import { NETWORK } from "../lib/networks"
import { Pill } from "../App"

/** Retry the backend /anchored call until the node has indexed the receipt.
 *  The backend does eth_getTransactionReceipt server-side (no CORS), so we
 *  just need to wait for the RPC to reflect the mined block. */
async function retryAnchored(
  milestoneId: number,
  txHash: string,
  maxRetries = 20,
  delayMs = 3000,
): Promise<unknown> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await api.anchored(milestoneId, txHash)
    } catch (e: any) {
      const pending = e.message?.includes("not found") || e.message?.includes("not confirmed")
      if (!pending || i === maxRetries - 1) throw e
      await new Promise(r => setTimeout(r, delayMs))
    }
  }
}

const ABI = [
  {
    name: "commit",
    type: "function",
    inputs: [
      { name: "workHash", type: "bytes32" },
      { name: "contextHash", type: "bytes32" },
      { name: "aiAssistLevel", type: "uint8" },
    ],
    outputs: [],
    stateMutability: "nonpayable",
  },
] as const

const CONTRACT = import.meta.env.VITE_LEDGER_ADDRESS as `0x${string}`

type Status = "idle" | "hashing" | "awaiting_wallet" | "pending" | "confirmed" | "rejected" | "failed"

interface PolishResult {
  polished: string
  changes: string[]
  added_nothing: boolean
}

export function MilestoneCard({
  milestone,
  onAnchored,
}: {
  milestone: any
  onAnchored?: (id: number, hash: string) => void
}) {
  const [status, setStatus] = useState<Status>(milestone.tx_hash ? "confirmed" : "idle")
  const [draft, setDraft] = useState(milestone.draft_text ?? "")
  const [brief, setBrief] = useState("")
  const [error, setError] = useState("")

  // Polish (writing assistant) state
  const [polishing, setPolishing] = useState(false)
  const [polishResult, setPolishResult] = useState<PolishResult | null>(null)
  const [polishError, setPolishError] = useState("")

  const { writeContractAsync } = useWriteContract()
  const currentChainId = useChainId()
  const { switchChainAsync } = useSwitchChain()

  async function commit() {
    if (!draft.trim()) return
    setError("")
    setStatus("hashing")
    try {
      const { workHash, contextHash, aiAssistLevel } = await api.hashMilestone(
        milestone.id, draft, brief, "", 60
      )

      // Ensure the wallet is on the contract's network (e.g. BOT Chain Testnet)
      if (currentChainId !== NETWORK.id && switchChainAsync) {
        setStatus("awaiting_wallet")
        try {
          await switchChainAsync({ chainId: NETWORK.id })
        } catch (switchErr: any) {
          throw new Error(`Please switch your wallet network to ${NETWORK.name} in MetaMask`)
        }
      }

      setStatus("awaiting_wallet")
      const hash = await writeContractAsync({
        address: CONTRACT,
        abi: ABI,
        functionName: "commit",
        args: [workHash as `0x${string}`, contextHash as `0x${string}`, aiAssistLevel],
        chainId: NETWORK.id,
      })
      setStatus("pending")
      // Retry backend call until the RPC has indexed the mined receipt
      await retryAnchored(milestone.id, hash)
      setStatus("confirmed")
      onAnchored?.(milestone.id, hash)
    } catch (e: any) {
      setError(e.message)
      setStatus(e.message?.includes("rejected") ? "rejected" : "failed")
    }
  }

  async function polish() {
    if (!draft.trim() || polishing) return
    setPolishError("")
    setPolishResult(null)
    setPolishing(true)
    try {
      const result = await api.polishMilestone(milestone.id, draft)
      setPolishResult(result)
    } catch (e: any) {
      setPolishError(e.message)
    } finally {
      setPolishing(false)
    }
  }

  function applyPolish() {
    if (!polishResult) return
    setDraft(polishResult.polished)
    setPolishResult(null)
  }

  const statusColor: Record<Status, string> = {
    idle: "var(--text-faint)",
    hashing: "var(--accent-bright)",
    awaiting_wallet: "var(--amber)",
    pending: "var(--amber)",
    confirmed: "var(--teal)",
    rejected: "var(--red)",
    failed: "var(--red)",
  }

  const statusLabel: Record<Status, string> = {
    idle: "",
    hashing: "Computing hash…",
    awaiting_wallet: "Confirm in wallet…",
    pending: "Confirming on-chain…",
    confirmed: "Anchored on BOT Chain",
    rejected: "Wallet rejected",
    failed: "Failed",
  }

  const locked = status === "hashing" || status === "awaiting_wallet" || status === "pending" || status === "confirmed"

  return (
    <div className="rounded-2xl p-5 backdrop-blur-sm"
      style={{
        background: "var(--surface)",
        border: `1px solid ${status === "confirmed" ? "var(--teal-border)" : "var(--surface-border)"}`,
      }}>
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-medium text-sm truncate" style={{ color: "var(--text)" }}>{milestone.title}</span>
          {status === "confirmed" && <Pill tone="teal">Synced</Pill>}
        </div>
        {milestone.tx_hash && (
          <a href={`${NETWORK.explorer}/tx/${milestone.tx_hash}`} target="_blank" rel="noreferrer"
            className="shrink-0 flex items-center gap-1.5 text-[11px] font-mono hover:underline"
            style={{ color: "var(--accent-bright)" }}>
            View tx
            <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="text-[8px]" />
          </a>
        )}
      </div>

      <textarea value={draft} onChange={e => setDraft(e.target.value)}
        rows={3} placeholder="Paste your draft here to anchor it on-chain…"
        disabled={locked}
        className="w-full rounded-xl px-4 py-3 text-sm resize-none mb-2.5 outline-none disabled:opacity-60"
        style={{ background: "var(--input-bg)", color: "var(--text)", border: "1px solid var(--input-border)" }} />

      {/* Polish result panel */}
      {polishResult && (
        <div className="rounded-xl px-4 py-3 mb-3 text-sm"
          style={{ background: "var(--input-bg)", border: "1px solid var(--accent-border)" }}>
          <p className="text-[11px] font-mono mb-2" style={{ color: "var(--accent-bright)" }}>
            Writing assistant suggestion
          </p>
          <p className="text-sm mb-2" style={{ color: "var(--text)", whiteSpace: "pre-wrap" }}>
            {polishResult.polished}
          </p>
          {polishResult.changes.length > 0 && (
            <ul className="text-[11px] mb-2 list-disc list-inside" style={{ color: "var(--text-faint)" }}>
              {polishResult.changes.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          )}
          {!polishResult.added_nothing && (
            <p className="text-[11px] mb-2" style={{ color: "var(--amber)" }}>
              ⚠ The model may have added content not in your original notes. Review carefully before using.
            </p>
          )}
          <div className="flex gap-2">
            <button onClick={applyPolish}
              className="px-3 py-1.5 rounded-lg text-[11px] font-medium text-white transition-all"
              style={{ background: "linear-gradient(135deg,#8b5cf6,#6d28d9)" }}>
              Use this
            </button>
            <button onClick={() => setPolishResult(null)}
              className="px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all"
              style={{ color: "var(--text-faint)", border: "1px solid var(--surface-border)" }}>
              Discard
            </button>
          </div>
        </div>
      )}

      {polishError && (
        <p className="text-[11px] mb-2" style={{ color: "var(--red)" }}>{polishError}</p>
      )}

      <input value={brief} onChange={e => setBrief(e.target.value)}
        placeholder="Assignment brief (optional)"
        disabled={locked}
        className="w-full rounded-xl px-4 py-2.5 text-sm mb-4 outline-none disabled:opacity-60"
        style={{ background: "var(--input-bg)", color: "var(--text)", border: "1px solid var(--input-border)" }} />

      <div className="flex items-center gap-3">
        <button onClick={commit} disabled={locked}
          className="px-4 py-2 rounded-xl text-xs font-medium text-white disabled:opacity-40 transition-all"
          style={{ background: "linear-gradient(135deg,#8b5cf6,#6d28d9)", boxShadow: "0 0 16px var(--accent-glow)" }}>
          {status === "confirmed" ? "Anchored" : "Commit to chain"}
        </button>

        {!locked && draft.trim() && (
          <button onClick={polish} disabled={polishing}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium disabled:opacity-40 transition-all"
            style={{ color: "var(--accent-bright)", border: "1px solid var(--accent-border)", background: "var(--accent-soft)" }}>
            <FontAwesomeIcon icon={faWandMagicSparkles} className="text-[10px]" />
            {polishing ? "Polishing…" : "Polish"}
          </button>
        )}

        {status !== "idle" && (
          <span className="flex items-center gap-1.5 text-[11px] font-mono" style={{ color: statusColor[status] }}>
            <span className="w-1.5 h-1.5 rounded-full"
              style={{ background: statusColor[status], boxShadow: `0 0 7px ${statusColor[status]}` }} />
            {statusLabel[status]}
          </span>
        )}
      </div>

      {error && <p className="text-[11px] mt-3" style={{ color: "var(--red)" }}>{error}</p>}

      <div className="flex items-center justify-between mt-4 pt-3.5 text-[9px] font-mono uppercase tracking-[0.14em]"
        style={{ borderTop: "1px solid var(--surface-border)", color: "var(--text-faint)" }}>
        <span>Keccak256 · {NETWORK.name}</span>
        <span>AI Assist: 60%</span>
      </div>
    </div>
  )
}
