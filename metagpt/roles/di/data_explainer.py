from __future__ import annotations

import json

from pydantic import Field, model_validator

from metagpt.actions import Action
from metagpt.actions.di.execute_nb_code import ExecuteNbCode
from metagpt.actions.di.explain_and_write_analysis_code import ExplainAndWriteAnalysisCode
from metagpt.logs import logger
from metagpt.roles.di.data_interpreter import DataInterpreter
from metagpt.roles.role import RoleReactMode
from metagpt.schema import Message
from metagpt.tools.tool_recommend import BM25ToolRecommender
from metagpt.strategy.explainer_planner import ExplainerPlanner

from time import sleep

REACT_THINK_PROMPT = """
# User Requirement
{user_requirement}
# Context
{context}

Output a json following the format:
```json
{{
    "thoughts": str = "Thoughts on current situation, reflect on how you should proceed to fulfill the user requirement",
    "state": bool = "Decide whether you need to take more actions to complete the user requirement. Return true if you think so. Return false if you think the requirement has been completely fulfilled."
}}
```
"""


class DataExplainer(DataInterpreter):
    name: str = "Edward"
    profile: str = "DataExplainer"
    nb_state: dict = {"cells": []}
    max_tasks: int = 16
    max_nb_tokens: int = 28000
    execute_code: ExecuteNbCode = Field(default_factory=ExecuteNbCode, exclude=True)

    @model_validator(mode="after")
    def set_plan_and_tool(self) -> "Explainer":
        self.planner = ExplainerPlanner(max_tasks=self.max_tasks)
        self._set_react_mode(react_mode=self.react_mode, max_react_loop=self.max_react_loop, auto_run=self.auto_run)
        self.use_plan = (
            self.react_mode == "plan_and_act"
        )  # create a flag for convenience, overwrite any passed-in value
        if self.tools and not self.tool_recommender:
            self.tool_recommender = BM25ToolRecommender(tools=self.tools)
        self.set_actions([ExplainAndWriteAnalysisCode])
        self._set_state(0)
        return self

    def _set_react_mode(self, react_mode: str, max_react_loop: int = 1, auto_run: bool = True):
        assert react_mode in RoleReactMode.values(), f"react_mode must be one of {RoleReactMode.values()}"
        self.rc.react_mode = react_mode
        if react_mode == RoleReactMode.REACT:
            self.rc.max_react_loop = max_react_loop
        elif react_mode == RoleReactMode.PLAN_AND_ACT:
            self.planner = ExplainerPlanner(goal=self.goal, max_tasks=self.max_tasks, working_memory=self.rc.working_memory, auto_run=auto_run)

    async def _act(self) -> Message:
        """Useful in 'react' mode. Return a Message conforming to Role._act interface."""
        code, _, _ = await self._write_and_exec_code()
        return Message(content=code, role="assistant", sent_from=self._setting, cause_by=ExplainAndWriteAnalysisCode)


    def _get_nb_state(self):
        return json.dumps(self.nb_state, ensure_ascii=False)

    def _truncate_nb(self):
        while len(self._get_nb_state()) > self.max_nb_tokens*4:
            self.nb_state['cells'].pop(0)

    def _clean_outputs(self, outputs):
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
                    'evalue': output['evalue'],
                    'traceback': output['traceback'][:3] + output['traceback'][
                        -2:]})  # only get the most important part
        return new_outputs

    def _create_nb_cell(self, source: str, cell_type: str, outputs: list = None):
        new_cell = {
            'cell_type': cell_type,
            'source': source.splitlines(keepends=True)
        }

        if outputs:
            new_cell['outputs'] = self._clean_outputs(outputs)

        return new_cell

    def _add_to_nb(self, source: str, cell_type: str, outputs: list = None):
        self.nb_state['cells'].append(self._create_nb_cell(source, cell_type, outputs))
        self._truncate_nb()

    async def _write_and_exec_code(self, max_retry: int = 3):
        counter = 0
        success = False

        # plan info
        plan_status = self.planner.get_plan_status() if self.use_plan else ""

        # tool info
        if self.tool_recommender:
            context = (
                self.working_memory.get()[-1].content if self.working_memory.get() else ""
            )  # thoughts from _think stage in 'react' mode
            plan = self.planner.plan if self.use_plan else None
            tool_info = await self.tool_recommender.get_recommended_tool_info(context=context, plan=plan)
        else:
            tool_info = ""

        # data info
        await self._check_data()

        # if notebook is empty, write a title cell
        if not self.execute_code.nb.cells:
            title = await self._write_title(self.planner.get_useful_memories()[0].content) # get only current plan context
            _, _ = await self.execute_code.run(title, language="markdown")
            self._add_to_nb(source=title, cell_type="markdown")

        while not success and counter < max_retry:
            ### write and run explanation ###
            markdown = await self._write_markdown(plan_status)
            _, _ = await self.execute_code.run(markdown, language="markdown")
            self._add_to_nb(source=markdown, cell_type="markdown")

            ### write and run code ###
            code, cause_by = await self._write_code(counter, plan_status, tool_info)
            outputs, success = await self.execute_code.run(code)
            self._add_to_nb(source=code, cell_type="code", outputs=outputs)
            print(json.dumps(self._clean_outputs(outputs), ensure_ascii=False, indent=4))

            if not success:
                self.working_memory.add(Message(
                    content="There was an error during the execution. Please correct it.",
                    role="user", cause_by=ExecuteNbCode))
            
            counter += 1
            sleep(2)

            # if not success and counter >= max_retry:
            #     logger.info("coding failed!")
            #     review, _ = await self.planner.ask_review(auto_run=False, trigger=ReviewConst.CODE_REVIEW_TRIGGER)
            #     if ReviewConst.CHANGE_WORDS[0] in review:
            #         counter = 0  # redo the task again with help of human suggestions

        self.working_memory.clear()

        return code, json.dumps(outputs), success

    async def run(self, with_message=None) -> Message | None:
        self.user_requirement = with_message
        await super().run(with_message)


    async def _write_markdown(
        self,
        plan_status: str = "",
    ) -> str:
        todo = self.rc.todo  # todo is ExplainAndWriteAnalysisCode
        logger.info(f"ready to {todo.name}")

        markdown = await todo.write_markdown(
            user_requirement=self.user_requirement,
            plan_status=plan_status,
            working_memory=self.working_memory.get(),
            nb_state=self._get_nb_state()
        )

        return markdown

    async def _write_code(
        self,
        counter: int,
        plan_status: str = "",
        tool_info: str = "",
    ) -> tuple[str, Action]:
        todo = self.rc.todo  # todo is ExplainAndWriteAnalysisCode
        logger.info(f"ready to {todo.name}")
        use_reflection = counter > 0 and self.use_reflection  # only use reflection after the first trial

        code = await todo.write_code(
            user_requirement=self.user_requirement,
            plan_status=plan_status,
            tool_info=tool_info,
            working_memory=self.working_memory.get(),
            use_reflection=use_reflection,
            nb_state=self._get_nb_state()
        )

        return code, todo


    async def _write_title(
        self,
        plan_contex: str = ""
    ) -> str:
        todo = self.rc.todo  # todo is ExplainAndWriteAnalysisCode
        logger.info(f"ready to write notebook title")

        title = await todo.write_title(
            plan_contex=plan_contex
        )

        return title
