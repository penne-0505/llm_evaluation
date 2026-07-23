// Deno validator self-test runner: exercises valid and intentionally invalid fixtures.

type ValidatorKind = "todo" | "intent" | "qa" | "frontmatter";

type TestCaseParams = {
  kind: ValidatorKind;
  target: string;
  shouldPass: boolean;
};

type ScopeCaseParams = {
  label: string;
  scopePaths: string;
  shouldPass: boolean;
};

type CommandResult = {
  code: number;
  stdout: string;
  stderr: string;
};

const TODO_VALID = [
  "_evals/validator-fixtures/todo/valid/basic.md",
];
const TODO_INVALID = [
  "_evals/validator-fixtures/todo/invalid/missing-title.md",
  "_evals/validator-fixtures/todo/invalid/malformed-heading.md",
  "_evals/validator-fixtures/todo/invalid/missing-qa-for-medium.md",
  "_evals/validator-fixtures/todo/invalid/mismatched-heading-id.md",
];
const INTENT_VALID = [
  "_evals/validator-fixtures/intent/valid",
];
const INTENT_INVALID = [
  "_evals/validator-fixtures/intent/invalid/missing-why.md",
  "_evals/validator-fixtures/intent/invalid/orphan-invariant.md",
];
const QA_VALID = [
  "_evals/validator-fixtures/qa/valid",
];
const QA_INVALID = [
  "_evals/validator-fixtures/qa/invalid/missing-invariant.md",
  "_evals/validator-fixtures/qa/invalid/v2-missing-decision-scope.md",
  "_evals/validator-fixtures/qa/invalid/status-verdict-mismatch.md",
  "_evals/validator-fixtures/qa/invalid/verification-in-progress-status.md",
  "_evals/validator-fixtures/qa/invalid/verification-missing-test-plan-reference.md",
  "_evals/validator-fixtures/qa/invalid/qa-archive-path.md",
];
const FRONTMATTER_VALID = [
  "_evals/validator-fixtures/frontmatter/valid/intent-schema.md",
  "_evals/validator-fixtures/frontmatter/valid/qa-schema.md",
];
const FRONTMATTER_INVALID = [
  "_evals/validator-fixtures/frontmatter/invalid/duplicate-field.md",
  "_evals/validator-fixtures/frontmatter/invalid/unknown-field.md",
  "_evals/validator-fixtures/frontmatter/invalid/wrong-type.md",
  "_evals/validator-fixtures/frontmatter/invalid/intent-schema-on-qa.md",
  "_evals/validator-fixtures/frontmatter/invalid/qa-schema-on-intent.md",
];

const deno = Deno.execPath();

const runCommand = async (args: string[]): Promise<CommandResult> => {
  const command = new Deno.Command(deno, {
    args,
    stdout: "piped",
    stderr: "piped",
  });
  const output = await command.output();
  return {
    code: output.code,
    stdout: new TextDecoder().decode(output.stdout).trim(),
    stderr: new TextDecoder().decode(output.stderr).trim(),
  };
};

const validatorArgs = (kind: ValidatorKind, target: string): string[] => {
  if (kind === "frontmatter") {
    return [
      "run",
      "--allow-read",
      "scripts/validate-frontmatter.ts",
      "--fixture",
      target,
    ];
  }
  if (kind === "todo") {
    return ["run", "--allow-read", "scripts/validate-todo.ts", target];
  }
  if (kind === "intent") {
    return [
      "run",
      "--allow-read",
      "scripts/validate-intent.ts",
      "--fixture",
      target,
    ];
  }
  return [
    "run",
    "--allow-read",
    "scripts/validate-qa.ts",
    "--fixture",
    target,
  ];
};

