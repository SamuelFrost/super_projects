# Expected coding behavior

Use informative variable and function names. Do not omit important context just to make names shorter.
```

`enforce_git_commit_hooks_and_formatters.md`
```markdown
# Tool interaction guideline for git commit

 Never skip commit hooks without explicit approval. Ensure relevant formatters and linters run for modified files before a commit is made.
```

#### Complex example

`meaningful_pull_request_content_guidelines.md`
```markdown
# Pull request content guidelines

Adhere to project guidelines for pull requests. Start by referencing the project's pull request template if available. In general a pull request body should contain the following sections:

- Requirement/background that the pull request addresses.
- Description of the changes made in the pull request.
- Important technical choices, decisions, and remaining concerns.
- Tested behavior and results.

Writing guidelines:

- Use language consistent with product terminology and include code names when relevant. It is okay to reference one concept with multiple names-- use parenthesis around the alternate name(s). example: "... home page (ホームページ | `root_page`) ..."
- Avoid internal jargon and abbreviations.
- Avoid “Replay” or “foundation” language with no product meaning. (fluff)
- Group the body by reviewer concern (contract/API, read model, shared architecture, fixtures, UI wiring, regressions, tests) rather than by commit order.
- State each acceptance criterion in full. Do not refer to bare IDs or internal identifiers in the PR.
- When editing an existing PR, fetch the current body first and preserve hosted screenshots, attachment URLs, and required template headings.
- Treat commit lists, diagrams, full AC sets, multiple screenshots, and payload dumps as optional. Include only what helps this review; keep the richer detail to a local report.
- Avoid reference to local files or processes.

Title naming guidelines:

- Ensure the title clearly conveys the entirity of the pull request.