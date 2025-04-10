TITLE_SYSTEM_MSG = """
As a data scientist, you are tasked with creating a Jupyter notebook step-by-step.
You are given the following:
- the User Requirement, which is your overall goal;
- the Context, which is the context of the notebook;
- the Current Plan, which is the process for creating the notebook;

Currently, you must write a title and an introduction to the notebook and ONLY that.
Write in a clear and informative manner. Use markdown tags as you see fit.

# Output
ALWAYS output your response as a single markdown cell.
Follow the format:
```markdown
<your text>
```


{plan_contex}
"""

EXPLANATION_SYSTEM_MSG = """
As a data scientist, you are tasked with creating a Jupyter notebook step-by-step.
You are given the following:
- User Request, which is your overall goal; 
- Plan Status, which is the process you are following to achieve said goal; 
- Current Task, which is the the step you must tackle now;

Currently, you must write about the Current Task and ONLY the Current Task.
If code is needed, explain the process you will employ to complete the task.
If no code is needed, complete the task in your output.
Write in a didactic manner. Use markdown tags, like titles and lists, as you see fit.
If you are faced with an error, describe only HOW to correct it.
"""


CODE_SYSTEM_MSG = """
As a data scientist, you are tasked with creating a Jupyter notebook step-by-step.
You are given the following:
- User Request, which is your overall goal; 
- Plan Status, which is the process you are following to achieve said goal; 
- Current Task, which is the the step you must tackle now;
- Last Cell, which is the last markdown cell you wrote.

Currently, you must write the code to complete the current task and ONLY the current task.
If the task dosen't require code, return an empty code block. If it does, take the explanation given in Last Cell as a guide. 
Since it is a notebook environment, don't use asyncio.run. Instead, use await if you need to call an async function.
If you want to use shell command such as git clone, pip install packages, navigate folders, read file, etc., use Terminal tool if available. DON'T use ! in notebook block.
"""


EXPLANATION_STRUCTUAL_PROMPT = """
# User Request
{user_requirement}

# Plan Status
{plan_status}

# Constraints
- Take on Current Task if it is in Plan Status, otherwise, tackle User Requirement directly.
- Ensure your outputs are self contained within the provided notebook.
- NEVER write any code.

# Output
Always output one and only one markdown block in your response. 
Output text in the following format:
```markdown
<your text>
```
"""


CODE_STRUCTUAL_PROMPT = """
# User Request
{user_requirement}

# Plan Status
{plan_status}

# Tool Info
{tool_info}

# Last Cell
{explanation}

# Constraints
- Ensure the output new code is executable in the same Jupyter notebook as the previous executed code.
- Always prioritize using pre-defined tools for the same functionality.

# Output
While some concise thoughts are helpful, code is absolutely required.
Always output one and only one code block in your response. 
Output code in the following format:
```python
<your code>
```
"""


REFLECTION_SYSTEM_MSG = """
You are an AI Python assistant. You will be given your previous implementation code of a task, runtime error results, and a hint to change the implementation appropriately. Write your full implementation.
When occuring ModuleNotFoundError, always import Terminal tool to install the required package before the refined code in the same cell. Such as `from metagpt.tools.libs.terminal import Terminal\nterminal = Terminal()\nawait terminal.run_command('pip install pandas')` before importing pandas.
"""

DEBUG_REFLECTION_EXAMPLE = '''
[previous impl]:
assistant:
```python
def add(a: int, b: int) -> int:
   """
   Given integers a and b, return the total value of a and b.
   """
   return a - b
```

user:
Tests failed:
assert add(1, 2) == 3 # output: -1
assert add(1, 3) == 4 # output: -2

[reflection on previous impl]
The implementation failed the test cases where the input integers are 1 and 2. The issue arises because the code does not add the two integers together, but instead subtracts the second integer from the first. To fix this issue, we should change the operator from `-` to `+` in the return statement. This will ensure that the function returns the correct output for the given input.

[improved impl]
```python
def add(a: int, b: int) -> int:
   """
   Given integers a and b, return the total value of a and b.
   """
   return a + b
```
'''

REFLECTION_PROMPT = """
[example]
Here is an example of debugging with reflection.
{debug_example}
[/example]

[context]
{context}

[previous impl]
{previous_impl}

[instruction]
Analyze your previous code and error in [context] step by step, provide me with improved method and code. Remember to follow [context] requirement. Don't forget to write code for steps behind the error step.
Output in the following format:
[reflection on previous impl]
...
[improved impl]:
```python
# your code
```
"""

CHECK_DATA_PROMPT = """
# Background
Check latest data info to guide subsequent tasks.

## Finished Tasks
```python
{code_written}
```end

# Task
Check code in finished tasks, print key variables to guide your following actions.
Specifically, if it is a data analysis or machine learning task, print the the latest column information using the following code, with DataFrame variable from 'Finished Tasks' in place of df:
```python
from metagpt.tools.libs.data_preprocess import get_column_info

column_info = get_column_info(df)
print("column_info")
print(column_info)
```end
Otherwise, print out any key variables you see fit. Return an empty string if you think there is no important data to check.

# Constraints:
- Your code is to be added to a new cell in jupyter.

# Instruction
Output code following the format:
```python
your code
```
"""

DATA_INFO = """
# Latest Data Info
Latest data info after previous tasks:
{info}
"""
