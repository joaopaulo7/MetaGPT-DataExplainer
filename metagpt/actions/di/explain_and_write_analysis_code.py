# -*- encoding: utf-8 -*-
"""
@Date    :   2025/04/09 15:42:27
@Author  :   joaopaulo7
@File    :   explain_and_write_analysis_code.py
"""
from __future__ import annotations

import json
from typing import Any, Coroutine

from metagpt.actions.di.write_analysis_code import WriteAnalysisCode
from metagpt.prompts.di.explain_and_write_analysis_code import (
    DEBUG_REFLECTION_EXAMPLE,
    TITLE_SYSTEM_MSG,
    EXPLANATION_SYSTEM_MSG,
    CODE_SYSTEM_MSG,
    EXPLANATION_STRUCTURAL_PROMPT,
    CODE_STRUCTURAL_PROMPT,
    REFLECTION_PROMPT,
    REFLECTION_SYSTEM_MSG, TITLE_STRUCTURAL_PROMPT,
)
from metagpt.schema import Message
from metagpt.utils.common import CodeParser, ParsingErrorException

CORRECTION_PROMPT = """
\n\nError: Failed to parse JSON! Make sure to use the correct format!
Make sure that the whole JSON is in a triple tick code block.
Reason as to what the mistake might be before attempting again.
"""


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


    async def _ask_and_parse_json(self,
                                  structural_prompt: str,
                                  system_msg: str,
                                  working_memory: list[Message] = [],
                                  use_reflection: bool = False,
                                  memory: list[Message] = [],
                                  max_attempts: int = 3,
                                  **kwargs) -> str:

        success = False
        tries = 0
        error_msg = []
        rsp=""
        while not success and tries < max_attempts:
            tries += 1
            context = self.llm.format_msg(memory
                                          + [Message(content=structural_prompt, role="user")]
                                          + working_memory
                                          + error_msg)
            try:
                if use_reflection:
                    code = await self._debug_with_reflection(context=context, working_memory=working_memory)
                else:
                    rsp = await self.llm.aask(context, system_msgs=[system_msg], **kwargs)
                    json_dict = json.loads(CodeParser.parse_code(text=rsp, lang="json"), strict=False)
                    code = "".join(json_dict['source'])
                success = True
            except (ParsingErrorException, json.decoder.JSONDecodeError) as e:
                error_msg.append(Message(content=rsp, role="assistant"))
                error_msg.append(Message(content=f"{CORRECTION_PROMPT}\n{str(e)}", role="user"))

        # if it didn't make it, just returns the response
        if not success:
            return rsp
        else:
            return code



    async def write_code(
            self,
            user_requirement: str,
            plan_status: str = "",
            tool_info: str = "",
            working_memory: list[Message] = None,
            use_reflection: bool = False,
            nb_state: str = "",
            memory: list[Message] = None,
            **kwargs) -> str:

        working_memory = working_memory or []
        memory = memory or []

        # generate code
        structural_prompt = CODE_STRUCTURAL_PROMPT.format(
            user_requirement=user_requirement,
            plan_status=plan_status,
            tool_info=tool_info,
            nb_state=nb_state
            )

        return await self._ask_and_parse_json(structural_prompt, CODE_SYSTEM_MSG,working_memory, use_reflection,
                                              memory, **kwargs)


    async def write_markdown(
            self,
            user_requirement: str,
            plan_status: str = "",
            working_memory: list[Message] = None,
            use_reflection: bool = False,
            nb_state: str = "",
            memory: list[Message] = None,
            **kwargs) -> str:
        working_memory = working_memory or []
        memory = memory or []

        # generate markdown explanation
        structural_prompt = EXPLANATION_STRUCTURAL_PROMPT.format(
            user_requirement=user_requirement,
            plan_status=plan_status,
            nb_state=nb_state
        )


        return await self._ask_and_parse_json(structural_prompt, EXPLANATION_SYSTEM_MSG, working_memory, use_reflection,
                                              memory, **kwargs)
    
    
    async def write_title(
            self,
            plan_contex: str = "",
            **kwargs,
    ) -> str:
        # generate markdown title
        structural_prompt = TITLE_STRUCTURAL_PROMPT.format(
            plan_contex=plan_contex.split('## Current Task')[0]) # remove irrelevant information

        return await self._ask_and_parse_json(structural_prompt , TITLE_SYSTEM_MSG, **kwargs)
