# Fix Records

A fix record answers: where did each necessary part of the fix become effective?

## Selection

1. Partition artifacts by independently necessary component: server code, client release, configuration, data correction, migration, or another effective unit.
2. Remove reverted, superseded, temporary, partial, pending, and process-only artifacts.
3. Within each component, select the most downstream authoritative record proving it became effective.
4. List one record per necessary component. Do not also list an upstream commit when the selected release or deployment already proves the same component became effective.
5. Keep separate records when multiple components are required, such as code plus configuration or release plus migration.

Merge requests, reviews, approvals, pipeline runs, draft branches, and merge-only commits are supporting evidence, not final effective records. Do not use a merge record as deployment proof or a deployment record as client-adoption proof.

## Format

First explain the functional change and any material user action in one short paragraph. Then use one bullet per selected component:

```markdown
- `<Record type and scope>`: [`<display identifier>`](<authoritative URL>) - <functional role>
```

The URL verifies the claim made by the record: a commit or submitted change links to the actual change; a release or build to its version page; a deployment to its deployment record; and a configuration, data, or migration record to the effective published result.

For Git, display the short SHA and link the full web commit URL. GitLab uses `/-/commit/<full-sha>`; GitHub uses `/commit/<full-sha>`. Derive an HTTPS repository base from an unambiguous remote; otherwise ask for the viewable URL.

## Missing record

If no final effective record or viewable authoritative URL is available, include it in the single bundled question. After explicit omission approval, write exactly:

`No effective fix record is available to cite.`

Never invent a record, identifier, or URL.
