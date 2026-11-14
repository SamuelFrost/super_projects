# AI privacy defaults

The image disables documented optional local reporting. These settings are **not
proof that provider-side training is disabled**. Complete the account settings
below before sending project data to cloud tools.

| Tool | Container default | Account setting still required |
| --- | --- | --- |
| Codex CLI / IDE integration | `/etc/codex/config.toml`: analytics and feedback off, OpenTelemetry exports off | ChatGPT **Settings → Data controls → Improve the model for everyone: off**. Separately turn **Include environments** off in Codex settings. |
| ChatGPT desktop / web | Uses the signed-in account's controls | Same ChatGPT and Codex controls above; local Codex configuration does not control ordinary ChatGPT chats. Review separate voice sharing controls if using voice. |
| Claude Code | Nonessential traffic and session quality surveys disabled through image environment variables | Claude **Settings → Privacy → Help improve Claude: off** for consumer accounts. This also covers Claude Code on those accounts. |
| Claude Desktop / web | Uses the signed-in account's controls | Same Claude privacy setting; Claude Code environment variables do not configure Claude Desktop. |
| Gemini CLI | System settings disable usage statistics, telemetry, traces, and prompt logging; telemetry environment variables also off | Authentication determines data terms. Use a paid Developer API service or Vertex AI with appropriate no-training terms; unpaid API terms may permit improvement use. Gemini web activity settings do not configure CLI/API data use. |
| Gemini web | Uses the signed-in account's controls | Turn **Keep Activity** off in Gemini Apps Activity. This also changes web chat history behavior. |
| Cursor IDE / Agent CLI | Desktop launchers disable telemetry and crash reporting; devcontainer IDE telemetry defaults to off | Enable **Privacy Mode** in Cursor Settings → General; verify it for the signed-in account used by Agent CLI. Team admins can enforce it in the dashboard. |
| VS Code / GitHub Copilot | `/etc/vscode/policy.json` sets `TelemetryLevel=off` and `EnableFeedback=false`; desktop launchers also disable telemetry and crash reporting | In [GitHub Copilot settings](https://github.com/settings/copilot), set **Allow GitHub to use my data for AI model training → Disabled** for individual plans. Organization-managed plans use their policies. Third-party extensions can have separate reporting and training controls; Codex uses the OpenAI controls above. |
| lllm CLI / browser agent / web | Local Ollama inference; the supplied Ollama service has `OLLAMA_NO_CLOUD=1`. OpenTelemetry SDK disabled in the devcontainer | No provider account is needed for local inference. Browser/MCP tools still contact the sites/services you ask them to use. Custom remote models/exporters have their own policies. |

Do not submit feedback containing project information: provider feedback paths can
permit review or improvement use even after ordinary training opt-out. Security,
abuse prevention, and processing needed to provide a service may still occur.
Local history persistence is independent of provider training consent.

The controls live in the image, outside state volumes, so rebuilds update them
without replacing persisted profiles. Gemini system settings override user/project
settings. VS Code machine policy disables core telemetry and feedback even with
an existing persisted profile; extensions may have independent controls. Codex
system settings are defaults: explicit user, profile, project, or CLI overrides
can supersede them. The image environment applies to both GUI and
terminal processes; existing processes need a container recreation. These are
reporting defaults; they do not isolate network access.

## Official references

- [Codex configuration precedence](https://learn.chatgpt.com/docs/config-file/config-basic)
  and [analytics / telemetry](https://learn.chatgpt.com/docs/config-file/config-advanced).
- [ChatGPT data controls, including Codex's separate environment setting](https://help.openai.com/en/articles/7730893-data-controls-in-chatgpt).
- [Claude Code data usage and reporting controls](https://code.claude.com/docs/en/data-usage).
- [Gemini CLI system configuration](https://geminicli.com/docs/reference/configuration/)
  and [authentication-specific terms](https://geminicli.com/docs/resources/tos-privacy/).
- [Gemini Apps activity controls](https://support.google.com/gemini/answer/13278892)
  and [privacy hub](https://support.google.com/gemini/answer/13594961).
- [Cursor Privacy Mode](https://cursor.com/help/security-and-privacy/privacy).
- [Ollama local-only mode](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features).
- [VS Code Linux packages](https://code.visualstudio.com/docs/setup/linux), [telemetry](https://code.visualstudio.com/docs/configure/telemetry), and [Linux policy configuration](https://code.visualstudio.com/docs/enterprise/policies#linux-json-policies).
- [GitHub Copilot model training controls](https://docs.github.com/en/copilot/how-tos/manage-your-account/manage-policies#model-training-and-improvements).
