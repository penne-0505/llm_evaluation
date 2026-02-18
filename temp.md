You are a senior front-end engineer. Your task is to build a complete, multi-page UI prototype for an LLM benchmark application.

Work autonomously from start to finish: design the file structure, implement all pages, wire up navigation and shared state, and verify the result runs correctly. Do not ask for clarification — make your own decisions.

---

## Application Overview

A benchmarking tool that sends prompts to a subject LLM, then evaluates the responses using multiple judge LLMs via task-specific rubrics ("LLM-as-a-Judge" pattern).
Supported providers: OpenAI, Anthropic, Gemini, OpenRouter.

---

## Pages to Implement

### Page 1 — Settings

**API Key Management**
- Input, save, and delete API keys per provider (OpenAI / Anthropic / Gemini / OpenRouter)
- Clearly indicate which providers have no key set, and which failed with an error (show the error message)

**Model Selection**
- Select one subject model and one or more judge models from a list fetched via API
- Show error if fewer than 1 judge is selected; show warning if fewer than 3
- Show last-updated timestamp for the model list; provide a manual refresh button
- Fall back to free-text input when no API key is configured

**Evaluation Parameters**
- Judge run count: 1–5
- Subject LLM temperature: 0.0–1.0
- Judge temperature: fixed at 0.0 (display only, not editable)

**Persistence**
- Save current selections (models, run count, temperature); restore on next load

**Task Selection**
- List of tasks (ID + type: fact / creative / speculative), select one or more
- Select all / deselect all buttons
- Show selected task count

---

### Page 2 — Run

**Pre-run confirmation**
- Selected subject model
- Selected judge models (list + count)
- Selected tasks (list + count)
- Total step count (tasks × judges × run count)

**In-progress state**
- Overall progress bar (completed steps / total steps)
- Currently processing: task number, task ID, judge model name
- Elapsed time

**Controls**
- "Start Evaluation" button (disabled while running)
- "Cancel" button (visible only while running)

**Completed state**
- Success message
- Path of the saved result file
- Link / button to navigate to the Results page

**Cancelled state**
- Cancellation message
- Completed task count / total task count

Simulate the evaluation process with a timer (no real API calls needed).

---

### Page 3 — Results

Displays the result of the most recently completed evaluation run.

**Run metadata**
- Subject model name
- Run timestamp
- List of judge models used

**Per-task results** (one section per evaluated task)
- Task ID and type (fact / creative / speculative)
- Full response text from the subject LLM
- Per-judge evaluation (see below)

**Per-judge evaluation** (shown separately per judge — do not aggregate across judges)
- Three-axis scores (mean ± SD): Logic & Fact, Constraint Adherence, Helpfulness
- Total Score (mean ± SD) with a progress bar (0–100)
- Confidence distribution: count of High / Medium / Low across runs
- Critical Fail flag: if detected, show an alert with the reason
- Reasoning text: up to 3 run samples

**Cross-task summary**
- Per judge: average score across all tasks + number of tasks evaluated
- Review list: flag task × judge combinations that meet any of:
  - Score SD > 5
  - Critical Fail detected
  - Low Confidence present

---

### Page 4 — Dashboard

Displays aggregated data from all past evaluation runs.

**Model score comparison chart**
- Bar chart of average scores per model (up to 20 models)
- Color-code bars by score band: ≥80 / ≥60 / <60
- On hover: full model name, average score, run count, best score

**Evaluation history list**
- Card-based list with pagination (prev / next)
- Each card: short model name, average score, relative timestamp, task count
- Each card navigates to the full result detail (reuse Page 3 layout)

**Side-by-side comparison**
- Select two past results to compare
- Summary: average score per model
- Per task: response text, per-judge scores, and missing-run indicators — shown side by side

**Recent runs**
- Last 5 runs: model name, average score, timestamp, task count, judge count

**Aggregation table**
- All models: model name, run count, average score, best score, latest run date

If no past results exist, show a first-use guide: API keys → model selection → task selection → start evaluation.

---

## Data & State

All backend calls should be replaced with realistic dummy data and local state. Design your own TypeScript types. Shared state (selected models, task list, latest result, history) must be accessible across all pages.

Errors to handle in the UI (no crashes — show inline messages):
- Task file not found
- Invalid environment path
- Runtime error during evaluation (show message + stack trace placeholder)
- Save attempted without API key
- Delete attempted without selecting a provider
- History load failure

---

## Technical Requirements

- **Framework**: React with TypeScript
- **Styling**: your choice (Tailwind CSS, CSS Modules, styled-components, shadcn/ui, etc.)
- **Charts**: your choice (Recharts, Chart.js, Visx, etc.)
- **Routing**: your choice (React Router, TanStack Router, etc.)
- **State management**: your choice
- Design, layout, and UX are entirely your call.

---

## Deliverables

1. A working Vite + React + TypeScript project
2. All four pages fully implemented and navigable
3. Realistic dummy data populating every view
4. A `README.md` with: how to install, how to run, and a brief description of architectural decisions made

Proceed without asking questions. Make all design and implementation decisions yourself.
