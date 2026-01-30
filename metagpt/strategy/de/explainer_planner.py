import json
from typing import List

from toon_format import encode as toon_encode

from metagpt.strategy.planner import Planner
from metagpt.actions.di.ask_review import AskReview, ReviewConst
from metagpt.actions.de.write_plan import (
    WritePlan,
    precheck_update_plan_from_rsp,
    update_plan_from_rsp,
)
)
from metagpt.logs import logger
from metagpt.schema import Message, ExplainerPlan
from metagpt.strategy.de.task_type import TaskType

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
{guidance}
"""

STREAM_CAP = 4096

def simplified_task(task):
    return {
        "task_id": task.task_id,
        "instruction": task.instruction,
        "task_type": task.task_type,
        "dependent_task_ids": task.dependent_task_ids
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
            if "WARNING:" in output['text'] or "FutureWarning:" in output['text']:
                continue
            new_outputs.append({
                'output_type': "stream",
                'text': output['text'][:STREAM_CAP*4].splitlines(keepends=True)})

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
                'traceback': [tb for tb in output['traceback'][:3] + output['traceback'][-2:]]})
    return new_outputs


def _create_nb_cell(source: str, cell_type: str, outputs: list = None, duration: str = "00:00:00"):
    new_cell = {
        'cell_type': cell_type,
        'metadata': {'execution_time': duration},
        'source': source.splitlines(keepends=True)
    }

    if outputs:
        new_cell['outputs'] = _clean_outputs(outputs)

    return new_cell



class ExplainerPlanner(Planner):
    toon: bool = False
    max_tasks: int = 16
    max_context: int = 32000
    max_nb_tokens: int = 30000
    nb_state: dict = {"cells": []}
    working_nb_state: dict = {"cells": []}


    def reset_working_state(self):
        self.working_nb_state = deepcopy(self.nb_state)

    def get_nb_state(self, long_term: bool = False) -> str:
        nb_state = ""
        if self.toon:
            if long_term:
                nb_state = json.dumps(self.nb_state, indent=2, ensure_ascii=False)
            else:
                nb_state = json.dumps(self.working_nb_state, indent=2, ensure_ascii=False)
            
            return f"```ipynb\n{nb_state}\n```"
        else:
            if long_term:
                nb_state = toon_encode(self.nb_state)
            else:
                nb_state = toon_encode(self.working_nb_state)
            return f"```toon\n{nb_state}\n```"

    
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
            self.reset_working_state()
        else:
            self.working_nb_state['cells'].append(_create_nb_cell(source, cell_type, outputs, duration))
            self._truncate_nb(long_term)


    async def update_plan(self, goal: str = "", max_tasks: int = None, max_retries: int = 4, guidance: bool = False):
        if not max_tasks:
            max_tasks = self.max_tasks
        if goal:
            self.plan = ExplainerPlan(goal=goal)

        plan_confirmed = False
        while not plan_confirmed:
            context = self.get_context(guidance=guidance)
            context_msg = [Message(content=context, role="user")]
            rsp = await WritePlan().run(context_msg, max_tasks=max_tasks)
            self.working_memory.add(Message(content=rsp, role="assistant", cause_by=WritePlan))

            # precheck plan before asking reviews
            is_plan_valid, error = precheck_update_plan_from_rsp(rsp, self.plan)
            if not is_plan_valid and max_retries > 0:
                error_msg = f"The generated plan is not valid with error: {str(error)}, try regenerating. Make sure all dependent tasks exist."
                logger.warning(error_msg)
                self.working_memory.add(Message(content=error_msg, role="user", cause_by=WritePlan))
                max_retries -= 1
                continue

            _, plan_confirmed = await self.ask_review(trigger=ReviewConst.TASK_REVIEW_TRIGGER)

        if plan_confirmed:
            update_plan_from_rsp(rsp=rsp, current_plan=self.plan)
            
            # estimate context length and set max nb state context based on it (500 tokens as a 'safety margin')
            self.max_nb_tokens = self.max_context - len(self.get_context(guidance=False, nb_state=False))//4 - 500

        self.working_memory.clear()


    def get_context(self, guidance: bool = False, nb_state: bool = True) -> str:
        context = STRUCTURAL_CONTEXT.format(
            user_request = self.plan.goal,
            current_plan = self.get_plan_status(guidance=False),
            nb_state = self.get_nb_state() if nb_state else ""
        )
        return context


    def _get_clean_tasks(self) -> Tuple[str, str, str]:
        cleaned_finished = []
        cleaned_current = "None"
        cleaned_next = []

        for task in self.plan.tasks:
            if task.task_id == self.plan.current_task_id:
                cleaned_current = json.dumps(simplified_task(task), indent=1, ensure_ascii=False)
            elif task.is_finished:
                cleaned_finished.append(simplified_task(task))
            else:
                cleaned_next.append(simplified_task(task))

        return (json.dumps(cleaned_finished, indent=1, ensure_ascii=False),
                cleaned_current,
                json.dumps(cleaned_next, indent=1, ensure_ascii=False))


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
