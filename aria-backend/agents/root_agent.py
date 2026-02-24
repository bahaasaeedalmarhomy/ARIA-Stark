from google.adk.agents import SequentialAgent

# Stub: agents will be added in Stories 2.1 and 3.1
root_agent = SequentialAgent(
    name="aria_root",
    sub_agents=[],  # planner_agent + executor_agent added in future stories
)
