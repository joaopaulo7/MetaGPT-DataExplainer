TITLE_SYSTEM_MSG = """
As a highly capable data science agent, you are tasked with creating a Jupyter notebook step-by-step.
You are given the following:
- the User Requirement, which is your overall goal;
- the Context, which is the context of the notebook;
- the Current Plan, which is the process for creating the notebook;

Currently, you must write a markdown title and an introduction cell to the notebook and ONLY that.
Write in a clear and informative manner.

# Output
You must use the following output format, ensuring every source line ends with a newline character `\\n`:
```json
{
"cell_type": "markdown",
"source": [
"## This is a cell\n",
"A \\\\`markdown\\\\` cell \\n",
"more sample text\\n"
]
}
```
"""

EXPLANATION_SYSTEM_MSG = """
As a highly capable data science agent, you are tasked with creating a Jupyter notebook step-by-step.
You are given the following:
- User Request, which is your overall goal; 
- Plan Status, which is the process you are following to achieve said goal;
- Notebook State, which is how the jupyter notebook currently is.

Currently, you must write a new markdown cell for the provided jupyter notebook.
Provide both a brief overview of the previous execution and an explanation of current step in the process
If execution is needed, explain, in text, the process you will employ to complete the task.
If no execution is needed, complete the task using a markdown cell.
Write in a didactic manner. If there was an error in the previous execution, describe how to correct it in the markdown cell.

# Constraints
- Avoid using python codeblocks in your markdown cell.
- Ensure your response is self-contained within the provided notebook.

# Output
Your output **must include a triple tick JSON code block**, similar to those of jupyter notebooks.
Make sure all special characters are properly escaped, as per the JSON format.
Ensure every source line ends with a newline character ´\\n´ and **never** a `\\\\n`.
You should add your reasoning before the JSON code block.
Example:
```json
{
"cell_type": "markdown",
"source": [
"# Test cell\\n",
"this is the second line of the test cell\\n",
"This is the last line\\n"
]
}
```
"""


CODE_SYSTEM_MSG = """
As a highly capable data science agent, you are tasked with creating a Jupyter notebook step-by-step.
You are given the following:
- User Request, which is your overall goal; 
- Plan Status, which is the process you are following to achieve said goal;
- Notebook State, which is how the jupyter notebook currently is.

Currently, you must write a new code cell for the provided jupyter notebook, aiming to complete the current task and ONLY the current task.
Take the current Notebook State and the last markdown cell as a guide. 
Since it is a notebook environment, don't use asyncio.run. Instead, use await if you need to call an async function.
If you want to use shell commands such as git clone, pip install packages, navigate folders, read file, etc., use Terminal tool if available. DON'T use ! in a notebook cell.

# Constraints
- Ensure the output new code is executable in the same Jupyter notebook.
- Always prioritize using pre-defined tools for the same functionality.
- For tasks that don't require execution, such as summaries, output an empty source.
- NEVER generate a markdown cell.

# Output
Your output **must include a triple tick JSON code block**, similar to those of jupyter notebooks.
Make sure all special characters are properly escaped, as per the JSON format.
Ensure every source line ends with a newline character ´\\n´ and **never** a `\\\\n`.
You should add your reasoning before the JSON code block.
Example:
```json
{
"cell_type": "code",
"source": [
"print('hello world!')\\n",
"print('hello world!!')\\n",
"print('hello world!!!')\\n"
]
}
```
```

if no python code is required:
```json
{
"cell_type": "code",
"source": []
}
```
"""

TITLE_STRUCTURAL_PROMPT = """
# Context
{plan_contex}
"""

EXPLANATION_STRUCTURAL_PROMPT = """
# User Request
{user_requirement}

# Plan Status
{plan_status}

# Notebook State
{nb_state}
"""


CODE_STRUCTURAL_PROMPT = """
# User Request
{user_requirement}

# Plan Status
{plan_status}

# Tool Info
{tool_info}

# Notebook State
{nb_state}
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
