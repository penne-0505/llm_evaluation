// Agent lifecycle hook guard for docs-driven projects.
// It nudges agents to run the documented workflow and blocks high-risk deletion
// paths, but it never updates docs or archives files by itself.

const HOOK_EVENT_NAMES = new Set([
  "SessionStart",
  "Stop",
  "PreToolUse",
  "UserPromptSubmit",
]);

type HookEventName =
  | "SessionStart"
  | "Stop"
  | "PreToolUse"
  | "UserPromptSubmit";

type ToolInput = {
  file_path?: unknown;
  path?: unknown;
  target_file?: unknown;
  command?: unknown;
  cmd?: unknown;
  [key: string]: unknown;
};

type HookInput = {
  hook_event_name?: unknown;
  hookEventName?: unknown;
  tool_name?: unknown;
  toolName?: unknown;
  tool_input?: ToolInput;
  toolInput?: ToolInput;
  stop_hook_active?: unknown;
  last_assistant_message?: unknown;
  lastAssistantMessage?: unknown;
  [key: string]: unknown;
};

export type HookDecision =
  | { decision: "block"; reason: string }
  | { decision: "context"; context: string };

const SESSION_CONTEXT = [
  "Docs-driven workflow reminder:",
  "- Read AGENTS.md, TODO.md, _docs/documentation_guide.md, and relevant _docs/standards before implementation.",
  "- Skills are not automatic. Use implementation-prep before multi-file or document-aligned work.",
  "- Use docs-inventory for current-state triage, handoff discovery, stale-doc audits, or concerns that docs have become ceremonial.",
  "- For Size >= M or Risk >= Medium tasks, use docs-prep and qa-prep before implementation, and qa-review before completion.",
  "- Use docs-cleanup when draft/plan/survey/archive boundaries or substantial documentation cleanup are involved.",
  "- Hooks are guardrails only: do not let them replace judgement, QA evidence, or explicit verification notes.",
].join("\n");

const USER_PROMPT_CONTEXT =
  "Before acting, re-check the current hypothesis against known evidence and plausible counterevidence, then stay within the agreed Goal, Scope, Non-Goals, and Intent.";

const WRITE_AUDIT_CONTEXT = [
  "Before modifying files, audit the proposed change:",
  "- Identify the evidence for the root cause and one plausible disconfirming explanation.",
  "- Check non-local effects on callers, data flow, tests, docs, operations, and future maintenance.",
  "- Compare the local patch with the durable solution, and preserve compatibility only when its support horizon and rationale are explicit.",
  "- Stay within the agreed Goal, Scope, Non-Goals, and user authority; propose broader work instead of silently expanding scope.",
  "Record externally verifiable decisions, tests, and residual risks rather than private chain-of-thought.",
].join("\n");

const CLOSURE_TERMS_RE =
  /check-docs|validate-|docs-inventory|qa-review|docs-cleanup|post-implementation|verification|verdict|residual risk|未検証|検証|残リスク|実行できなかった|deferred/i;

const AUDIT_EVIDENCE_PATTERNS = [
  /仮説|反証|反例|別解|counterevidence|counterexample|alternative explanation|assumption/i,
  /影響範囲|非局所|全体|呼び出し元|データフロー|運用影響|non-local|system impact|caller|data flow|downstream|upstream/i,
  /根本原因|恒久|長期|保守性|互換性|support horizon|root cause|durable|long-term|maintainability|compatibility/i,
  /残リスク|トレードオフ|見送り|deferred|residual risk|trade-off|follow-up/i,
];

const COMPLETION_TERMS_RE =
  /完了|対応しました|実装しました|更新しました|修正しました|追加しました|done|completed|implemented|fixed|updated|added|finished|pass/i;

const QUESTION_AT_END_RE = /[?？]\s*$/;

const normalizePath = (path: unknown): string => {
  const segments: string[] = [];
  for (const segment of String(path ?? "").replaceAll("\\", "/").split("/")) {
    if (segment === "" || segment === ".") continue;
    if (segment === "..") segments.pop();
    else segments.push(segment);
  }
  return segments.join("/");
};

const unique = (
  items: string[],
): string[] => [...new Set(items.filter(Boolean))];

