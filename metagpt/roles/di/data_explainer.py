from __future__ import annotations

from pydantic import Field, model_validator

from metagpt.actions.di.execute_nb_code import ExecuteNbCode
from metagpt.actions.di.explain_and_write_analysis_code import ExplainAndWriteAnalysisCode
from metagpt.logs import logger
from metagpt.roles.di.data_interpreter import DataInterpreter
from metagpt.schema import Message
from metagpt.tools.tool_recommend import BM25ToolRecommender

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
    execute_code: ExecuteNbCode = Field(default_factory=ExecuteNbCode, exclude=True)

    @model_validator(mode="after")
    def set_plan_and_tool(self) -> "Interpreter":
        self._set_react_mode(react_mode=self.react_mode, max_react_loop=self.max_react_loop, auto_run=self.auto_run)
        self.use_plan = (
            self.react_mode == "plan_and_act"
        )  # create a flag for convenience, overwrite any passed-in value
        if self.tools and not self.tool_recommender:
            self.tool_recommender = BM25ToolRecommender(tools=self.tools)
        self.set_actions([ExplainAndWriteAnalysisCode])
        self._set_state(0)
        return self


    async def _act(self) -> Message:
        """Useful in 'react' mode. Return a Message conforming to Role._act interface."""
        code, _, _ = await self._write_and_exec_code()
        return Message(content=code, role="assistant", sent_from=self._setting, cause_by=ExplainAndWriteAnalysisCode)


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

        while not success and counter < max_retry:
            ### write code ###
            code, explanation, cause_by = await self._write_code(counter, plan_status, tool_info)

            self.working_memory.add(Message(content=explanation, role="assistant", cause_by=cause_by))
            self.working_memory.add(Message(content=code, role="assistant", cause_by=cause_by))

            ### execute code ###
            _, _ = await self.execute_code.run(explanation, language="markdown")
            result, success = await self.execute_code.run(code)
            print(result)

            self.working_memory.add(Message(content=result, role="user", cause_by=ExecuteNbCode))

            ### process execution result ###
            counter += 1

            # if not success and counter >= max_retry:
            #     logger.info("coding failed!")
            #     review, _ = await self.planner.ask_review(auto_run=False, trigger=ReviewConst.CODE_REVIEW_TRIGGER)
            #     if ReviewConst.CHANGE_WORDS[0] in review:
            #         counter = 0  # redo the task again with help of human suggestions

        return code, result, success

    async def run(self, with_message=None) -> Message | None:
        self.user_requirement = with_message
        await super().run(with_message)

    async def _write_code(
        self,
        counter: int,
        plan_status: str = "",
        tool_info: str = "",
    ):
        todo = self.rc.todo  # todo is ExplainAndWriteAnalysisCode
        logger.info(f"ready to {todo.name}")
        use_reflection = counter > 0 and self.use_reflection  # only use reflection after the first trial

        code, explanation = await todo.run(
            user_requirement=self.user_requirement,
            plan_status=plan_status,
            tool_info=tool_info,
            working_memory=self.working_memory.get(),
            use_reflection=use_reflection,
        )

        return code, explanation, todo


    async def _write_title(
        self,
        plan_contex: str = ""
    ):
        todo = self.rc.todo  # todo is ExplainAndWriteAnalysisCode
        logger.info(f"ready to write notebook title")

        title = await todo.write_title(
            plan_contex=plan_contex
        )

        return title