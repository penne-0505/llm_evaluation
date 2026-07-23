import {
  analyzePreToolUse,
  analyzeStop,
  analyzeUserPromptSubmit,
  auditEvidenceCount,
  parsePorcelainPaths,
} from "./agent-workflow-hook.ts";

const assert = (condition: unknown, message: string): void => {
  if (!condition) {
    console.error(`FAIL ${message}`);
    Deno.exit(1);
  }
  console.log(`PASS ${message}`);
};

assert(
  parsePorcelainPaths(" M TODO.md\nR  old.md -> new.md\n?? scripts/x.mjs\n")
    .join(",") === "TODO.md,old.md,new.md,scripts/x.mjs",
  "parse git porcelain paths",
);

const userPromptResult = analyzeUserPromptSubmit();
assert(
  userPromptResult.decision === "context" &&
    userPromptResult.context.includes("plausible counterevidence") &&
    userPromptResult.context.includes("Scope") &&
    userPromptResult.context.length < 240,
  "AC-001 INV-001 keep per-prompt audit short and evidence-based",
);

const patchAudit = analyzePreToolUse({
  tool_name: "apply_patch",
  tool_input: { command: "*** Begin Patch\n*** Update File: README.md\n" },
});
const writeAudit = analyzePreToolUse({
  tool_name: "Write",
  tool_input: { file_path: "src/example.ts" },
});
assert(
  patchAudit?.decision === "context" &&
    patchAudit.context.includes("root cause") &&
    writeAudit?.decision === "context" &&
    writeAudit.context.includes("silently expanding scope"),
  "AC-002 INV-002 add durable write audit context",
);

assert(
  analyzePreToolUse({
    tool_name: "Read",
    tool_input: { file_path: "README.md" },
  }) === null,
  "INV-002 avoid write audit noise on read-only tools",
);

assert(
  analyzePreToolUse({
    tool_name: "Bash",
    tool_input: { command: "git rm _docs/qa/Core/x/test-plan.md" },
  })?.decision === "block",
  "block git rm",
);

assert(
  analyzePreToolUse({
    tool_name: "Bash",
    tool_input: { command: "rm -rf _docs/intent/Core/x" },
  })?.decision === "block",
  "block rm",
);

assert(
  analyzePreToolUse({
    tool_name: "apply_patch",
    tool_input: {
      command: [
        "*** Begin Patch",
        ["***", "Delete", "File:", "README.md"].join(" "),
        "",
      ].join("\n"),
    },
  })?.decision === "block",
  "block apply_patch file deletion",
);

assert(
  analyzePreToolUse({
    tool_name: "Write",
    tool_input: { file_path: ".env" },
  })?.decision === "block",
  "block sensitive file edit",
);

assert(
  analyzeStop({
    dirtyPaths: ["TODO.md", ".codex/hooks.json"],
    input: { last_assistant_message: "対応しました。" },
  })?.decision === "block",
  "stop hook nudges missing closure evidence",
);

assert(
  analyzeStop({
    dirtyPaths: ["TODO.md"],
    input: {
      last_assistant_message: "対応しました。qa-reviewと検証はPASSです。",
    },
  })?.decision === "block",
  "AC-003 INV-003 stop hook rejects verification without independent audit",
);

assert(
  analyzeStop({
    dirtyPaths: ["TODO.md"],
    input: {
      last_assistant_message:
        "対応しました。qa-reviewと検証はPASSです。反証候補を確認し、影響範囲と長期保守性を再監査しました。残リスクはありません。",
    },
  }) === null,
  "AC-003 INV-003 stop hook allows verification with multi-perspective audit",
);

assert(
  auditEvidenceCount("反証を確認し、影響範囲と長期保守性を監査した。") === 3,
  "INV-003 count distinct audit perspectives",
);

assert(
  analyzeStop({
    dirtyPaths: ["README.md"],
    input: {
      stop_hook_active: true,
      last_assistant_message: "対応しました。",
    },
  }) === null,
  "stop hook avoids recursive block",
);

const HOOK_SCRIPT = `${Deno.cwd()}/scripts/agent-workflow-hook.ts`;

const sanitizedEnv = (): Record<string, string> => {
  const env = { ...Deno.env.toObject() };
  delete env.LD_LIBRARY_PATH;
  delete env.LD_PRELOAD;
  return env;
};

const runGitIn = async (cwd: string, args: string[]): Promise<void> => {
  const output = await new Deno.Command("git", {
    args,
    cwd,
    clearEnv: true,
    env: sanitizedEnv(),
    stdout: "piped",
    stderr: "piped",
  }).output();
  if (!output.success) {
    throw new Error(
      `git ${args.join(" ")} failed: ${
        new TextDecoder().decode(output.stderr)
      }`,
    );
  }
};

const runStopHook = async (
  args: string[],
  cwd: string,
): Promise<{ code: number; stdout: string; stderr: string }> => {
  const command = new Deno.Command(Deno.execPath(), {
    args,
    cwd,
    clearEnv: true,
    env: sanitizedEnv(),
    stdin: "piped",
    stdout: "piped",
    stderr: "piped",
  });
  const child = command.spawn();
  const writer = child.stdin.getWriter();
  await writer.write(
    new TextEncoder().encode(
      JSON.stringify({
        hook_event_name: "Stop",
        last_assistant_message: "対応しました。",
      }),
    ),
  );
  await writer.close();
  const output = await child.output();
  return {
    code: output.code,
    stdout: new TextDecoder().decode(output.stdout).trim(),
    stderr: new TextDecoder().decode(output.stderr).trim(),
  };
};

const stopFixture = await Deno.makeTempDir({ prefix: "docs-dd-stop-hook-" });
try {
  await Deno.writeTextFile(`${stopFixture}/TODO.md`, "# TODO\n");
  await runGitIn(stopFixture, ["init", "--quiet"]);
  await runGitIn(stopFixture, ["config", "user.email", "hook@example.test"]);
  await runGitIn(stopFixture, ["config", "user.name", "Hook"]);
  await runGitIn(stopFixture, ["add", "TODO.md"]);
  await runGitIn(stopFixture, ["commit", "--quiet", "-m", "base"]);
  await Deno.writeTextFile(`${stopFixture}/TODO.md`, "# TODO\n\ndirty\n");

  const stopWithContract = await runStopHook([
    "run",
    "--allow-read",
    "--allow-env",
    "--allow-run=git",
    HOOK_SCRIPT,
    "stop",
  ], stopFixture);
  assert(
    stopWithContract.code === 0 &&
      stopWithContract.stdout.includes('"decision":"block"'),
    "Stop hook blocks under declared --allow-read --allow-env --allow-run=git",
  );

  const stopWithoutEnv = await runStopHook([
    "run",
    "--allow-read",
    "--allow-run=git",
    HOOK_SCRIPT,
    "stop",
  ], stopFixture);
  assert(
    stopWithoutEnv.code !== 0 &&
      stopWithoutEnv.stderr.includes("--allow-env") &&
      !stopWithoutEnv.stdout.includes('"decision"'),
    "Stop hook fails closed without --allow-env instead of silent skip",
  );
} finally {
  await Deno.remove(stopFixture, { recursive: true });
}
