"""
PROMPT> python -m src.plan.plan_file
"""
from datetime import datetime
from dataclasses import dataclass

@dataclass
class PlanFile:
    content: str

    @classmethod
    def create(cls, vague_plan_description: str) -> "PlanFile":
        run_date = datetime.now()
        pretty_date = run_date.strftime("%Y-%b-%d")
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
    plan = PlanFile.create("My plan is here!")
    print(plan.content)
