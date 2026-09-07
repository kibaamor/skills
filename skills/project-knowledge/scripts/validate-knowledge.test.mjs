import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { validateKnowledge } from "./validate-knowledge.mjs";

test("accepts valid knowledge links and heading structure", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await mkdir(path.join(root, "src"));
  await writeFile(path.join(root, "src", "app.js"), "module.exports = {};\n");
  await writeFile(
    path.join(root, "AGENTS.md"),
    "# Repository Guide\n\n## Start Here\n\n[App](./src/app.js)\n\n[Start](#start-here)\n\n```mermaid\nflowchart LR\n  A --> B\n```\n",
  );

  assert.deepEqual(await validateKnowledge(root, ["AGENTS.md"]), []);
});

test("rejects missing heading anchors and invalid Mermaid blocks", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await writeFile(
    path.join(root, "ARCHITECTURE.md"),
    "# Architecture\n\n[Missing](#missing-section)\n\n```mermaid\nA --> [B\n```\n",
  );

  const errors = await validateKnowledge(root, ["ARCHITECTURE.md"]);
  assert.equal(errors.length, 3);
  assert.ok(errors.some((error) => error.includes("unresolved heading link")));
  assert.ok(errors.some((error) => error.includes("diagram type")));
  assert.ok(errors.some((error) => error.includes("unbalanced delimiters")));
});

test("rejects missing links, duplicate headings, and skipped levels", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await writeFile(
    path.join(root, "CODE-MAP.md"),
    "# Code Map\n\n## Modules\n\n#### Missing\n\n## Modules\n\n[Handler](./src/Handler.js)\n",
  );

  const errors = await validateKnowledge(root, ["CODE-MAP.md"]);
  assert.equal(errors.length, 3);
  assert.ok(errors.some((error) => error.includes("heading level skips")));
  assert.ok(errors.some((error) => error.includes("duplicate heading")));
  assert.ok(
    errors.some((error) =>
      error.includes("unresolved or case-mismatched link"),
    ),
  );
});

test("rejects duplicate GitHub-style heading anchors", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await writeFile(
    path.join(root, "AGENTS.md"),
    "# Repository Guide\n\n## API & UI\n\n## API UI\n",
  );

  const errors = await validateKnowledge(root, ["AGENTS.md"]);
  assert.equal(errors.length, 1);
  assert.ok(errors[0].includes('duplicate heading anchor "api-ui"'));
});

test("handles encoded, external, image, and fenced links", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await mkdir(path.join(root, "docs"));
  await writeFile(path.join(root, "docs", "with space.md"), "# Details\n");
  await writeFile(path.join(root, "diagram.png"), "not really an image\n");
  await writeFile(
    path.join(root, "AGENTS.md"),
    [
      "# Repository Guide",
      "",
      "[Encoded](./docs/with%20space.md#details)",
      "[External](https://example.com/missing)",
      "![Diagram](./diagram.png)",
      "[Reference]: ./docs/with%20space.md#details",
      "",
      "```md",
      "[Ignored](./missing.md)",
      "## Ignored Heading",
      "```",
      "",
    ].join("\n"),
  );

  assert.deepEqual(await validateKnowledge(root, ["AGENTS.md"]), []);
});

test("rejects missing reference-style links", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await writeFile(
    path.join(root, "AGENTS.md"),
    "# Repository Guide\n\n[Missing]: ./missing.md\n",
  );

  const errors = await validateKnowledge(root, ["AGENTS.md"]);
  assert.equal(errors.length, 1);
  assert.ok(errors[0].includes("unresolved or case-mismatched link"));
});

test("ignores Mermaid delimiters inside quoted labels", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await writeFile(
    path.join(root, "ARCHITECTURE.md"),
    '# Architecture\n\n```mermaid\nflowchart LR\n  A["JSON {schema"] --> B\n```\n',
  );

  assert.deepEqual(await validateKnowledge(root, ["ARCHITECTURE.md"]), []);
});

test("accepts common Markdown links, anchors, and ignored examples", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await mkdir(path.join(root, "docs"));
  await mkdir(path.join(root, "src"));
  await writeFile(path.join(root, "docs", "guide(v2).md"), "# Guide\n");
  await writeFile(path.join(root, "docs", "with space.md"), "# Guide\n");
  await writeFile(path.join(root, "src", "app.js"), "export const app = {};\n");
  await writeFile(
    path.join(root, "CODE-MAP.md"),
    [
      "# Code Map",
      "",
      "foo_bar",
      "-------",
      "",
      "[Section](#foo_bar)",
      "[Parenthesized](./docs/guide(v2).md)",
      "[Spaced][guide]",
      "[Source line](./src/app.js#L1)",
      "",
      "[guide]: <./docs/with space.md>",
      "",
      "<!-- [Ignored](./missing-comment.md) -->",
      "`[Ignored](./missing-code.md)`",
      "",
    ].join("\n"),
  );

  assert.deepEqual(await validateKnowledge(root, ["CODE-MAP.md"]), []);
});

test("rejects undefined reference links", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await writeFile(
    path.join(root, "AGENTS.md"),
    "# Repository Guide\n\n[Missing][missing-reference]\n",
  );

  const errors = await validateKnowledge(root, ["AGENTS.md"]);
  assert.equal(errors.length, 1);
  assert.ok(errors[0].includes("undefined reference link"));
});

test("accepts Mermaid declarations and comments beyond a fixed allowlist", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await writeFile(
    path.join(root, "ARCHITECTURE.md"),
    "# Architecture\n\n```mermaid\nC4Context\n  %% Explain [legacy syntax\n  Person(user, User)\n```\n",
  );

  assert.deepEqual(await validateKnowledge(root, ["ARCHITECTURE.md"]), []);
});

test("rejects unclosed Mermaid blocks", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await writeFile(
    path.join(root, "ARCHITECTURE.md"),
    "# Architecture\n\n```mermaid\nflowchart LR\n  A --> B\n",
  );

  const errors = await validateKnowledge(root, ["ARCHITECTURE.md"]);
  assert.equal(errors.length, 1);
  assert.ok(errors[0].includes("unclosed Mermaid block"));
});

test("ignores YAML frontmatter when validating headings", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "project-knowledge-"));
  await writeFile(
    path.join(root, "AGENTS.md"),
    "---\ntitle: Repository Guide\n---\n\n# Repository Guide\n",
  );

  assert.deepEqual(await validateKnowledge(root, ["AGENTS.md"]), []);
});
