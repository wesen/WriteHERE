from typing import Dict
from recursive.agent.registry import agent_register

# from recursive.utils.file_io import make_mappings

# ALL_SYSTEM_MESSAGE_MAPPINGS, ALL_PROMPT_MAPPINGS = make_mappings(__file__)


class AgentProxy:
    """
    config.action_mapping: key is action, value is a List, 1st value is agent class, 2nd value is agent prompt version
    """

    def __init__(self, config: Dict):
        self.config = config
        self.action_mapping = config["action_mapping"]
        self.agent_dict = {}

    def get_agent(self, agent_type):
        if agent_type not in self.agent_dict:
            agent_cls = agent_register.module_dict[agent_type]
            self.agent_dict[agent_type] = agent_cls(self.config)
        return self.agent_dict[agent_type]

    def proxy(self, action, *args, **kwargs):
        agent_cls, input_kwargs = self.action_mapping[action]
        kwargs.update(input_kwargs)
        agent = self.get_agent(agent_cls)
        return agent


if __name__ == "__main__":
    config = {
        "action_mapping": {
            "plan": ["DummyRandomPlanningAgent", {}],
            "update": ["DummyRandomUpdateAgent", {}],
            "execute": ["DummyRandomExecutorAgent", {}],
            "prior_reflect": ["DummyRandomPriorReflectionAgent", {}],
            "post_reflect": ["DummyRandomPostReflectionAgent", {}],
        }
    }
    agent_proxy = AgentProxy(config)
    agent = agent_proxy.proxy("plan")
    from pprint import pprint

    pprint(agent.parse_result(agent.forward(None, {}, {}, {}, {}, {})))
