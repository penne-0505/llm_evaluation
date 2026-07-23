// Deno版 TODO.md validator: npm / remote import 依存なし

const TODO_FILE = Deno.args[0] ?? "TODO.md";
const PRIORITIES = ["P0", "P1", "P2", "P3"] as const;
const SIZES = ["XS", "S", "M", "L", "XL"] as const;
const LARGE_SIZES = ["M", "L", "XL"] as const;
const RISKS = ["Low", "Medium", "High", "Critical"] as const;
const CATEGORIES = [
  "Feat",
  "Enhance",
  "Bug",
  "Refactor",
  "Perf",
  "Doc",
  "Test",
  "Chore",
] as const;
const REQUIRED_FIELDS = [
  "Title",
  "ID",
  "Priority",
  "Size",
  "Risk",
  "Area",
  "Dependencies",
  "Goal",
  "Acceptance Criteria",
  "Steps",
  "Description",
  "Plan",
  "Intent",
  "QA",
  "Verification",
] as const;
const SECTION_NAMES = ["Inbox", "Backlog", "Ready", "In Progress"] as const;
const DOC_PATH_FIELDS = ["Plan", "Intent", "QA", "Verification"] as const;

type Priority = (typeof PRIORITIES)[number];
type Size = (typeof SIZES)[number];
type Risk = (typeof RISKS)[number];
type Category = (typeof CATEGORIES)[number];
type SectionName = (typeof SECTION_NAMES)[number];
type RequiredField = (typeof REQUIRED_FIELDS)[number];
type DocPathField = (typeof DOC_PATH_FIELDS)[number];

type Task = {
  section: SectionName;
  lineNo: number;
  heading: string;
  fields: Record<string, string>;
  headingId?: string;
  headingIdCategory?: string;
  headingCategory?: string;
  headingTitle?: string;
  headingError?: string;
};

type TitleParts = {
  category: string;
  title: string;
};

type ValidateDocPathParams = {
  task: Task;
  label: string;
  field: DocPathField;
  value: string | undefined;
  mustExist: boolean;
  errors: string[];
};

const CATEGORY_PATTERN = CATEGORIES.join("|");
const ID_RE = new RegExp(
  `^([A-Za-z][A-Za-z0-9-]*)-(${CATEGORY_PATTERN})-([1-9]\\d*)$`,
);
const TASK_HEADING_RE = new RegExp(
  `^###\\s+([A-Za-z][A-Za-z0-9-]*-(${CATEGORY_PATTERN})-[1-9]\\d*):\\s+\\[(${CATEGORY_PATTERN})\\]\\s+(.+?)\\s*$`,
);
const FIELD_RE =
  /^-\s+(?:\*\*([A-Za-z][A-Za-z ]*)\*\*|([A-Za-z][A-Za-z ]*)):\s*(.*)$/;
const PATH_PATTERNS: Record<DocPathField, RegExp> = {
  Plan:
    /^_docs\/plan\/([A-Za-z][A-Za-z0-9-]*)\/([a-z0-9]+(?:-[a-z0-9]+)*)\/plan\.md$/,
  Intent:
    /^_docs\/intent\/([A-Za-z][A-Za-z0-9-]*)\/([a-z0-9]+(?:-[a-z0-9]+)*)\/decision\.md$/,
  QA:
    /^_docs\/qa\/([A-Za-z][A-Za-z0-9-]*)\/([a-z0-9]+(?:-[a-z0-9]+)*)\/test-plan\.md$/,
  Verification:
    /^_docs\/qa\/([A-Za-z][A-Za-z0-9-]*)\/([a-z0-9]+(?:-[a-z0-9]+)*)\/verification\.md$/,
};