export const parsePorcelainPaths = (statusOutput: unknown): string[] => {
  const paths: string[] = [];
  for (const rawLine of String(statusOutput ?? "").split(/\r?\n/)) {
    const line = rawLine.trimEnd();
    if (line === "") continue;
    const body = line.slice(3).trim();
    if (body.includes(" -> ")) {
      const [from, to] = body.split(" -> ").map((value) =>
        value.replace(/^"|"$/g, "")
      );
      paths.push(normalizePath(from), normalizePath(to));
    } else {
      paths.push(normalizePath(body.replace(/^"|"$/g, "")));
    }
  }
  return unique(paths);
};

const pathFromToolInput = (toolInput: ToolInput | null | undefined): string => {
  if (!toolInput || typeof toolInput !== "object") return "";
  return normalizePath(
    toolInput.file_path ?? toolInput.path ?? toolInput.target_file ?? "",
  );
};

const commandFromToolInput = (
  toolInput: ToolInput | null | undefined,
): string => {
  if (!toolInput || typeof toolInput !== "object") return "";
  return String(toolInput.command ?? toolInput.cmd ?? "");
};

const includesSensitivePath = (value: unknown): boolean =>
  /(^|[\/\s'"`])(\.env(\.|$|[\/\s'"`])|id_rsa\b|id_ed25519\b|\.pem\b|\.key\b)/i
    .test(String(value ?? ""));

const protectedArchiveMove = (command: string): boolean =>
  /\b(git\s+)?mv\b[\s\S]*_docs\/(intent|qa|guide|reference)\b[\s\S]*_docs\/archives\b/i
    .test(command) ||
  /\b(git\s+)?mv\b[\s\S]*_docs\/archives\/(intent|qa|guide|reference)\b/i
    .test(command);

const destructiveCommandReason = (command: unknown): string | null => {
  const text = String(command ?? "");
  const checks: Array<{ re: RegExp; reason: string }> = [
    {
      re: /(^|[;&|()\s])git\s+rm(\s|$)/,
      reason:
        "git rm is blocked by this template. Propose permanent deletion to the user, or use archive movement only after the checklist passes.",
    },
    {
      re: /(^|[;&|()\s])rm\s+(-[^\s]+\s+)?/,
      reason:
        "rm is blocked by this template. Propose permanent deletion to the user, or use archive movement only after the checklist passes.",
    },
    {
      re: /(^|[;&|()\s])git\s+reset\s+--hard(\s|$)/,
      reason:
        "git reset --hard is blocked because it can discard user or agent work.",
    },
    {
      re: /(^|[;&|()\s])git\s+clean(\s|$)/,
      reason: "git clean is blocked because it can permanently remove files.",
    },
    {
      re: /(^|[;&|()\s])git\s+checkout\s+--(\s|$)/,
      reason:
        "git checkout -- is blocked because it can discard local changes.",
    },
  ];
  for (const check of checks) {
    if (check.re.test(text)) return check.reason;
  }
  if (protectedArchiveMove(text)) {
    return "Do not move intent, QA, guide, or reference docs into archives. Only draft, plan, and survey docs can be archived after the checklist passes.";
  }
  if (
    includesSensitivePath(text) &&
    /\b(cat|less|more|sed|awk|rg|grep|python|node|deno|cp|mv)\b/.test(text)
  ) {
    return "This command appears to touch sensitive credential-like files. Avoid reading or copying .env, key, or token material.";
  }
  return null;
};

const patchDeletionReason = (command: string): string | null => {
  if (!/\*\*\* Delete File:/.test(command)) return null;
  return "File deletion through apply_patch is blocked by this template. Propose permanent deletion to the user, or use archive movement only after the checklist passes.";
};

export const analyzePreToolUse = (
  input: HookInput | null | undefined,
): HookDecision | null => {
  const toolName = String(input?.tool_name ?? input?.toolName ?? "");
  const toolInput = input?.tool_input ?? input?.toolInput ?? {};
  const command = commandFromToolInput(toolInput);
  const filePath = pathFromToolInput(toolInput);

  if (/bash|shell/i.test(toolName)) {
    const reason = destructiveCommandReason(command);
    if (reason) return { decision: "block", reason };
  }

  if (/apply_patch|edit|write|multiedit/i.test(toolName)) {
    const reason = patchDeletionReason(command);
    if (reason) return { decision: "block", reason };
    if (includesSensitivePath(filePath)) {
      return {
        decision: "block",
        reason:
          "Edits to sensitive credential-like files are blocked. Use .env.example or a documented non-secret placeholder instead.",
      };
    }
    return { decision: "context", context: WRITE_AUDIT_CONTEXT };
  }

  return null;
};

export const analyzeUserPromptSubmit = (): Extract<
  HookDecision,
  { decision: "context" }
> => ({
  decision: "context",
  context: USER_PROMPT_CONTEXT,
});

type StopPathGroups = {
  all: string[];
  todo: string[];
  docs: string[];
  workflow: string[];
  archive: string[];
  temporaryDocs: string[];
  qaDocs: string[];
};

const relevantStopPaths = (paths: string[]): StopPathGroups => {
  const normalized = unique(paths.map(normalizePath));
  return {
    all: normalized,
    todo: normalized.filter((path) => path === "TODO.md"),
    docs: normalized.filter((path) =>
      path.startsWith("_docs/") || [
        "README.md",
        "QUICKSTART.md",
        "AGENTS.md",
        "CLAUDE.md",
      ].includes(path)
    ),
    workflow: normalized.filter((path) =>
      path === "AGENTS.md" ||
      path === "CLAUDE.md" ||
      path.startsWith(".codex/") ||
      path === ".claude/settings.json" ||
      path.startsWith(".agents/skills/") ||
      path.startsWith(".claude/skills/") ||
      path.startsWith(".github/workflows/") ||
      path.startsWith("_docs/standards/") ||
      path.startsWith("scripts/validate-") ||
      path === "scripts/check-docs.sh" ||
      path === "scripts/scope.ts" ||
      path === "scripts/agent-workflow-hook.ts" ||
      path === "scripts/test-agent-workflow-smoke.ts"
    ),
    archive: normalized.filter((path) => path.startsWith("_docs/archives/")),
    temporaryDocs: normalized.filter((path) =>
      /^_docs\/(draft|plan|survey)\//.test(path)
    ),
    qaDocs: normalized.filter((path) => path.startsWith("_docs/qa/")),
  };
};

const looksLikeCompletion = (message: unknown): boolean => {
  const text = String(message ?? "").trim();
  if (text === "") return true;
  if (QUESTION_AT_END_RE.test(text) && !COMPLETION_TERMS_RE.test(text)) {
    return false;
  }
  return COMPLETION_TERMS_RE.test(text);
};

const hasClosureEvidence = (message: unknown): boolean =>
  CLOSURE_TERMS_RE.test(String(message ?? ""));

export const auditEvidenceCount = (message: unknown): number =>
  AUDIT_EVIDENCE_PATTERNS.filter((pattern) =>
    pattern.test(String(message ?? ""))
  )
    .length;

const listSome = (label: string, paths: string[]): string | null => {
  if (paths.length === 0) return null;
  const shown = paths.slice(0, 5).map((path) => `  - ${path}`).join("\n");
  const suffix = paths.length > 5
    ? `\n  - ...and ${paths.length - 5} more`
    : "";
  return `${label}:\n${shown}${suffix}`;
};

export const analyzeStop = (
  { input = {}, dirtyPaths = [] }: {
    input?: HookInput;
    dirtyPaths?: string[];
  },
): HookDecision | null => {
  if (input.stop_hook_active === true) return null;

  const grouped = relevantStopPaths(dirtyPaths);
  const hasRelevantChange = grouped.todo.length > 0 ||
    grouped.docs.length > 0 ||
    grouped.workflow.length > 0;
  if (!hasRelevantChange) return null;

  const lastMessage = String(
    input.last_assistant_message ?? input.lastAssistantMessage ?? "",
  );
  if (!looksLikeCompletion(lastMessage)) return null;
  const hasVerificationEvidence = hasClosureEvidence(lastMessage);
  const hasIndependentAuditEvidence = auditEvidenceCount(lastMessage) >= 2;
  if (hasVerificationEvidence && hasIndependentAuditEvidence) return null;

  const sections = [
    listSome("Changed workflow-sensitive files", grouped.workflow),
    listSome("Changed documentation files", grouped.docs),
    listSome("Changed TODO files", grouped.todo),
  ].filter(Boolean).join("\n\n");

  const actions = [
    "Before finishing, handle the docs-driven closure explicitly:",
    "- If TODO.md or _docs changed, run ./scripts/check-docs.sh or state why it cannot run.",
    "- If the request is current-state triage, handoff discovery, or documentation health review, use docs-inventory before cleanup.",
    "- If the task is Size >= M or Risk >= Medium, use qa-review and record verification before completion.",
    "- If draft/plan/survey cleanup or archives are involved, use docs-cleanup. Do not archive intent or QA docs.",
    "- Re-audit the result from at least two explicit perspectives: counterevidence or alternatives, non-local system effects, long-term maintainability or compatibility, and residual risks or trade-offs.",
    "- Keep the audit within the agreed Goal / Scope / Non-Goals. Propose broader work instead of silently expanding scope.",
    "- Mention commands actually run and remaining gaps in the final response.",
  ].join("\n");

  return {
    decision: "block",
    reason: `${sections}\n\n${actions}`,
  };
};

const readStdin = async (): Promise<string> => {
  const chunks: Uint8Array[] = [];
  const buffer = new Uint8Array(8192);
  while (true) {
    const n = await Deno.stdin.read(buffer);
    if (n === null) break;
    chunks.push(buffer.slice(0, n));
  }
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const merged = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return new TextDecoder().decode(merged);
};

const parseHookInput = (raw: string): HookInput => {
  if (!raw.trim()) return {};
  try {
    return JSON.parse(raw) as HookInput;
  } catch {
    return {};
  }
};

const runGitStatus = async (): Promise<string[]> => {
  let env: Record<string, string>;
  try {
    env = { ...Deno.env.toObject() };
  } catch (err) {
    throw new Error(
      `Stop hook requires --allow-env to sanitize git subprocess env (need --allow-read --allow-env --allow-run=git): ${
        err instanceof Error ? err.message : String(err)
      }`,
    );
  }
  delete env.LD_LIBRARY_PATH;
  delete env.LD_PRELOAD;
  let output: Deno.CommandOutput;
  try {
    output = await new Deno.Command("git", {
      args: ["status", "--short"],
      stdout: "piped",
      stderr: "piped",
      clearEnv: true,
      env,
    }).output();
  } catch (err) {
    throw new Error(
      `Stop hook could not run git status (need --allow-run=git): ${
        err instanceof Error ? err.message : String(err)
      }`,
    );
  }
  if (!output.success) return [];
  return parsePorcelainPaths(new TextDecoder().decode(output.stdout));
};

const jsonOut = (value: unknown): void => {
  console.log(JSON.stringify(value));
};

const blockOut = (eventName: string, reason: string): void => {
  if (eventName === "PreToolUse") {
    jsonOut({
      decision: "block",
      reason,
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: reason,
      },
    });
    return;
  }
  jsonOut({ decision: "block", reason });
};

const contextOut = (eventName: string, context: string): void => {
  jsonOut({
    hookSpecificOutput: {
      hookEventName: eventName,
      additionalContext: context,
    },
  });
};

const sessionStartOut = (): void => {
  jsonOut({
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: SESSION_CONTEXT,
    },
  });
};

