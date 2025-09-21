from metagpt.strategy.planner import *
from typing import Dict, Tuple

STRUCTURAL_CONTEXT = """
## User Request
{user_request}

{current_plan}

## Notebook State
{nb_state}
"""


PLAN_STATUS = """
## Finished Tasks
{finished_tasks}

## Current Task
{current_task}

## Next Tasks
{next_tasks}

## Task Guidance
Write code for the incomplete sections of 'Current Task'. And avoid duplicating code from 'Finished Tasks' and 'Finished Section of Current Task', such as repeated import of packages, reading data, etc.
Specifically, {guidance}
"""

def simplified_task(task):
    return {
        "task_id": task.task_id,
        "dependent_task_ids": task.dependent_task_ids,
        "instruction": task.instruction,
        "task_type": task.task_type,
    }


class ExplainerPlanner(Planner):

    max_tasks: int = 16

    async def update_plan(self, goal: str = "", max_tasks: int = 7, max_retries: int = 3, nb_state: str = ""):
        if goal:
            self.plan = Plan(goal=goal)

        plan_confirmed = False
        while not plan_confirmed:
            context = self._get_context(nb_state)
            rsp = await WritePlan().run(context, max_tasks=max_tasks)
            self.working_memory.add(Message(content=rsp, role="assistant", cause_by=WritePlan))

            # precheck plan before asking reviews
            is_plan_valid, error = precheck_update_plan_from_rsp(rsp, self.plan)
            if not is_plan_valid and max_retries > 0:
                error_msg = f"The generated plan is not valid with error: {error}, try regenerating, remember to generate either the whole plan or the single changed task only"
                logger.warning(error_msg)
                self.working_memory.add(Message(content=error_msg, role="assistant", cause_by=WritePlan))
                max_retries -= 1
                continue

            _, plan_confirmed = await self.ask_review(trigger=ReviewConst.TASK_REVIEW_TRIGGER)

        update_plan_from_rsp(rsp=rsp, current_plan=self.plan)

        self.working_memory.clear()


    def _get_context(self, nb_state: str = "") -> List[Message]:
        context = STRUCTURAL_CONTEXT.format(
            user_request=self.plan.goal,
            current_plan=self.get_useful_memories(),
            nb_state=nb_state
        )
        return [Message(content=context, role="user")]


    def _get_clean_tasks(self) -> Tuple[str, str, str]:
        cleaned_finished = []
        cleaned_current = "None"
        cleaned_next = []

        for task in self.plan.tasks:
            if task.task_id == self.plan.current_task_id:
                cleaned_current = json.dumps(simplified_task(task), indent=4, ensure_ascii=False)
            elif task.is_finished:
                cleaned_finished.append(simplified_task(task))
            else:
                cleaned_next.append(simplified_task(task))

        return (json.dumps(cleaned_finished, indent=4, ensure_ascii=False),
                cleaned_current,
                json.dumps(cleaned_next, indent=4, ensure_ascii=False))


    def get_plan_status(self, exclude: List[str] = None) -> str:
        # prepare components of a plan status
        finished_tasks, current_task, next_tasks = self._get_clean_tasks()

        task_type_name = self.current_task.task_type
        task_type = TaskType.get_type(task_type_name)
        guidance = task_type.guidance if task_type else ""

        # combine components in a prompt
        prompt = PLAN_STATUS.format(
            finished_tasks=finished_tasks,
            current_task=current_task,
            next_tasks=next_tasks,
            guidance=guidance,
        )
        return prompt
