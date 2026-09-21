import type { Plugin } from "@opencode-ai/plugin"

const GATE =
  /(pytest|ruff|black|mypy|pyright|coverage|(npm|pnpm|yarn)\s+(run\s+)?(test|lint|typecheck)|make\s+(test|check|lint))/i

const FAIL =
  /(\b[1-9]\d*\s+failed\b)|(\b[1-9]\d*\s+errors?\b)|(ERR!)|(Traceback \(most recent call last\))|(exit code [1-9])/i

const PASS =
  /(\b[1-9]\d*\s+passed\b)|(All checks passed)|(no issues found)|(reformatted)|(Successfully)/i

const MAX_SESSIONS = 100
const MAX_FAILURES_PER_SESSION = 50

const REMINDER =
  "\n\n> [auto-melhoria] Este comando falhou antes nesta sessão e agora passou. " +
  "Se a correção revelou um erro seu, registre a lição ANTES de encerrar em " +
  "`.opencode/LESSONS.md` no formato Gatilho/Erro/Regra/Evidência. " +
  "Só registre erro real e já corrigido; não invente."

export default (async () => {
  const failedBySession = new Map<string, Set<string>>()

  const recordFailure = (sessionID: string, key: string) => {
    const set = failedBySession.get(sessionID) ?? new Set<string>()
    set.delete(key)
    set.add(key)
    while (set.size > MAX_FAILURES_PER_SESSION) {
      const oldest = set.values().next().value
      if (oldest === undefined) break
      set.delete(oldest)
    }
    failedBySession.delete(sessionID)
    failedBySession.set(sessionID, set)
    if (failedBySession.size > MAX_SESSIONS) {
      const oldest = failedBySession.keys().next().value
      if (oldest !== undefined) failedBySession.delete(oldest)
    }
  }

  return {
    "tool.execute.after": async (input, output) => {
      try {
        if (input.tool !== "bash") return
        const cmd =
          typeof input.args?.command === "string" ? input.args.command : ""
        if (!GATE.test(cmd)) return

        const text = output.output ?? ""
        const code = output.metadata?.exitCode ?? output.metadata?.exit
        const hasCode = typeof code === "number"
        const isFail = hasCode ? code !== 0 : FAIL.test(text)
        const isPass = hasCode ? code === 0 : PASS.test(text) && !FAIL.test(text)

        const key = cmd.trim()
        if (isFail) {
          recordFailure(input.sessionID, key)
          return
        }
        if (!isPass) return

        const set = failedBySession.get(input.sessionID)
        if (!set?.has(key)) return
        set.delete(key)
        if (set.size === 0) failedBySession.delete(input.sessionID)
        output.output = `${text}${REMINDER}`
      } catch {
        // Nunca quebrar a ferramenta por causa do lembrete.
      }
    },
  }
}) satisfies Plugin