const stripCodeBlocks = (src: string): string => {
  const output: string[] = [];
  let inFence = false;
  for (const line of src.split(/\r?\n/)) {
    if (/^\s*```/.test(line)) {
      inFence = !inFence;
      output.push("");
      continue;
    }
    output.push(inFence ? "" : line);
  }
  return output.join("\n");
};

const normalizeInlineCode = (value: string): string => {
  const trimmed = value.trim();
  if (trimmed.startsWith("`") && trimmed.endsWith("`")) {
    return trimmed.slice(1, -1).trim();
  }
  return trimmed;
};

const normalizeSectionName = (value: string): string =>
  value.replace(/\s*\(.*\)\s*$/, "").trim();

const parseTasks = (src: string): Task[] => {
  const lines = src.split(/\r?\n/);
  const tasks: Task[] = [];
  let currentSection: SectionName | null = null;
  let current: Task | null = null;
  let currentField: string | null = null;

  const flush = (): void => {
    if (current) tasks.push(current);
    current = null;
    currentField = null;
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const lineNo = index + 1;
    const section = line.match(/^##\s+(.+?)\s*$/);
    if (section) {
      flush();
      currentSection = normalizeSectionName(section[1]) as SectionName;
      continue;
    }

    if (!SECTION_NAMES.includes(currentSection as SectionName)) continue;

    const heading = line.match(/^###\s+(.+?)\s*$/);
    if (heading) {
      flush();
      const headingMatch = line.match(TASK_HEADING_RE);
      current = {
        section: currentSection as SectionName,
        lineNo,
        heading: heading[1].trim(),
        fields: {},
      };
      if (headingMatch) {
        current.headingId = headingMatch[1];
        current.headingIdCategory = headingMatch[2];
        current.headingCategory = headingMatch[3];
        current.headingTitle = headingMatch[4].trim();
      } else {
        current.headingError =
          "task heading must match ### <ID>: [<Category>] <Title>";
      }
      continue;
    }

    if (!current) continue;
    const field = line.match(FIELD_RE);
    if (field) {
      const fieldName = (field[1] ?? field[2]).trim();
      current.fields[fieldName] = field[3].trim();
      currentField = fieldName;
      continue;
    }
    if (currentField && (/^\s+/.test(line) || line.trim() === "")) {
      current.fields[currentField] = `${
        current.fields[currentField] ?? ""
      }\n${line}`.trimEnd();
    }
  }
  flush();
  return tasks;
};

const parseDependencies = (value: string): string[] | null => {
  const normalized = normalizeInlineCode(value);
  if (normalized === "[]") return [];
  if (!normalized.startsWith("[") || !normalized.endsWith("]")) return null;
  const inner = normalized.slice(1, -1).trim();
  if (inner === "") return [];
  return inner.split(",").map((item) => item.trim()).filter(Boolean);
};

const fileExists = async (path: string): Promise<boolean> => {
  try {
    const stat = await Deno.stat(path);
    return stat.isFile;
  } catch (err) {
    if (err instanceof Deno.errors.NotFound) return false;
    throw err;
  }
};

const add = (list: string[], message: string): void => {
  list.push(message);
};

const report = (
  prefix: string,
  messages: string[],
  logger: (message: string) => void,
): void => {
  if (!messages.length) return;
  logger(`${prefix}: ${TODO_FILE}`);
  for (const message of messages) logger(`  - ${message}`);
};

const riskAtLeast = (risk: string, floor: Risk): boolean =>
  (RISKS as readonly string[]).indexOf(risk) >=
    (RISKS as readonly string[]).indexOf(floor);

const isNone = (value: string | undefined): boolean =>
  normalizeInlineCode(value ?? "") === "None";

const validateDocPath = async ({
  task,
  label,
  field,
  value,
  mustExist,
  errors,
}: ValidateDocPathParams): Promise<void> => {
  const normalized = normalizeInlineCode(value ?? "");
  if (normalized === "" || normalized === "None") return;

  const match = normalized.match(PATH_PATTERNS[field]);
  if (!match) {
    add(errors, `${label}: ${field} must match canonical ${field} path`);
    return;
  }

  const [, docArea] = match;
  if (task.fields.Area && docArea !== task.fields.Area) {
    add(errors, `${label}: ${field} Area segment must match Area field`);
  }

  if (mustExist && !await fileExists(normalized)) {
    add(errors, `${label}: ${field} file does not exist: ${normalized}`);
  }
};

const acceptanceCriteriaIds = (value: string | undefined): string[] =>
  [...(value ?? "").matchAll(/\bAC-\d{3}\b/g)].map((match) => match[0]);

const titleParts = (title: string): TitleParts | null => {
  const match = title.match(/^\[([A-Za-z]+)\]\s+(.+)$/);
  if (!match) return null;
  return { category: match[1], title: match[2].trim() };
};

const taskLabel = (task: Task): string =>
  task.headingId ?? task.fields.ID ?? task.fields.Title ??
    `line ${task.lineNo}: ${task.heading}`;

const validateHeadingConsistency = (
  task: Task,
  label: string,
  errors: string[],
): void => {
  if (task.headingError) {
    add(errors, `${label}: ${task.headingError}`);
    return;
  }

  const id = task.fields.ID ?? "";
  if (id && id !== task.headingId) {
    add(errors, `${label}: heading ID must match ID field`);
  }

  const title = task.fields.Title ?? "";
  const parsedTitle = titleParts(title);
  if (parsedTitle) {
    if (parsedTitle.category !== task.headingCategory) {
      add(errors, `${label}: heading Category must match Title field category`);
    }
    if (parsedTitle.title !== task.headingTitle) {
      add(errors, `${label}: heading Title must match Title field text`);
    }
  }

  if (task.headingIdCategory !== task.headingCategory) {
    add(errors, `${label}: ID category must match heading Category`);
  }
};

const run = async (): Promise<void> => {
  const src = await Deno.readTextFile(TODO_FILE);
  const stripped = stripCodeBlocks(src);
  const errors: string[] = [];
  const warnings: string[] = [];

  const nextMatch = stripped.match(/Next ID No:\s*(\d+)/);
  if (!nextMatch) {
    add(errors, "Next ID No: <number> is required");
  }
  const nextIdNo = nextMatch ? Number(nextMatch[1]) : null;
  if (nextIdNo !== null && (!Number.isInteger(nextIdNo) || nextIdNo <= 0)) {
    add(errors, "Next ID No must be a positive integer");
  }

  for (const section of SECTION_NAMES) {
    if (!new RegExp(`^##\\s+${section}\\b`, "m").test(stripped)) {
      add(errors, `missing required section: ${section}`);
    }
  }
  if (/^##\s+(Done|Archived)\b/m.test(stripped)) {
    add(errors, "TODO.md must not define Done or Archived sections");
  }

  const tasks = parseTasks(stripped);
  const ids = new Set<string>();
  let maxIdNo = 0;

  for (const task of tasks) {
    const label = taskLabel(task);
    validateHeadingConsistency(task, label, errors);

    for (const field of REQUIRED_FIELDS) {
      if (!(field in task.fields) || task.fields[field].trim() === "") {
        add(errors, `${label}: missing required field: ${field}`);
      }
    }

    const title = task.fields.Title ?? "";
    const parsedTitle = titleParts(title);
    if (!parsedTitle) {
      add(errors, `${label}: Title must match "[Category] Title"`);
    } else if (
      !(CATEGORIES as readonly string[]).includes(parsedTitle.category)
    ) {
      add(
        errors,
        `${label}: Title category must be one of ${CATEGORIES.join(", ")}`,
      );
    }

    const id = task.fields.ID ?? "";
    const idMatch = id.match(ID_RE);
    if (!idMatch) {
      add(errors, `${label}: ID must match <Area>-<Category>-<Number>`);
    } else {
      const [, idArea, idCategory, idNumberRaw] = idMatch;
      const idNumber = Number(idNumberRaw);
      maxIdNo = Math.max(maxIdNo, idNumber);
      if (ids.has(id)) add(errors, `${label}: duplicate ID`);
      ids.add(id);
      if (nextIdNo !== null && idNumber >= nextIdNo) {
        add(errors, `${label}: ID number must be less than Next ID No`);
      }
      if (task.fields.Area && task.fields.Area !== idArea) {
        add(errors, `${label}: ID Area must match Area field`);
      }
      if (parsedTitle && parsedTitle.category !== idCategory) {
        add(errors, `${label}: Title category must match ID category`);
      }
      if (task.headingCategory && idCategory !== task.headingCategory) {
        add(errors, `${label}: ID category must match heading Category`);
      }
    }

    const priority = task.fields.Priority;
    if (priority && !(PRIORITIES as readonly string[]).includes(priority)) {
      add(errors, `${label}: Priority must be one of ${PRIORITIES.join(", ")}`);
    }

    const size = task.fields.Size;
    if (size && !(SIZES as readonly string[]).includes(size)) {
      add(errors, `${label}: Size must be one of ${SIZES.join(", ")}`);
    }

    const risk = task.fields.Risk;
    if (risk && !(RISKS as readonly string[]).includes(risk)) {
      add(errors, `${label}: Risk must be one of ${RISKS.join(", ")}`);
    }

    const deps = parseDependencies(task.fields.Dependencies ?? "");
    if (deps === null) {
      add(errors, `${label}: Dependencies must be [] or [ID, ID, ...]`);
    } else {
      for (const dep of deps) {
        if (!ID_RE.test(dep)) {
          add(errors, `${label}: dependency has invalid ID format: ${dep}`);
        } else if (
          !ids.has(dep) && !tasks.some((other) => other.fields.ID === dep)
        ) {
          add(
            warnings,
            `${label}: dependency is not in current TODO.md: ${dep}`,
          );
        }
      }
    }

    const category = idMatch?.[2] ?? parsedTitle?.category ?? "";
    const acIds = acceptanceCriteriaIds(task.fields["Acceptance Criteria"]);
    if (acIds.length === 0) {
      add(
        errors,
        `${label}: Acceptance Criteria must include AC-001 style IDs`,
      );
    }
    for (const acId of acIds) {
      if (!/^AC-\d{3}$/.test(acId)) {
        add(errors, `${label}: invalid acceptance criterion ID: ${acId}`);
      }
    }
    if (
      size && risk &&
      ((LARGE_SIZES as readonly string[]).includes(size) ||
        riskAtLeast(risk, "Medium")) &&
      acIds.length < 2
    ) {
      add(
        warnings,
        `${label}: Size >= M or Risk >= Medium should define at least two acceptance criteria`,
      );
    }
    if (
      category === "Bug" &&
      !/regression|prevent|再発|回帰|no-test/i.test(
        task.fields["Acceptance Criteria"] ?? "",
      )
    ) {
      add(
        warnings,
        `${label}: Bug tasks should include regression prevention in Acceptance Criteria`,
      );
    }

    const mustExist = (["Ready", "In Progress"] as readonly string[]).includes(
      task.section,
    );
    for (const field of DOC_PATH_FIELDS) {
      await validateDocPath({
        task,
        label,
        field,
        value: task.fields[field],
        mustExist,
        errors,
      });
    }

    if (size && (LARGE_SIZES as readonly string[]).includes(size)) {
      if (isNone(task.fields.Plan)) {
        add(errors, `${label}: Size ${size} requires Plan`);
      }
      if (isNone(task.fields.Intent)) {
        add(errors, `${label}: Size ${size} requires Intent`);
      }
      if (isNone(task.fields.QA)) {
        add(errors, `${label}: Size ${size} requires QA`);
      }
    }
    if (risk && riskAtLeast(risk, "Medium")) {
      if (isNone(task.fields.Intent)) {
        add(errors, `${label}: Risk ${risk} requires Intent`);
      }
      if (isNone(task.fields.QA)) {
        add(errors, `${label}: Risk ${risk} requires QA`);
      }
    }
    if (risk && riskAtLeast(risk, "High")) {
      if (isNone(task.fields.Plan)) {
        add(errors, `${label}: Risk ${risk} requires Plan`);
      }
      if (isNone(task.fields.Intent)) {
        add(errors, `${label}: Risk ${risk} requires Intent`);
      }
      if (isNone(task.fields.QA)) {
        add(errors, `${label}: Risk ${risk} requires QA`);
      }
      if (task.section === "In Progress" && isNone(task.fields.Verification)) {
        add(
          warnings,
          `${label}: In Progress High/Critical risk task should already have Verification`,
        );
      }
    }
  }

  if (nextIdNo !== null && maxIdNo > 0 && nextIdNo < maxIdNo + 1) {
    add(errors, "Next ID No must be at least the max existing ID number + 1");
  }

  report("WARN", warnings, console.warn);
  if (errors.length) {
    report("ERROR", errors, console.error);
    Deno.exit(1);
  }
};

run().catch((err: unknown) => {
  console.error(err instanceof Error ? err.message : String(err));
  Deno.exit(1);
});
