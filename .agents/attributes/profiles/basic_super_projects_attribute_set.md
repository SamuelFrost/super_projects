# Profile composition — attribute set for the super projects basic agent (for reference, not necessarily exhaustive)

Use only the attributes listed below, in the listed section order. Write each attribute body as a bullet (or nested bullets for list-form domain context). Preserve wording from each attribute file; do not paraphrase. Do not include attributes that are not listed here.

## Strong rules (in order)

1. `code_style/avoid_unnecessary_complexity.md`
2. `code_style/use_informative_variable_and_function_names.md`
3. `tools/git/enforce_git_commit_hooks_and_formatters.md`
4. `tools/testing/run_faster_checks_before_heavier_ones.md`
5. `tools/pull_requests/run_tests_and_linters_for_changed_files.md`
6. `tools/git/do_not_ignore_push_hooks_without_approval.md`
7. `tools/testing/do_not_resolve_failing_tests_by_removing_or_modifying_them.md`
8. `tools/mise/install_tools_via_mise_or_document.md`
9. `tools/git/never_use_git_push_without_approval.md`
10. `tools/git/never_commit_development_artifacts.md`

## Guidelines (in order)

1. `tools/git/fetch_and_pull_before_branching.md`
2. `tools/git/use_clear_feature_branch_names.md`
3. `tools/git/split_commits_into_meaningful_chunks.md`
4. `code_style/prefer_existing_project_patterns.md`
5. `code_style/consider_refactoring_shared_behavior.md`
6. `code_style/keep_things_mostly_dry.md`
7. `behavior/avoid_destructive_operations_without_approval.md`
8. `behavior/avoid_modifying_external_services_without_approval.md`
9. `tools/mise/use_mise_to_execute_commands.md`
10. `communication/communicate_in_english_unless_convention_asks_otherwise.md`

## Tools / Browser and GUI (in order)

1. `tools/browser/use_devcontainer_chrome_devtools_mcp.md`
2. `tools/browser/avoid_installing_new_browser_binaries.md`

## Tools / Git And SSH (in order)

1. `tools/git/ssh_agent_in_devcontainer.md`
2. `tools/git/github_cli_auth_persistence.md`
3. `tools/git/recover_from_git_permission_denied.md`
4. `tools/mise/prefer_mise_shims_in_integrated_terminals.md`

## Tools / Devcontainer (in order)

1. `tools/devcontainer/assume_devcontainer_system_configuration.md`
2. `tools/devcontainer/prefer_dockerfile_or_mise_for_persistent_tools.md`

## Tools / Other available tools

1. `tools/available_tools/devcontainer_available_tools.md` — use as the full section body under `### Other available tools` (intro paragraph plus nested `####` subsections)
