#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import {
  access,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const skillDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const evalsDir = path.join(skillDir, "evals");

async function readJson(file) {
  return JSON.parse(await readFile(file, "utf8"));
}

async function exists(file) {
  try {
    await access(file);
    return true;
  } catch {
    return false;
  }
}

async function behaviorTask(test) {
  const fixtureInstructions = await Promise.all(
    test.files.map(async (file) => {
      const content = await readFile(path.join(skillDir, file), "utf8");
      return [
        `Materialize fixture ${file} in the current working directory before running the skill.`,
        'Use this JSON fixture content; create every entry in its top-level "files" object relative to the current working directory and do not create another repository elsewhere.',
        "```json",
        content.trim(),
        "```",
      ].join("\n");
    }),
  );

  return {
    id: `behavior-${String(test.id).padStart(2, "0")}`,
    name: `Behavior ${test.id}: ${test.expected_output}`,
    tags: ["behavior"],
    inputs: {
      prompt: `${test.prompt}\n\nFixture setup:\n${fixtureInstructions.join("\n\n")}`,
    },
    expected: {
      should_trigger: true,
      outcomes: [{ type: "task_completed" }],
    },
    graders: [
      {
        type: "prompt",
        name: "requirements",
        config: {
          model: "gpt-5-mini",
          prompt: [
            "Evaluate the final response and the generated or updated project-knowledge-generator documents in the current workspace against every requirement.",
            "Project-knowledge documents are AGENTS.md, CONTEXT.md, CONTEXT-MAP.md, ARCHITECTURE.md, and CODE-MAP.md, including selected nested variants. Treat fixture source documents such as README.md as evidence, not generated output.",
            "If all expectations hold and no failure condition occurs, call set_waza_grade_pass with concise evidence.",
            "Otherwise, call set_waza_grade_fail with the unmet expectations and observed evidence.",
            `Expected output: ${test.expected_output}`,
            `Expectations: ${JSON.stringify(test.expectations)}`,
            `Failure conditions: ${JSON.stringify(test.failure_conditions)}`,
          ].join("\n"),
        },
      },
    ],
  };
}

function triggerTask(test, index) {
  return {
    id: `trigger-${String(index + 1).padStart(2, "0")}`,
    name: `${test.should_trigger ? "Positive" : "Negative"} trigger ${index + 1}`,
    tags: [
      "trigger",
      test.should_trigger ? "positive-trigger" : "negative-trigger",
    ],
    inputs: { prompt: test.query },
    expected: { should_trigger: test.should_trigger },
    graders: [
      {
        type: "trigger",
        name: "skill-trigger",
        config: {
          skill_path: "SKILL.md",
          mode: test.should_trigger ? "positive" : "negative",
          threshold: 0.6,
        },
      },
    ],
  };
}

export async function loadTasks() {
  const behavior = await readJson(path.join(evalsDir, "evals.json"));
  const triggers = await readJson(path.join(evalsDir, "trigger-evals.json"));
  return [
    ...(await Promise.all(behavior.evals.map(behaviorTask))),
    ...triggers.map(triggerTask),
  ];
}

async function writeSuite(directory, tasks) {
  const tasksDir = path.join(directory, "tasks");
  await mkdir(tasksDir, { recursive: true });

  const suite = {
    name: "project-knowledge-generator-eval",
    description: "Behavior and trigger evaluation for project-knowledge-generator.",
    skill: "project-knowledge-generator",
    version: "1.0",
    config: {
      trials_per_task: 1,
      timeout_seconds: 600,
      parallel: false,
      executor: "copilot-sdk",
      model: "auto",
    },
    metrics: [
      {
        name: "task_completion",
        weight: 1,
        threshold: 0.8,
        description: "Did the skill satisfy the scenario requirements?",
      },
    ],
    tasks: ["tasks/*.yaml"],
  };

  await writeFile(
    path.join(directory, "wazaEval.yaml"),
    JSON.stringify(suite, null, 2),
  );
  await Promise.all(
    tasks.map((task) =>
      writeFile(
        path.join(tasksDir, `${task.id}.yaml`),
        JSON.stringify(task, null, 2),
      ),
    ),
  );
}

function printHelp() {
  console.log(`Usage: node scripts/run-evals.mjs [--list] [waza run options]

Examples:
  node scripts/run-evals.mjs
  node scripts/run-evals.mjs --task behavior-02
  node scripts/run-evals.mjs --tags trigger
  node scripts/run-evals.mjs --model gpt-5-mini --trials 2

Results are written to evals/results/latest.json and latest.junit.xml.`);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes("--help") || args.includes("-h")) {
    printHelp();
    return;
  }

  const tasks = await loadTasks();
  if (args.includes("--list")) {
    for (const task of tasks) console.log(`${task.id}\t${task.name}`);
    const behaviorCount = tasks.filter((task) =>
      task.tags.includes("behavior"),
    ).length;
    const triggerCount = tasks.length - behaviorCount;
    console.log(
      `\n${tasks.length} task(s): ${behaviorCount} behavior, ${triggerCount} trigger`,
    );
    return;
  }

  const temporaryDir = await mkdtemp(
    path.join(os.tmpdir(), "project-knowledge-generator-evals-"),
  );
  const resultsDir = path.join(evalsDir, "results");
  const resultFile = path.join(resultsDir, "latest.json");
  const junitFile = path.join(resultsDir, "latest.junit.xml");

  try {
    await writeSuite(temporaryDir, tasks);
    await mkdir(resultsDir, { recursive: true });
    await Promise.all([
      rm(resultFile, { force: true }),
      rm(junitFile, { force: true }),
    ]);
    const result = spawnSync(
      "waza",
      [
        "run",
        path.join(temporaryDir, "wazaEval.yaml"),
        "--context-dir",
        skillDir,
        "--output",
        resultFile,
        "--reporter",
        `junit:${junitFile}`,
        "--interpret",
        ...args,
      ],
      { cwd: skillDir, stdio: "inherit" },
    );

    if (result.error) throw result.error;
    process.exitCode = result.status ?? 1;
    console.log(
      `\nJSON: ${(await exists(resultFile)) ? resultFile : "not produced"}`,
    );
    console.log(
      `JUnit: ${(await exists(junitFile)) ? junitFile : "not produced"}`,
    );
  } finally {
    await rm(temporaryDir, { recursive: true, force: true });
  }
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
) {
  await main();
}
