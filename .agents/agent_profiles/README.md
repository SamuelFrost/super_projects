# Agent profiles

Agent profiles present in this directory are used as templates for individual users to customize the behavior of the agent to fit their specific needs while making it easy to share and reuse across users.

## How to use

Copy the profile you want to use from the `.agents/agent_profiles` directory to the workspace root directory and rename it to `agents.md`, then edit the file to your needs. For example, to start from the basic profile:

```bash
cp .agents/agent_profiles/default_super_projects_agent.md agents.md
```

For the meta-development workspace (outer repo on `meta-development/main`, nested `super_projects/` clone):

```bash
cp .agents/agent_profiles/meta_development_super_projects_agent.md agents.md
```

If you have an uncommitted profile currently in use in `agents.md`, move it to the `.local_only` directory first so you do not lose it:

```bash
cp agents.md .agents/agent_profiles/.local_only/descriptive_name_of_the_profile.md
```

- language preference note: after copying the profile, ask your AI agent to translate the profile to your preferred language for best results.

### Enable profile for your preferred AI tool
- **Cursor:** `AGENTS.md` in the project root is a symlink to `agents.md`. Cursor applies that file on its own. An `@agents.md` line inside `.cursor/rules/*.mdc` is not expanded, so do not keep a second copy of the profile there.
- **Claude Code:** `.claude/rules/agents.md` symlinks to root `agents.md` (already set up)
- **Gemini CLI:** auto-loads `agents.md` from the project root; optional override in `.gemini/settings.json`
- **VS Code:** set `"chat.useAgentsMdFile": true` in `.vscode/settings.json`

## If you have profiles that are not yet ready to share, you can keep them in the .agents/agent_profiles/.local_only
directory and they will not be included in the shared profiles. These are .gitignored.