# -*- encoding: utf-8 -*-
"""
@Date    :   2025/04/09 15:42:27
@Author  :   joaopaulo7
@File    :   explain_and_write_analysis_code.py
"""
from __future__ import annotations

from typing import Any, Coroutine

from metagpt.actions.di.write_analysis_code import WriteAnalysisCode
from metagpt.prompts.di.explain_and_write_analysis_code import (
    DEBUG_REFLECTION_EXAMPLE,
    EXPLAINER_EXPLANATION_SYSTEM_MSG,
    EXPLAINER_CODE_SYSTEM_MSG,
    REFLECTION_PROMPT,
    REFLECTION_SYSTEM_MSG,
    CODE_STRUCTUAL_PROMPT,
    EXPLANATION_STRUCTUAL_PROMPT,
)
from metagpt.schema import Message
from metagpt.utils.common import CodeParser


class ExplainAndWriteAnalysisCode(WriteAnalysisCode):
    async def _debug_with_reflection(self, context: list[Message], working_memory: list[Message]):
        reflection_prompt = REFLECTION_PROMPT.format(
            debug_example=DEBUG_REFLECTION_EXAMPLE,
            context=context,
            previous_impl=working_memory,
        )

        rsp = await self._aask(reflection_prompt, system_msgs=[REFLECTION_SYSTEM_MSG])
        # reflection = json.loads(CodeParser.parse_code(block=None, text=rsp))
        # return reflection["improved_impl"]
        reflection = CodeParser.parse_code(block=None, text=rsp)
        return reflection

    async def run(
        self,
        user_requirement: str,
        plan_status: str = "",
        tool_info: str = "",
        working_memory: list[Message] = None,
        use_reflection: bool = False,
        memory: list[Message] = None,
        **kwargs,
    ) -> tuple[str, str]:
        working_memory = working_memory or []
        memory = memory or []

        # generate markdown explanation
        structual_prompt = EXPLANATION_STRUCTUAL_PROMPT.format(
            user_requirement=user_requirement,
            plan_status=plan_status
        )

        context = self.llm.format_msg(memory + [Message(content=structual_prompt, role="user")] + working_memory)

        # LLM call
        rsp = await self.llm.aask(context, system_msgs=[EXPLAINER_EXPLANATION_SYSTEM_MSG], **kwargs)
        explanation = CodeParser.parse_code(text=rsp, lang="markdown")


        # generate code
        structual_prompt = CODE_STRUCTUAL_PROMPT.format(
            user_requirement=user_requirement,
            plan_status=plan_status,
            tool_info=tool_info
        )

        context = self.llm.format_msg(memory + [Message(content=structual_prompt, role="user")] + working_memory)

        # LLM call
        if use_reflection:
            code = await self._debug_with_reflection(context=context, working_memory=working_memory)
        else:
            rsp = await self.llm.aask(context, system_msgs=[EXPLAINER_CODE_SYSTEM_MSG], **kwargs)
            code = CodeParser.parse_code(text=rsp, lang="python")

        return code, explanation
