# Attribute index

This index lists the available agent attributes by category. Link text uses each attribute’s classification header.

## Behavior

- [Constraint — avoid destructive operations without approval](behavior/avoid_destructive_operations_without_approval.md)
- [Constraint — avoid modifying external services without approval](behavior/avoid_modifying_external_services_without_approval.md)

## Code style

- [Coding behavior guideline — avoid unnecessary complexity](code_style/avoid_unnecessary_complexity.md)
- [Coding behavior guideline — refactor shared behavior before duplicating](code_style/consider_refactoring_shared_behavior.md)
- [Coding behavior guideline — keep things mostly DRY](code_style/keep_things_mostly_dry.md)
- [Coding behavior guideline — prefer existing project patterns](code_style/prefer_existing_project_patterns.md)
- [Coding behavior guideline — use informative variable and function names](code_style/use_informative_variable_and_function_names.md)

## Communication

- [Communication guideline — prefer English unless convention asks otherwise](communication/communicate_in_english_unless_convention_asks_otherwise.md)

## Documentation

- [Documentation preference — create directory information files often](documentation/create_directory_information_files_often.md)

## Profiles

- [Profile composition — attribute set for the super projects basic agent](profiles/basic_super_projects_attribute_set.md)
- [Profile composition — structure for the super projects basic agent](profiles/basic_super_projects_profile_structure.md)

## Tools

### Available tools

- [Domain context — how the devcontainer installs and configures tools](tools/available_tools/devcontainer_configuration_explanation.md)
- [Domain context — base terminal and system tools](tools/available_tools/base_terminal_and_system_tools.md)
- [Domain context — build dependencies for mise-managed runtimes](tools/available_tools/build_dependencies_for_mise_managed_runtimes.md)
- [Domain context — CLIs and package managers](tools/available_tools/clis_and_package_managers.md)
- [Domain context — mise-managed workspace runtimes](tools/available_tools/mise_managed_workspace_runtimes.md)
- [Domain context — browser, GUI, and VNC stack](tools/available_tools/browser_gui_and_vnc_stack.md)

### Browser

- [Tool interaction guideline — avoid installing new browser binaries](tools/browser/avoid_installing_new_browser_binaries.md)
- [Tool interaction guideline — use the devcontainer Chrome DevTools MCP](tools/browser/use_devcontainer_chrome_devtools_mcp.md)

### Devcontainer

- [Domain context — assume the configured devcontainer environment](tools/devcontainer/assume_devcontainer_system_configuration.md)
- [Tool installation guideline — prefer Dockerfile or mise for persistent tools](tools/devcontainer/prefer_dockerfile_or_mise_for_persistent_tools.md)

### Git

- [Constraint — do not ignore push hooks without approval](tools/git/do_not_ignore_push_hooks_without_approval.md)
- [Tool interaction guideline — enforce git commit hooks and formatters](tools/git/enforce_git_commit_hooks_and_formatters.md)
- [Git workflow guideline — fetch and pull before branching](tools/git/fetch_and_pull_before_branching.md)
- [Domain context — GitHub CLI auth persistence](tools/git/github_cli_auth_persistence.md)
- [Constraint — never commit development artifacts](tools/git/never_commit_development_artifacts.md)
- [Constraint — never use git push without approval](tools/git/never_use_git_push_without_approval.md)
- [Tool interaction guideline — recover from Git permission denied](tools/git/recover_from_git_permission_denied.md)
- [Git workflow guideline — split commits into meaningful chunks](tools/git/split_commits_into_meaningful_chunks.md)
- [Domain context — SSH agent in the devcontainer](tools/git/ssh_agent_in_devcontainer.md)
- [Git workflow guideline — use clear feature branch names](tools/git/use_clear_feature_branch_names.md)

### Mise

- [Tool installation guideline — install via mise or document the requirement](tools/mise/install_tools_via_mise_or_document.md)
- [Tool interaction guideline — prefer mise shims in integrated terminals](tools/mise/prefer_mise_shims_in_integrated_terminals.md)
- [Tool interaction guideline — use mise to execute commands](tools/mise/use_mise_to_execute_commands.md)

### Pull requests

- [Pull request content guidelines — write meaningful PR titles and bodies](tools/pull_requests/meaningful_pull_request_content_guidelines.md)
- [Tool interaction guideline — run tests and linters for changed PR files](tools/pull_requests/run_tests_and_linters_for_changed_files.md)

### Testing

- [Constraint — do not resolve failing tests by removing or modifying them](tools/testing/do_not_resolve_failing_tests_by_removing_or_modifying_them.md)
- [Testing behavior guideline — run faster checks before heavier ones](tools/testing/run_faster_checks_before_heavier_ones.md)
