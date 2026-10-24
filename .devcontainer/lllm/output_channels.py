"""Decide which agent events the CLI is allowed to print.

This filters presentation after ADK has already produced the events. It does
not change the agent, its tools, or the model request.
"""

import argparse
import json
from dataclasses import dataclass

from lllm.agent import app as adk_app

CHANNEL_NAMES = ("thinking", "answer", "tool_calls", "tool_results", "prompt")
DEFAULT_CHANNEL_VISIBILITY = {
    "thinking": True,
    "answer": True,
    "tool_calls": True,
    "tool_results": False,
    "prompt": False,
}
DEFAULT_SUB_AGENT_CHANNEL_VISIBILITY = {"prompt": True}
OUTPUT_CHANNELS_CONFIG_KEYS = {"defaults", "sub_agent_defaults", "agent_overrides"}


@dataclass
class AgentOutputVisibility:
    """Resolved output channel visibility for each agent name."""

    visibility_by_agent_name: dict[str, dict[str, bool]]

    @classmethod
    def from_parsed_config(
        cls, parsed_output_channels_config: dict[str, dict[str, bool]] | None
    ) -> "AgentOutputVisibility":
        if parsed_output_channels_config is None:
            return cls(
                visibility_by_agent_name=_resolve_output_channel_visibility_by_agent({})
            )
        return cls(visibility_by_agent_name=parsed_output_channels_config)

    @classmethod
    def from_arguments(cls, parsed_args: argparse.Namespace) -> "AgentOutputVisibility":
        return cls.from_parsed_config(parsed_args.outputChannels)

    def is_enabled(self, agent_name: str, channel_name: str) -> bool:
        agent_visibility = self.visibility_by_agent_name.get(agent_name)
        if agent_visibility is None:
            agent_visibility = DEFAULT_CHANNEL_VISIBILITY
        return agent_visibility[channel_name]


def collect_sub_agent_names(parent_agent) -> set[str]:
    sub_agent_names: set[str] = set()
    for child_agent in getattr(parent_agent, "sub_agents", None) or []:
        child_agent_name = getattr(child_agent, "name", None)
        if child_agent_name:
            sub_agent_names.add(child_agent_name)
        sub_agent_names.update(collect_sub_agent_names(child_agent))
    return sub_agent_names


def _parse_channel_boolean_overrides(
    raw_channel_overrides: object, section_name: str
) -> dict[str, bool]:
    if not isinstance(raw_channel_overrides, dict):
        raise argparse.ArgumentTypeError(f"{section_name} must be an object")
    channel_boolean_overrides: dict[str, bool] = {}
    for channel_name, is_enabled in raw_channel_overrides.items():
        if channel_name not in CHANNEL_NAMES:
            choices = ", ".join(CHANNEL_NAMES)
            raise argparse.ArgumentTypeError(
                f"unknown information {channel_name!r} in {section_name}; "
                f"choose from {choices}"
            )
        if not isinstance(is_enabled, bool):
            raise argparse.ArgumentTypeError(
                f"{section_name}.{channel_name} must be a boolean, not {is_enabled!r}"
            )
        channel_boolean_overrides[channel_name] = is_enabled
    return channel_boolean_overrides


def _resolve_output_channel_visibility_by_agent(
    output_channels_config: dict,
) -> dict[str, dict[str, bool]]:
    root_agent_name = adk_app.root_agent.name
    sub_agent_names = collect_sub_agent_names(adk_app.root_agent)
    known_agent_names = {root_agent_name, *sub_agent_names}
    default_channel_overrides = _parse_channel_boolean_overrides(
        output_channels_config.get("defaults") or {}, "defaults"
    )
    sub_agent_default_channel_overrides = _parse_channel_boolean_overrides(
        output_channels_config.get("sub_agent_defaults") or {}, "sub_agent_defaults"
    )
    raw_override_entries = output_channels_config.get("agent_overrides") or []
    if not isinstance(raw_override_entries, list):
        raise argparse.ArgumentTypeError("agent_overrides must be a list")
    parsed_agent_channel_overrides: list[tuple[list[str], dict[str, bool]]] = []
    for entry_index, raw_entry in enumerate(raw_override_entries):
        section_name = f"agent_overrides[{entry_index}]"
        if not isinstance(raw_entry, dict):
            raise argparse.ArgumentTypeError(f"{section_name} must be an object")
        target_agent_names = raw_entry.get("target_agents")
        if (
            not isinstance(target_agent_names, list)
            or not target_agent_names
            or not all(
                isinstance(agent_name, str) and agent_name
                for agent_name in target_agent_names
            )
        ):
            raise argparse.ArgumentTypeError(
                f"{section_name}.target_agents must be a non-empty list of agent names"
            )
        unknown_agent_names = [
            agent_name
            for agent_name in target_agent_names
            if agent_name not in known_agent_names
        ]
        if unknown_agent_names:
            known_choices = ", ".join(sorted(known_agent_names))
            raise argparse.ArgumentTypeError(
                f"unknown agent {unknown_agent_names[0]!r}; choose from {known_choices}"
            )
        entry_channel_boolean_overrides = {
            key: value for key, value in raw_entry.items() if key != "target_agents"
        }
        parsed_agent_channel_overrides.append(
            (
                target_agent_names,
                _parse_channel_boolean_overrides(
                    entry_channel_boolean_overrides, section_name
                ),
            )
        )
    visibility_by_agent_name: dict[str, dict[str, bool]] = {}
    for agent_name in (root_agent_name, *sorted(sub_agent_names)):
        agent_visibility = dict(DEFAULT_CHANNEL_VISIBILITY)
        if agent_name != root_agent_name:
            agent_visibility.update(DEFAULT_SUB_AGENT_CHANNEL_VISIBILITY)
        agent_visibility.update(default_channel_overrides)
        if agent_name != root_agent_name:
            agent_visibility.update(sub_agent_default_channel_overrides)
        for target_agent_names, entry_overrides in parsed_agent_channel_overrides:
            if agent_name in target_agent_names:
                agent_visibility.update(entry_overrides)
        visibility_by_agent_name[agent_name] = agent_visibility
    return visibility_by_agent_name


def parse_output_channels_argument(
    raw_output_channels_json: str,
) -> dict[str, dict[str, bool]]:
    try:
        output_channels_config = json.loads(raw_output_channels_json)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(
            f"--outputChannels is not JSON: {error.msg}"
        ) from error
    if not isinstance(output_channels_config, dict):
        raise argparse.ArgumentTypeError("--outputChannels must be a JSON object")
    unknown_config_keys = sorted(
        set(output_channels_config) - OUTPUT_CHANNELS_CONFIG_KEYS
    )
    if unknown_config_keys:
        raise argparse.ArgumentTypeError(
            f"unknown key {unknown_config_keys[0]!r}; choose from "
            "defaults, sub_agent_defaults, agent_overrides"
        )
    return _resolve_output_channel_visibility_by_agent(output_channels_config)
