import type { Plugin } from "@opencode-ai/plugin"

const GATE =
  /(pytest|ruff|black|mypy|pyright|coverage|npm (run )?(test|lint|typecheck)|pnpm|yarn|make (test|check|lint))/i

const FAIL =
  /(\b\d+\s+failed\b)|(\berror\b)|(ERR!)|(Traceback \(most recent call last\))|(exit code [1-9])/i

const PASS =
  /(\b\d+\s+passed\b)|(All checks passed)|(no issues found)|(reformatted)|(Successfully)/i

const REMINDER =
  "\n\n> [auto-melhoria] Este comando falhou antes nesta sessão e agora passou. " +
  "Se a correção revelou um erro seu, registre a lição ANTES de encerrar em " +
  "`.opencode/LESSONS.md` no formato Gatilho/Erro/Regra/Evidência. " +
  "Só registre erro real e já corrigido; não invente."

export default (async () => {
  const failedBySession = new Map<string, Set<string>>()

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
        const isFail =
          (hasCode && code !== 0) || (!PASS.test(text) && FAIL.test(text))
        const isPass = hasCode ? code === 0 : PASS.test(text) && !FAIL.test(text)

        const key = cmd.trim()
        if (isFail) {
          const set = failedBySession.get(input.sessionID) ?? new Set<string>()
          set.add(key)
          failedBySession.set(input.sessionID, set)
          return
        }
        if (!isPass) return

        const set = failedBySession.get(input.sessionID)
        if (!set?.has(key)) return
        set.delete(key)
        output.output = `${text}${REMINDER}`
      } catch {
        // Nunca quebrar a ferramenta por causa do lembrete.
      }
    },
  }
}) satisfies Plugin
