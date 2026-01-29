#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2023/5/11 17:44
@Author  : alexanderwu
@File    : __init__.py

@ Modified by joaopaulo7 on 2026/01/29 
"""
from enum import Enum

from metagpt.actions.action import Action
from metagpt.actions.action_output import ActionOutput
from metagpt.actions.add_requirement import UserRequirement
from metagpt.actions.debug_error import DebugError
from metagpt.actions.design_api import WriteDesign
from metagpt.actions.design_api_review import DesignReview
from metagpt.actions.project_management import WriteTasks
from metagpt.actions.research import CollectLinks, WebBrowseAndSummarize, ConductResearch
from metagpt.actions.run_code import RunCode
from metagpt.actions.search_and_summarize import SearchAndSummarize
from metagpt.actions.write_code import WriteCode
from metagpt.actions.write_code_review import WriteCodeReview
from metagpt.actions.write_prd import WritePRD
from metagpt.actions.write_prd_review import WritePRDReview
from metagpt.actions.write_test import WriteTest
from metagpt.actions.di.execute_nb_code import ExecuteNbCode
from metagpt.actions.di.write_analysis_code import WriteAnalysisCode
from metagpt.actions.di.write_plan import WritePlan

#explainer
from metagpt.actions.de.execute_nb_code import ExecuteNbCode as  ExpExecuteNbCode
from metagpt.actions.de.explain_and_write_analysis_code import ExplainAndWriteAnalysisCode
from metagpt.actions.de.write_plan import WritePlan as ExpWritePlan


class ActionType(Enum):
    """All types of Actions, used for indexing."""

    ADD_REQUIREMENT = UserRequirement
    WRITE_PRD = WritePRD
    WRITE_PRD_REVIEW = WritePRDReview
    WRITE_DESIGN = WriteDesign
    DESIGN_REVIEW = DesignReview
    WRTIE_CODE = WriteCode
    WRITE_CODE_REVIEW = WriteCodeReview
    WRITE_TEST = WriteTest
    RUN_CODE = RunCode
    DEBUG_ERROR = DebugError
    WRITE_TASKS = WriteTasks
    SEARCH_AND_SUMMARIZE = SearchAndSummarize
    COLLECT_LINKS = CollectLinks
    WEB_BROWSE_AND_SUMMARIZE = WebBrowseAndSummarize
    CONDUCT_RESEARCH = ConductResearch
    EXECUTE_NB_CODE = ExecuteNbCode
    WRITE_ANALYSIS_CODE = WriteAnalysisCode
    WRITE_PLAN = WritePlan
    
    #explainer
    EXP_EXECUTE_NB_CODE = ExpExecuteNbCode
    EXPLAIN_AND_WRITE_ANALYSIS_CODE = ExplainAndWriteAnalysisCode
    EXP_WRITE_PLAN = ExpWritePlan


__all__ = [
    "ActionType",
    "Action",
    "ActionOutput",
]
