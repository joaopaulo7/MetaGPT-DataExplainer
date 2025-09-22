from metagpt.strategy.planner import *
from typing import Dict, Tuple
from copy import deepcopy
import re

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


def _remove_ansi_colors(text):
    """
    Removes ANSI escape sequences (color codes) from a string.
    """
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def _clean_outputs(outputs):
    new_outputs = []
    for output in outputs:
        if output['output_type'] == "stream":
            if "WARNING:" in output['text']:
                continue
            new_outputs.append({
                'output_type': "stream",
                'text': output['text']})

        elif output['output_type'] == "display_data":
            new_outputs.append({
                'output_type': "display_data",
                'data': {'text/plain': "IMAGE"}})

        elif output['output_type'] == "error":
            new_outputs.append({
                'output_type': "error",
                'ename': output['ename'],
                'evalue': _remove_ansi_colors(output['evalue']),
                # only get the most important traceback
                'traceback': [_remove_ansi_colors(tb) for tb in output['traceback'][:3] + output['traceback'][-2:]]})
    return new_outputs


def _create_nb_cell(source: str, cell_type: str, outputs: list = None, duration: str = "00:00:00"):
    new_cell = {
        'cell_type': cell_type,
        'source': source.splitlines(keepends=True),
        'execution_time': duration
    }

    if outputs:
        new_cell['outputs'] = _clean_outputs(outputs)

    return new_cell



class ExplainerPlanner(Planner):

    max_tasks: int = 16
    max_nb_tokens: int = 28000
    nb_state: dict = {"cells": []}
    working_nb_state: dict = {"cells": []}

    def get_nb_state(self, long_term: bool = False) -> str:
        if long_term:
            return json.dumps(self.nb_state, indent=0, ensure_ascii=False)
        else:
            return json.dumps(self.working_nb_state, indent=0, ensure_ascii=False)

    def _truncate_nb(self, long_term: bool = False) -> None:
        if long_term:
            while len(self.get_nb_state(long_term)) > self.max_nb_tokens*4:
                self.nb_state['cells'].pop(0)
        else:
            while len(self.get_nb_state(long_term)) > self.max_nb_tokens*4:
                self.working_nb_state['cells'].pop(0)

    def add_to_nb(self, source: str,
                  cell_type: str,
                  outputs: list = None,
                  duration: str = "00:00:00",
                  long_term: bool = False) -> None:

        if long_term:
            self.nb_state['cells'].append(_create_nb_cell(source, cell_type, outputs, duration))
            self._truncate_nb(long_term)

            # when the long-term nb_state changes, updates the working state.
            self.working_nb_state = deepcopy(self.nb_state)
        else:
            self.working_nb_state['cells'].append(_create_nb_cell(source, cell_type, outputs, duration))
            self._truncate_nb(long_term)


    async def update_plan(self, goal: str = "", max_tasks: int = None, max_retries: int = 3):
        if not max_tasks:
            max_tasks = self.max_tasks
        if goal:
            self.plan = Plan(goal=goal)

        plan_confirmed = False
        while not plan_confirmed:
            context = self.get_context()
            context_msg = [Message(content=context, role="user")]
            rsp = await WritePlan().run(context_msg, max_tasks=max_tasks)
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


    def get_context(self) -> str:
        context = STRUCTURAL_CONTEXT.format(
            user_request=self.plan.goal,
            current_plan=self.get_plan_status(guidance=False),
            nb_state=self.get_nb_state()
        )
        return context


    def _get_clean_tasks(self) -> Tuple[str, str, str]:
        cleaned_finished = []
        cleaned_current = "None"
        cleaned_next = []

        for task in self.plan.tasks:
            if task.task_id == self.plan.current_task_id:
                cleaned_current = json.dumps(simplified_task(task), indent=0, ensure_ascii=False)
            elif task.is_finished:
                cleaned_finished.append(simplified_task(task))
            else:
                cleaned_next.append(simplified_task(task))

        return (json.dumps(cleaned_finished, indent=0, ensure_ascii=False),
                cleaned_current,
                json.dumps(cleaned_next, indent=0, ensure_ascii=False))


    def get_plan_status(self, exclude: List[str] = None, guidance: bool = True) -> str:
        # prepare components of the plan status
        finished_tasks, current_task, next_tasks = self._get_clean_tasks()

        if guidance:
            task_type_name = self.current_task.task_type
            task_type = TaskType.get_type(task_type_name)
            guidance = task_type.guidance if task_type else ""
        else:
            guidance = ""


        # combine components in a prompt
        prompt = PLAN_STATUS.format(
            finished_tasks=finished_tasks,
            current_task=current_task,
            next_tasks=next_tasks,
            guidance=guidance,
        )

        if guidance:
            return prompt
        else:
            return prompt.split("## Task Guidance")[0] # remove guidance tag if no guidance is needed
