from os import popen
from json import loads as json_loads
from json.decoder import JSONDecodeError
from typing import Union
from time import perf_counter

GRADING_SCRIPT: str = " && ".join([
    'cd {work}',
    # 'bundle config path /grade/working/vendor/bundle',
    'bundle install --local --quiet',
    'rspec --format json' 
])

class ExecutionError(Exception):
    """The `GRADING_SCRIPT` did not return a parseable output"""

def verifyOutput(output: str) -> Union[ExecutionError, JSONDecodeError, None]:
    """Returns if the passed string is a valid output"""
    try:
        data = json_loads(output)
    except JSONDecodeError as j_error:
        return j_error

    if data['summary']['errors_outside_of_examples_count'] != 0:
        return ExecutionError(*data['messages'])

def run(work_dir: str) -> str:
    """Run the `GRADING_SCRIPT` and return stdout"""
    return popen(f"cd {work_dir} && {GRADING_SCRIPT.format(work=work_dir)}").read()

def execute(solution: bool, work_dir: str) -> str:
    """Run a test suite and return a summary of it.\n
       Throws: `ExecutionError`"""

    s_time = perf_counter()
    stdout = run(work_dir)
    print("    execution stdout returned in:", perf_counter() - s_time)

    output_error = verifyOutput(stdout)
    if isinstance(output_error, JSONDecodeError):
        suite = "instructor" if solution else "student"
        print(f"Unhandled error when running {suite} test suite. Output:")
        print(f"> {stdout}")
        print("Exiting.")
        exit(1)
    elif output_error is not None:
        raise output_error

    return stdout