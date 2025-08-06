"""
PROMPT> python -m planexe.plan.plan_file
"""
from datetime import datetime
from dataclasses import dataclass

@dataclass
class PlanFile:
    content: str

    @classmethod
    def create(cls, vague_plan_description: str, start_time: datetime) -> "PlanFile":
        pretty_date = start_time.strftime("%Y-%b-%d")
        plan_prompt = (
            f"Plan:\n{vague_plan_description}\n\n"
            f"Today's date:\n{pretty_date}\n\n"
            "Project start ASAP"
        )
        return cls(plan_prompt)

    def save(self, file_path: str) -> None:
        with open(file_path, "w") as f:
            f.write(self.content)

if __name__ == "__main__":
    start_time: datetime = datetime.now().astimezone()
    plan = PlanFile.create(vague_plan_description="My plan is here!", start_time=start_time)
    print(plan.content)
