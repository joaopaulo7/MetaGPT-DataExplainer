from metagpt.strategy.planner import *
from typing import Dict

PLAN_STATUS = """
## Current Task
{current_task}

## Task Guidance
Write code for the incomplete sections of 'Current Task'. And avoid duplicating code from 'Finished Tasks' and 'Finished Section of Current Task', such as repeated import of packages, reading data, etc.
Specifically, {guidance}
"""

TASK_FORMAT= """
{task_id}. **{instruction}**
    * type: {task_type}
    * success: {is_success}
"""

class ExplainerPlanner(Planner):

    max_tasks: int = 16

    async def update_plan(self, goal: str = "", max_tasks: int = None, max_retries: int = 3):
        if max_tasks is None:
            max_tasks = self.max_tasks
        await super().update_plan(goal=goal, max_tasks=max_tasks, max_retries=max_retries)

    def _get_clean_tasks(self) -> (str, str, str):
        cleaned_finished = []
        cleaned_current = "None"
        cleaned_next = []

        for task in self.plan.tasks:
            if task.task_id == self.plan.current_task_id:
                cleaned_current = TASK_FORMAT.format(**task.model_dump())
            elif task.is_finished:
                cleaned_finished.append(TASK_FORMAT.format(**task.model_dump()))
            else:
                cleaned_next.append(TASK_FORMAT.format(**task.model_dump()))

        return "\n".join(cleaned_finished), cleaned_current, "\n".join(cleaned_next),


    def get_plan_status(self, exclude: List[str] = None) -> str:
        # prepare components of a plan status
        finished_tasks, current_task, next_tasks = self._get_clean_tasks()

        task_type_name = self.current_task.task_type
        task_type = TaskType.get_type(task_type_name)
        guidance = task_type.guidance if task_type else ""

        # combine components in a prompt
        prompt = PLAN_STATUS.format(
            current_task=current_task,
            guidance=guidance,
        )
        return prompt