const inferEventName = (arg: string | undefined, input: HookInput): string => {
  const fromInput = input.hook_event_name ?? input.hookEventName;
  if (typeof fromInput === "string" && HOOK_EVENT_NAMES.has(fromInput)) {
    return fromInput as HookEventName;
  }
  if (arg === "session-start") return "SessionStart";
  if (arg === "stop") return "Stop";
  if (arg === "pre-tool-use") return "PreToolUse";
  if (arg === "user-prompt-submit") return "UserPromptSubmit";
  return String(fromInput ?? arg ?? "");
};

const main = async (): Promise<void> => {
  const raw = await readStdin();
  const input = parseHookInput(raw);
  const eventName = inferEventName(Deno.args[0], input);

  if (eventName === "SessionStart") {
    sessionStartOut();
    return;
  }

  if (eventName === "PreToolUse") {
    const result = analyzePreToolUse(input);
    if (result?.decision === "block") blockOut("PreToolUse", result.reason);
    else if (result?.decision === "context") {
      contextOut("PreToolUse", result.context);
    }
    return;
  }

  if (eventName === "UserPromptSubmit") {
    const result = analyzeUserPromptSubmit();
    contextOut("UserPromptSubmit", result.context);
    return;
  }

  if (eventName === "Stop") {
    const dirtyPaths = await runGitStatus();
    const result = analyzeStop({ input, dirtyPaths });
    if (result?.decision === "block") blockOut("Stop", result.reason);
  }
};

if (import.meta.main) {
  main().catch((err: unknown) => {
    console.error(
      `agent-workflow-hook failed: ${
        err instanceof Error ? err.message : String(err)
      }`,
    );
    Deno.exit(1);
  });
}
