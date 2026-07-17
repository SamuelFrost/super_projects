# Attributes for agents

These files are atomic attributes that can be used to encourage or discourage specific behaviors from the agent.

## How to use

### Method 1: Create an agent profile comprised of the attributes

Copy-paste or select desired lines and ask your AI tool to create a profile for you. For stronger adherence to the attributes, it may be better to directly write the attributes into the profile as opposed to referencing the file. On the other hand, if you frequently update the attributes, it may be easier to reference the file.

### Method 2: Modify configuration to include in context

Modify your AI tool's configuration to include the attributes in context.

### Method 3: Use the attributes directly in your prompts

Use the attributes directly in your prompts when relevant. This will give the strongest results and can be used in combination with the other methods.

## Creating attributes

### Writing guidelines

- Name the file based on the attribute's classification, such as rule, constraint, tool interaction guideline, behavior guideline, communication guideline, or domain context.
- Keep each attribute atomic: it should express one behavior, decision rule, or closely related set of actions.
- Include the conditions under which the attribute applies. Avoid absolute language such as “always” or “never” unless there are genuinely no exceptions.
- Prefer project-specific facts and concrete commands, paths, or examples over vague advice, but avoid details likely to become stale.
- Use precise language to avoid instructions that could be interpreted in multiple ways.

### Suggested attribute structure

```markdown
# <classification>

<description of the attribute>
```

#### Simple examples

`avoid_unnecessary_complexity.md`
```markdown
# Expected coding behavior

Avoid unnecessary complexity.
```

`use_informative_variable_and_function_names.md`
```markdown
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
```