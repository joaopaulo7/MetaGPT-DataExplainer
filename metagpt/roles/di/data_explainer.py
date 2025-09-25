from __future__ import annotations

import json
from typing import Literal, Tuple

from pydantic import Field, model_validator

from metagpt.actions import Action
from metagpt.actions.di.execute_nb_code import ExecuteNbCode
from metagpt.actions.di.explain_and_write_analysis_code import ExplainAndWriteAnalysisCode
from metagpt.logs import logger
from metagpt.roles.di.data_interpreter import DataInterpreter
from metagpt.roles.role import RoleReactMode
from metagpt.schema import Message, Task, TaskResult
from metagpt.tools.tool_recommend import BM25ToolRecommender
from metagpt.strategy.explainer_planner import ExplainerPlanner, _clean_outputs

from time import sleep, gmtime, time, strftime

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
    max_tasks: int = 12
    max_nb_tokens: int = 28000
    execute_code: ExecuteNbCode = Field(default_factory=ExecuteNbCode, exclude=True)

    @model_validator(mode="after")
    def set_plan_and_tool(self) -> "Explainer":
        self.planner = ExplainerPlanner(max_tasks=self.max_tasks, max_nb_tokens=self.max_nb_tokens)
        self._set_react_mode(react_mode=self.react_mode, max_react_loop=self.max_react_loop, auto_run=self.auto_run)
        self.use_plan = (
            self.react_mode == "plan_and_act"
        )  # create a flag for convenience, overwrite any passed-in value
        if self.tools and not self.tool_recommender:
            self.tool_recommender = BM25ToolRecommender(tools=self.tools)
        self.set_actions([ExplainAndWriteAnalysisCode])
        self._set_state(0)
        return self


    async def _act_on_task(self, current_task: Task) -> TaskResult:
        """Useful in 'plan_and_act' mode. Wrap the output in a TaskResult for review and confirmation."""
        is_success = False
        if current_task.task_type == "plan re-evaluation":
            try:
                await self.planner.update_plan(self.goal, guidance=True)
                is_success = True
            except Exception:
                pass
            task_result = TaskResult(code="", result="", is_success=is_success)
        else:
            code, result, is_success = await self._write_and_exec_code()
            task_result = TaskResult(code=code, result=result, is_success=is_success)
        return task_result


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

    async def _write_and_exec_code(self, max_retry: int = 4):
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

        # data info (may cause problems in larger datasets)
        #await self._check_data()

        # if notebook is empty, write a title cell
        if not self.execute_code.nb.cells:
            title = await self._write_title()
            _, _, duration = await self._run_code(title, language="markdown")
            self.planner.add_to_nb(source=title, cell_type="markdown", long_term=True)

        ### write and run explanation ###
        markdown = await self._write_markdown()
        _, _, duration = await self._run_code(markdown, language="markdown")
        self.planner.add_to_nb(source=markdown, cell_type="markdown")


        counter = 0
        success = False
        while not success and counter < max_retry:
            ### write and run code ###
            code, cause_by = await self._write_code(counter, tool_info)
            outputs, success, duration = await self._run_code(code)
            self.planner.add_to_nb(source=code, cell_type="code", outputs=outputs, duration=duration)
            print(json.dumps(_clean_outputs(outputs), ensure_ascii=False, indent=4))

            if not success:
                self.working_memory.add(Message(
                    content="There was an error during the execution of the last cell. Please correct it.",
                    role="user", cause_by=ExecuteNbCode))
            
            counter += 1

            # if not success and counter >= max_retry:
            #     logger.info("coding failed!")
            #     review, _ = await self.planner.ask_review(auto_run=False, trigger=ReviewConst.CODE_REVIEW_TRIGGER)
            #     if ReviewConst.CHANGE_WORDS[0] in review:
            #         counter = 0  # redo the task again with help of human suggestions


        # only adds successes to the long-term nb state.
        if success:
            self.planner.add_to_nb(source=markdown, cell_type="markdown", long_term=True)
            self.planner.add_to_nb(source=code, cell_type="code", outputs=outputs,
                                   duration=duration, long_term=True)
            self.working_memory.clear()

        return code, json.dumps(outputs), success


    async def run(self, with_message=None) -> Message | None:
        self.user_requirement = with_message
        await super().run(with_message)


    async def _write_markdown(self) -> str:
        todo = self.rc.todo  # todo is ExplainAndWriteAnalysisCode
        logger.info(f"ready to {todo.name}")

        markdown = await todo.write_markdown(
            user_requirement=self.user_requirement,
            plan_status=self.planner.get_plan_status(),
            working_memory=self.working_memory.get(),
            nb_state=self.planner.get_nb_state()
        )

        return markdown

    async def _write_code(
            self,
            counter: int,
            plan_status = None,
            tool_info: str = "") -> tuple[str, Action]:

        todo = self.rc.todo  # todo is ExplainAndWriteAnalysisCode
        logger.info(f"ready to {todo.name}")
        use_reflection = counter > 0 and self.use_reflection  # only use reflection after the first trial

        code = await todo.write_code(
            user_requirement=self.user_requirement,
            plan_status=self.planner.get_plan_status(),
            tool_info=tool_info,
            working_memory=self.working_memory.get(),
            use_reflection=use_reflection,
            nb_state=self.planner.get_nb_state()
        )

        return code, todo


    async def _write_title(self) -> str:
        todo = self.rc.todo  # todo is ExplainAndWriteAnalysisCode
        logger.info(f"ready to write notebook title")

        title = await todo.write_title(
            plan_contex=self.planner.get_context()
        )

        return title


    async def _run_code(self,
                        code: str,
                        language: Literal["markdown", "python"] = "python"
                        ) -> Tuple[list, bool, str]:
        start_time = time()
        outputs, success = await self.execute_code.run(code, language=language)
        return outputs, success, strftime("%H:%M:%S", gmtime(time() - start_time))