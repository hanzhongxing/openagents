from openagents.agents.worker_agent import WorkerAgent

class RandomTestAgent(WorkerAgent):

    default_agent_id = "random_test"

    async def on_startup(self):
        await self.workspace().channel("general").post("Hello from Random Test Agent!")
    
if __name__ == "__main__":
    agent = RandomTestAgent()
    agent.start(network_id="ai-news-chatroom")
    agent.wait_for_stop()