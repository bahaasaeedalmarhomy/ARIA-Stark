from google.adk.agents import SequentialAgent

from agents.planner_agent import planner_agent

# executor_agent placeholder — will be added in Story 3.1
root_agent = SequentialAgent(
    name="aria_root",
    sub_agents=[planner_agent],  # executor_agent added in Story 3.1
)
