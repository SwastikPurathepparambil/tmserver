import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from crewai import Agent, Task, Crew


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_crew(
    tool_instances: Optional[Dict[str, Any]] = None,
    task_names: Optional[List[str]] = None,
) -> Crew:
    """
    Build a Crew from YAML configs, optionally injecting runtime-built tools and
    selecting a subset/order of tasks to run.

    - tool_instances: dict of {tool_name: tool_instance} to attach to agents
    - task_names: ordered list of task keys from tasks.yaml to run
                  (defaults to the 3-task pipeline)
    """
    src_dir = Path(__file__).resolve().parent
    config_dir = src_dir / "config"

    agents_cfg = _load_yaml(config_dir / "agents.yaml")["agents"]
    tasks_cfg = _load_yaml(config_dir / "tasks.yaml")["tasks"]

    tools = tool_instances or {}

    # ---- Agents ----
    agents: Dict[str, Agent] = {}
    for name, cfg in agents_cfg.items():
        # Only attach tools that were actually injected/built.
        agent_tools = [tools[t] for t in cfg.get("tools", []) if t in tools]
        agents[name] = Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg.get("backstory", ""),
            verbose=bool(cfg.get("verbose", False)),
            tools=agent_tools,
        )

    # ---- Tasks (create all first) ----
    all_tasks: Dict[str, Task] = {}
    for name, cfg in tasks_cfg.items():
        all_tasks[name] = Task(
            description=cfg["description"],
            expected_output=cfg["expected_output"],
            agent=agents[cfg["agent"]],
            async_execution=bool(cfg.get("async_execution", False)),
            output_file=cfg.get("output_file"),
        )

    # Wire contexts by task name
    for name, cfg in tasks_cfg.items():
        ctx_names = cfg.get("context", [])
        if ctx_names:
            all_tasks[name].context = [all_tasks[c] for c in ctx_names if c in all_tasks]

    # ---- Choose which tasks to run (order matters) ----
    order = task_names or ["research_task", "profile_task", "resume_strategy_task"]
    selected_tasks = [all_tasks[n] for n in order if n in all_tasks]

    return Crew(
        agents=list(agents.values()),
        tasks=selected_tasks,
        verbose=True,
    )
