#!/usr/bin/env python3
"""Run self-tests for prompt rendering, prompt delivery auditing, and reviewer JSON validation."""
from __future__ import annotations
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PROMPTS = ROOT / "prompts"
SCHEMAS = ROOT / "schemas"

class Tests:
    def __init__(self): self.passed = 0; self.failed = []
    def check(self, name, condition, details=""):
        if condition: self.passed += 1; print(f"PASS {name}")
        else: self.failed.append(name); print(f"FAIL {name} {details}")

def run(args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)

def write_json(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    t = Tests()
    with tempfile.TemporaryDirectory(prefix="mmcr-selftest-") as td:
        tmp = Path(td)
        rendered = {}
        values_paths = {}
        for role, filename in (("discovery", "discovery-reviewer.md"), ("verification", "verification-reviewer.md")):
            template = PROMPTS / filename
            text = template.read_text(encoding="utf-8")
            tokens = sorted(set(re.findall(r"\{\{([A-Z][A-Z0-9_]*)\}\}", text)))
            values = {key: f"Synthetic {key}\nSecond line\n\n- evidence item" for key in tokens}
            values["BASELINE_CHANGE_PACKAGE"] = "Base: synthetic-base\nDiff: + changed behavior\nCurrent source: synthetic.go"
            if role == "discovery": values["REVIEW_TARGET"] = "Synthetic target for Discovery"
            else: values["REVIEW_TARGET_AND_REQUIREMENTS"] = "Synthetic target and requirement"
            values["CANDIDATE_FINDINGS"] = "C-F-001: hypothetical finding at synthetic.go:10"
            values["CANDIDATE_RECOMMENDATIONS"] = "C-R-001: hypothetical alternative at synthetic.go:20"
            value_file = tmp / f"{role}.values.json"; write_json(value_file, values)
            output = tmp / f"{role}.rendered.txt"
            p = run([SCRIPTS / "render_prompt.py", "--template", template, "--values", value_file, "--output", output])
            t.check(f"{role}: template renders", p.returncode == 0, p.stderr)
            actual = output.read_text(encoding="utf-8") if output.exists() else ""
            rendered[role] = actual; values_paths[role] = value_file
            capture = tmp / f"{role}.capture.txt"; capture.write_text(actual, encoding="utf-8", newline="")
            p = run([SCRIPTS / "validate_prompt.py", "--role", role, "--template", template, "--values", value_file, "--actual-prompt", capture])
            t.check(f"{role}: exact prompt accepted", p.returncode == 0, p.stdout + p.stderr)
            flattened = tmp / f"{role}.flattened.txt"; flattened.write_text(" ".join(actual.split()), encoding="utf-8")
            p = run([SCRIPTS / "validate_prompt.py", "--role", role, "--template", template, "--values", value_file, "--actual-prompt", flattened])
            t.check(f"{role}: flattened prompt rejected", p.returncode != 0)
            truncated = tmp / f"{role}.truncated.txt"; truncated.write_text("\n".join(actual.splitlines()[:-5]) + "\n", encoding="utf-8")
            p = run([SCRIPTS / "validate_prompt.py", "--role", role, "--template", template, "--values", value_file, "--actual-prompt", truncated])
            t.check(f"{role}: truncated prompt rejected", p.returncode != 0)
            altered = tmp / f"{role}.altered.txt"; altered.write_text(actual.replace("## Task", "## Altered Task", 1), encoding="utf-8")
            p = run([SCRIPTS / "validate_prompt.py", "--role", role, "--template", template, "--values", value_file, "--actual-prompt", altered])
            t.check(f"{role}: changed instruction content rejected", p.returncode != 0)
            extra = tmp / f"{role}.extra.txt"; extra.write_text("Unrequested preamble\n\n" + actual, encoding="utf-8")
            p = run([SCRIPTS / "validate_prompt.py", "--role", role, "--template", template, "--values", value_file, "--actual-prompt", extra])
            t.check(f"{role}: unexpected preamble rejected", p.returncode != 0)
            wrong_template = PROMPTS / ("verification-reviewer.md" if role == "discovery" else "discovery-reviewer.md")
            p = run([SCRIPTS / "validate_prompt.py", "--role", role, "--template", wrong_template, "--values", value_file, "--actual-prompt", capture])
            t.check(f"{role}: wrong role/template rejected", p.returncode != 0)

        # Dispatch audit must tie each role to an actual captured prompt argument.
        dcap, vcap = tmp / "D1.prompt.txt", tmp / "V1.prompt.txt"
        dcap.write_text(rendered["discovery"], encoding="utf-8", newline="")
        vcap.write_text(rendered["verification"], encoding="utf-8", newline="")
        manifest = {
            "expected_discovery_reviewers": ["D1", "D2"],
            "verification_expected": True,
            "dispatches": [
                {"reviewer_id": "D1", "role": "discovery", "model_route": "model-a", "dispatch_id": "dispatch-a", "capture_method": "dispatch_argument_capture", "fresh_context_evidence": "new child context id A", "template_path": str(PROMPTS / "discovery-reviewer.md"), "values_path": str(values_paths["discovery"]), "prompt_argument_path": str(dcap)},
                {"reviewer_id": "D2", "role": "discovery", "model_route": "model-b", "dispatch_id": "dispatch-b", "capture_method": "exact_argument_variable", "fresh_context_evidence": "new child context id B", "template_path": str(PROMPTS / "discovery-reviewer.md"), "values_path": str(values_paths["discovery"]), "prompt_argument_path": str(dcap)},
                {"reviewer_id": "V1", "role": "verification", "model_route": "parent-model", "dispatch_id": "dispatch-v", "capture_method": "dispatch_argument_capture", "fresh_context_evidence": "new child context id V", "template_path": str(PROMPTS / "verification-reviewer.md"), "values_path": str(values_paths["verification"]), "prompt_argument_path": str(vcap)}
            ]
        }
        mf = tmp / "dispatch-manifest.json"; write_json(mf, manifest)
        p = run([SCRIPTS / "validate_dispatch_prompts.py", "--manifest", mf])
        t.check("dispatch audit validates each captured prompt", p.returncode == 0, p.stdout + p.stderr)
        broken = json.loads(mf.read_text()); broken["dispatches"][0]["prompt_argument_path"] = str(tmp / "discovery.flattened.txt")
        (tmp / "discovery.flattened.txt").write_text("one line prompt", encoding="utf-8"); write_json(mf, broken)
        p = run([SCRIPTS / "validate_dispatch_prompts.py", "--manifest", mf])
        t.check("dispatch audit rejects prompt mismatch", p.returncode != 0)
        missing_capture = json.loads(mf.read_text()); missing_capture["dispatches"][0]["capture_method"] = "unavailable"; write_json(mf, missing_capture)
        p = run([SCRIPTS / "validate_dispatch_prompts.py", "--manifest", mf])
        t.check("dispatch audit rejects absent prompt provenance", p.returncode != 0)

        # Discovery output: valid, then schema-invalid.
        discovery_result = {
            "schema_version": "2.1", "reviewer_id": "D1", "review_status": "complete", "summary": "One verified candidate.", "scope": "synthetic.go diff",
            "spec_compliance": [],
            "findings": [{"local_id": "F-01", "kind": "defect", "title": "Body read error is ignored", "category": "correctness", "location": "synthetic.go:10-12", "evidence": "The returned error is discarded.", "trigger": "Reader returns partial bytes and a non-nil error.", "impact": "Incomplete data continues through the success path.", "severity": "high", "introduction_status": "introduced", "confidence": "high"}],
            "recommendations": [], "checks": [{"check_id": "T-01", "kind": "test", "purpose": "Reproduce partial read", "command": "go test ./pkg -run TestPartialRead", "status": "passed", "exit_code": 0, "scope": "Reader returns partial data and error", "output_summary": "PASS", "artifacts": [], "side_effects": "Temporary test cache only"}], "checks_not_run": [], "limitations": []
        }
        dr = tmp / "discovery.json"; write_json(dr, discovery_result)
        p = run([SCRIPTS / "validate_review_output.py", "--role", "discovery", "--schema", SCHEMAS / "discovery-result.schema.json", "--input", dr])
        t.check("Discovery output passes schema and semantic validation", p.returncode == 0, p.stdout + p.stderr)
        invalid_d = json.loads(dr.read_text()); invalid_d["findings"][0]["severity"] = "urgent"; write_json(dr, invalid_d)
        p = run([SCRIPTS / "validate_review_output.py", "--role", "discovery", "--schema", SCHEMAS / "discovery-result.schema.json", "--input", dr])
        t.check("Discovery invalid enum rejected", p.returncode != 0)
        invalid_check = json.loads(dr.read_text()); invalid_check["findings"][0]["severity"] = "high"; invalid_check["checks"][0]["exit_code"] = 4; write_json(dr, invalid_check)
        p = run([SCRIPTS / "validate_review_output.py", "--role", "discovery", "--schema", SCHEMAS / "discovery-result.schema.json", "--input", dr])
        t.check("inconsistent passed check exit code rejected", p.returncode != 0)
        duplicate_key = tmp / "duplicate-key.json"; duplicate_key.write_text('{"schema_version":"2.1","schema_version":"2.1"}', encoding="utf-8")
        p = run([SCRIPTS / "validate_review_output.py", "--role", "discovery", "--schema", SCHEMAS / "discovery-result.schema.json", "--input", duplicate_key])
        t.check("duplicate JSON keys rejected", p.returncode != 0)
        nonstandard_json = tmp / "nonstandard.json"; nonstandard_json.write_text('{"value": NaN}', encoding="utf-8")
        p = run([SCRIPTS / "validate_review_output.py", "--role", "discovery", "--schema", SCHEMAS / "discovery-result.schema.json", "--input", nonstandard_json])
        t.check("non-standard JSON constants rejected", p.returncode != 0)

        # Verification output: candidate set must match exactly.
        verification_result = {"schema_version": "2.1", "review_status": "complete", "summary": "Candidate verified.",
            "finding_assessments": [{"candidate_id": "C-F-001", "verdict": "confirmed", "rationale": "The trigger is reachable and the effect follows.", "evidence": ["synthetic.go:10-12"]}],
            "recommendation_assessments": [{"candidate_id": "C-R-001", "verdict": "worthwhile", "rationale": "The alternative reduces duplicated parsing without changing semantics.", "evidence": ["synthetic.go:20-25"]}],
            "checks": [], "checks_not_run": [], "limitations": []}
        vr = tmp / "verification.json"; write_json(vr, verification_result)
        expected = tmp / "expected-candidates.json"; write_json(expected, {"findings": ["C-F-001"], "recommendations": ["C-R-001"]})
        args = [SCRIPTS / "validate_review_output.py", "--role", "verification", "--schema", SCHEMAS / "verification-result.schema.json", "--input", vr, "--expected-candidates", expected]
        p = run(args); t.check("Verification output has exact candidate coverage", p.returncode == 0, p.stdout + p.stderr)
        write_json(expected, {"findings": ["C-F-001", "C-F-002"], "recommendations": ["C-R-001"]})
        p = run(args); t.check("missing candidate assessment rejected", p.returncode != 0)
        write_json(expected, {"findings": ["C-F-001"], "recommendations": ["C-R-001"]})
        invalid_unexpected = json.loads(vr.read_text()); invalid_unexpected["finding_assessments"][0]["candidate_id"] = "C-F-999"; write_json(vr, invalid_unexpected)
        p = run(args); t.check("unexpected candidate assessment rejected", p.returncode != 0)
        invalid_v = json.loads(vr.read_text()); invalid_v["finding_assessments"][0]["candidate_id"] = "C-F-001"; invalid_v["finding_assessments"].append(invalid_v["finding_assessments"][0]); write_json(vr, invalid_v)
        p = run(args); t.check("duplicate candidate assessment rejected", p.returncode != 0)

    print(f"\n{t.passed} passed; {len(t.failed)} failed")
    return 0 if not t.failed else 1

if __name__ == "__main__":
    raise SystemExit(main())