const testCase = async ({
  kind,
  target,
  shouldPass,
}: TestCaseParams): Promise<boolean> => {
  const result = await runCommand(validatorArgs(kind, target));
  const passed = shouldPass ? result.code === 0 : result.code !== 0;
  const label = `${kind} ${target}`;
  if (passed) {
    console.log(
      shouldPass ? `PASS ${label}` : `PASS ${label} failed as expected`,
    );
    return true;
  }

  console.error(
    shouldPass
      ? `FAIL ${label} expected exit 0, got ${result.code}`
      : `FAIL ${label} expected non-zero exit, got 0`,
  );
  if (result.stdout) console.error(result.stdout);
  if (result.stderr) console.error(result.stderr);
  return false;
};

// スコープ機構の決定的テスト: DD_SCOPE_PATHS が対象を絞ることを git なしで確認する。
const SCOPE_FIXTURE =
  "_evals/validator-fixtures/qa/invalid/missing-invariant.md";

// Cursor AppImage 等が LD_LIBRARY_PATH を付ける環境では、子 process にそのまま
// 継承させると --allow-run=git が拒否される。親 env を掃除してから上書きする。
const childEnv = (
  overrides: Record<string, string>,
): Record<string, string> => {
  const env = { ...Deno.env.toObject() };
  delete env.LD_LIBRARY_PATH;
  delete env.LD_PRELOAD;
  return { ...env, ...overrides };
};

const runQaWithScope = async (scopePaths: string): Promise<number> => {
  const command = new Deno.Command(deno, {
    args: [
      "run",
      "--allow-read",
      "--allow-env",
      "scripts/validate-qa.ts",
      "--fixture",
      SCOPE_FIXTURE,
    ],
    clearEnv: true,
    env: childEnv({ DD_SCOPE_PATHS: scopePaths }),
    stdout: "piped",
    stderr: "piped",
  });
  const output = await command.output();
  return output.code;
};

const runFrontmatterWithGitScope = async (
  env: Record<string, string>,
): Promise<number> => {
  const command = new Deno.Command(deno, {
    args: [
      "run",
      "--allow-read",
      "--allow-env",
      "--allow-run=git",
      "scripts/validate-frontmatter.ts",
    ],
    clearEnv: true,
    env: childEnv(env),
    stdout: "piped",
    stderr: "piped",
  });
  const output = await command.output();
  return output.code;
};

const runFrontmatterIn = async (
  cwd: string,
  env: Record<string, string>,
): Promise<number> => {
  const command = new Deno.Command(deno, {
    args: [
      "run",
      "--allow-read",
      "--allow-env",
      "--allow-run=git",
      `${Deno.cwd()}/scripts/validate-frontmatter.ts`,
    ],
    cwd,
    clearEnv: true,
    env: childEnv(env),
    stdout: "piped",
    stderr: "piped",
  });
  const output = await command.output();
  return output.code;
};

const runGit = async (cwd: string, args: string[]): Promise<string> => {
  const output = await new Deno.Command("git", {
    args,
    cwd,
    clearEnv: true,
    env: childEnv({}),
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
  return new TextDecoder().decode(output.stdout).trim();
};

const runCompatibilityBaselineCases = async (): Promise<boolean> => {
  const temp = await Deno.makeTempDir({
    dir: Deno.cwd(),
    prefix: ".docs-dd-compatibility-",
  });
  const legacyPath = "_docs/draft/legacy.md";
  const retiredPath = "_docs/draft/retired.md";
  const legacyContent = "# Legacy\n\nRemediated lint only.\n";
  try {
    await ensureDir(`${temp}/_docs/draft`);
    await write(`${temp}/${legacyPath}`, "# Legacy\n");
    await write(`${temp}/${retiredPath}`, "# Retired legacy\n");
    await runGit(temp, ["init", "--quiet"]);
    await runGit(temp, ["config", "user.email", "validator@example.test"]);
    await runGit(temp, ["config", "user.name", "Validator"]);
    await runGit(temp, ["add", "."]);
    await runGit(temp, ["commit", "--quiet", "-m", "base"]);
    const base = await runGit(temp, ["rev-parse", "HEAD"]);

    await write(`${temp}/${legacyPath}`, legacyContent);
    await runGit(temp, ["add", "."]);
    await runGit(temp, ["commit", "--quiet", "-m", "lint remediation"]);
    const blob = await runGit(temp, ["hash-object", "--", legacyPath]);
    const retiredBlob = await runGit(temp, ["hash-object", "--", retiredPath]);
    const manifest = `${temp}/compatibility.tsv`;
    const writeManifest = (rows: Array<[string, string]>): Promise<void> =>
      write(
        manifest,
        `path\tblob_sha1\n${
          rows.map(([path, sha]) => `${path}\t${sha}`).join("\n")
        }\n`,
      );
    await writeManifest([[legacyPath, blob], [retiredPath, retiredBlob]]);
    const scopeEnv = {
      DD_SCOPE_BASE: base,
      DD_SCOPE_DIFF_FILTER: "ACMR",
      DD_SCOPE_COMPATIBILITY_BASELINE: manifest,
    };

    if (await runFrontmatterIn(temp, scopeEnv) !== 0) return false;

    await write(`${temp}/${legacyPath}`, "# Legacy\n\nContent changed.\n");
    if (await runFrontmatterIn(temp, scopeEnv) === 0) return false;
    await write(`${temp}/${legacyPath}`, legacyContent);

    await writeManifest([["_docs/draft/unknown.md", blob]]);
    if (await runFrontmatterIn(temp, scopeEnv) === 0) return false;

    await writeManifest([[
      legacyPath,
      "0000000000000000000000000000000000000000",
    ]]);
    if (await runFrontmatterIn(temp, scopeEnv) === 0) return false;

    await write(manifest, "path\tblob_sha1\nmalformed-row\n");
    if (await runFrontmatterIn(temp, scopeEnv) === 0) return false;

    await writeManifest([[legacyPath, blob], [retiredPath, retiredBlob]]);
    await Deno.remove(`${temp}/${retiredPath}`);
    await runGit(temp, ["add", "-u"]);
    await runGit(temp, ["commit", "--quiet", "-m", "retire legacy doc"]);
    if (await runFrontmatterIn(temp, scopeEnv) === 0) return false;

    await writeManifest([[legacyPath, blob]]);
    return (await runFrontmatterIn(temp, scopeEnv)) === 0;
  } finally {
    await Deno.remove(temp, { recursive: true });
  }
};

const ensureDir = async (path: string): Promise<void> => {
  await Deno.mkdir(path, { recursive: true });
};

const write = (path: string, content: string): Promise<void> =>
  Deno.writeTextFile(path, content);

const runScopedTodoQaConsistencyCase = async () => {
  const repoRoot = Deno.cwd();
  const temp = await Deno.makeTempDir({
    dir: Deno.cwd(),
    prefix: ".docs-dd-qa-scope-",
  });
  try {
    await ensureDir(`${temp}/_docs/qa/Core/scoped-qa`);
    await ensureDir(`${temp}/_docs/intent/Core/scoped-qa`);
    await write(
      `${temp}/TODO.md`,
      `# Project Task Management Rules

## Backlog

### Core-Feat-1: [Feat] Scoped QA

- **Title**: [Feat] Scoped QA
- **ID**: Core-Feat-1
- **Risk**: Medium
- **Intent**: _docs/intent/Core/scoped-qa/decision.md
- **QA**: _docs/qa/Core/scoped-qa/test-plan.md
- **Verification**: None
`,
    );
    await write(
      `${temp}/_docs/qa/Core/scoped-qa/test-plan.md`,
      `---
title: Scoped QA test plan
status: active
draft_status: n/a
qa_status: planned
risk: Low
created_at: 2026-01-01
updated_at: 2026-01-01
references:
  - "_docs/intent/Core/scoped-qa/decision.md"
related_issues: []
related_prs: []
---

# Scoped QA test plan
`,
    );

    const command = new Deno.Command(deno, {
      args: [
        "run",
        "--allow-read",
        "--allow-env",
        `${repoRoot}/scripts/validate-qa.ts`,
        "_docs/qa",
      ],
      cwd: temp,
      env: { DD_SCOPE_PATHS: "_docs/qa/Other/not-this.md" },
      stdout: "piped",
      stderr: "piped",
    });
    const output = await command.output();
    return output.code !== 0;
  } finally {
    await Deno.remove(temp, { recursive: true });
  }
};

const scopeCase = async ({
  label,
  scopePaths,
  shouldPass,
}: ScopeCaseParams): Promise<boolean> => {
  const code = await runQaWithScope(scopePaths);
  const passed = shouldPass ? code === 0 : code !== 0;
  if (passed) {
    console.log(`PASS scope ${label}`);
    return true;
  }
  console.error(
    `FAIL scope ${label}: exit ${code} (expected ${
      shouldPass ? "0" : "non-zero"
    })`,
  );
  return false;
};

let ok = true;

for (const target of TODO_VALID) {
  ok = await testCase({ kind: "todo", target, shouldPass: true }) && ok;
}
for (const target of TODO_INVALID) {
  ok = await testCase({ kind: "todo", target, shouldPass: false }) && ok;
}
for (const target of INTENT_VALID) {
  ok = await testCase({ kind: "intent", target, shouldPass: true }) && ok;
}
for (const target of INTENT_INVALID) {
  ok = await testCase({ kind: "intent", target, shouldPass: false }) && ok;
}
for (const target of QA_VALID) {
  ok = await testCase({ kind: "qa", target, shouldPass: true }) && ok;
}
for (const target of QA_INVALID) {
  ok = await testCase({ kind: "qa", target, shouldPass: false }) && ok;
}
for (const target of FRONTMATTER_VALID) {
  ok = await testCase({ kind: "frontmatter", target, shouldPass: true }) && ok;
}
for (const target of FRONTMATTER_INVALID) {
  ok = await testCase({ kind: "frontmatter", target, shouldPass: false }) && ok;
}

// 対象外パスのみを scope に置くと、invalid fixture は判定されずに pass する。
ok = await scopeCase({
  label: "out-of-scope invalid fixture is skipped",
  scopePaths: "_evals/validator-fixtures/qa/valid/test-plan.md",
  shouldPass: true,
}) && ok;
// scope に含めると、従来通り invalid fixture が fail する。
ok = await scopeCase({
  label: "in-scope invalid fixture still fails",
  scopePaths: SCOPE_FIXTURE,
  shouldPass: false,
}) && ok;

ok = await (async () => {
  const code = await runFrontmatterWithGitScope({
    DD_SCOPE_BASE: "HEAD",
    DD_SCOPE_DIFF_FILTER: "ACMR",
  });
  if (code === 0) {
    console.log("PASS scope DD_SCOPE_DIFF_FILTER accepts ACMR");
    return true;
  }
  console.error(`FAIL scope DD_SCOPE_DIFF_FILTER accepts ACMR: exit ${code}`);
  return false;
})() && ok;

ok = await (async () => {
  const passed = await runCompatibilityBaselineCases();
  if (passed) {
    console.log(
      "PASS compatibility baseline skips exact blobs, re-enters changed files, and fails closed for invalid or stale rows",
    );
    return true;
  }
  console.error(
    "FAIL compatibility baseline did not preserve exact-blob scope or fail-closed validation",
  );
  return false;
})() && ok;

ok = await (async () => {
  const passed = await runScopedTodoQaConsistencyCase();
  if (passed) {
    console.log("PASS qa TODO consistency checks scope-excluded QA refs");
    return true;
  }
  console.error("FAIL qa TODO consistency checks scope-excluded QA refs");
  return false;
})() && ok;

ok = await (async () => {
  const code = await runFrontmatterWithGitScope({
    DD_SCOPE_BASE: "HEAD",
    DD_SCOPE_DIFF_FILTER: "A;rm",
  });
  if (code !== 0) {
    console.log("PASS scope DD_SCOPE_DIFF_FILTER rejects invalid values");
    return true;
  }
  console.error("FAIL scope DD_SCOPE_DIFF_FILTER rejects invalid values");
  return false;
})() && ok;

if (!ok) Deno.exit(1);
