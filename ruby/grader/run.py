#!/usr/bin/python3
from time import perf_counter
start_time = perf_counter()
from typing import Dict, Set
from lib.parsing import Suite, Test, parse
from json import loads as json_loads, dumps as json_dumps
import importlib.machinery
import lib.executing as exe
import os

#dev imports;; remove before production
from pprint import pprint

ROOT_DIR = "/grade"

WORK_DIR = f"{ROOT_DIR}/working/"
APP_DIR = f"{ROOT_DIR}/tests/app/"

class SolutionError(Exception):
    """Provided solution is not valid"""

def get_submission(data: Dict) -> str:
    """Get the student's submission as a plain-text string from data.json  
    If `tests/submission_processing.py` does not exist, load straight from 
    `["submitted_answers"]["student-parsons-solution"]`"""

    if os.path.isfile('/grade/tests/submission_processing.py'):
        loader = importlib.machinery.SourceFileLoader(
            'submission_processing', '/grade/tests/submission_processing.py' )
        module = loader.load_module()
        return module.get_submission(data)

    return data['submitted_answers']['student-parsons-solution']

def write_to(content: str, out_file: str, line: int = -1) -> None:
    """Write `content` to line `line` of file `to`"""
    new_lines = [ l + '\n' for l in content.split('\n') ]
    with open(out_file, "r") as old:
        old_content = old.readlines()
        old_content += ["\n"]

    final_lines = old_content[:line] + new_lines + old_content[line:]

    with open(out_file, "w") as out:
        out.writelines(final_lines)

def run(submission_content: str, grading_info: Dict, solution: bool, work_dir: str = WORK_DIR,
        app_dir: str = APP_DIR) -> Suite:
    """Load and execute the provided submission. Returns the test output as a `lib.parsing.Suite`"""
    os.system(f"rm -rf {work_dir}/*")
    os.system(f"cp -r {app_dir}/* {work_dir}")

    write_to(
        submission_content,
        out_file=f"{work_dir}/{grading_info['submission_file']}",
        line=grading_info['submit_to_line']
    )

    print("    <run> file ops done", perf_counter() - start_time)

    return parse(exe.execute(solution=solution, work_dir=WORK_DIR))

def verify_valid_solution(sol: Suite, exclusions: Set[str]=set()) -> None:
    """Verify that the solution meets the following criterion and throw a 
       `SolutionError` otherwise"""
    def failed_solution_test(test: Test) -> None:
        raise SolutionError(
            f"The test '{test.name}' did not pass on the solution system under test!" )

    sol_report = sol.grade(
        failure_case=failed_solution_test,
        exclude=exclusions
    )
    sol_points = sum(map(lambda report: report['points'], sol_report))
    max_points = sum(map(lambda report: report['max_points'], sol_report))
    if sol_points != max_points:
        raise SolutionError("The solution does not score 100%!")


def main():

    if not os.path.exists(f"{ROOT_DIR}"):
        raise FileNotFoundError(f"ERROR: {ROOT_DIR} not found! Mounting may have failed.")

    with open(f"{ROOT_DIR}/tests/meta.json", 'r') as info:
        grading_info = json_loads(info.read())
    with open(f"{ROOT_DIR}/data/data.json", 'r') as data:
        submission_data = json_loads(data.read())
    with open(f"{ROOT_DIR}/tests/solution", 'r') as sol:
        solution = sol.read()

    if not os.path.exists(WORK_DIR):
        os.mkdir(WORK_DIR)

    print("Assertions and setup done", perf_counter() - start_time)

    print("Running Solution ...")

    sol: Suite = run(
        grading_info.get('pre-text', '') + "\n" +
            solution + "\n" +
            grading_info.get('post-text', ''),
        grading_info,
        solution=True
    )

    print("Solution run", perf_counter() - start_time)

    try:
        verify_valid_solution(sol, set(grading_info.get('grading_exclusions', [])))
    except SolutionError as error:
        print(*error.args)

    print("Solution verified", perf_counter() - start_time)

    grading_data: Dict = {
        'gradable' : True,
    }

    print("Running Submission ...")

    try:
        sub: Suite = run(
            grading_info.get('pre-text', '') + "\n" +
                get_submission(submission_data) + "\n" +
                grading_info.get('post-text', ''),
            grading_info,
            solution=False
        )

        print("Submission run", perf_counter() - start_time)

        sub_report = sub.grade(
            failure_case=(lambda test: f"Failed: \n{test.failure.err_msg} \n"),
            exclude=set(grading_info.get('grading_exclusions', []))
        )

        grading_data['tests'] = sub_report
        pts = sum([ test['points'] for test in grading_data['tests'] ])
        max_pts = sum([ test['max_points'] for test in grading_data['tests'] ])
        grading_data['score'] = pts / max_pts

        print("Submission graded", perf_counter() - start_time)
    except exe.ExecutionError as error:
        grading_data['format_errors'] = error.args[0]
        grading_data['gradable'] = False

        print("Submission raised unexpected error")

    if not os.path.exists(out_path := f"{ROOT_DIR}/results"):
        os.mkdir(out_path)
    with open(f'{ROOT_DIR}/results/results.json', 'w+') as results:
        json_data: str = json_dumps(grading_data)
        pprint(grading_data)
        results.write(json_data)

if __name__ == '__main__':
    print("Imports and definitions done:", perf_counter() - start_time)
    main()
else:
    ###############################
    ###     DEBUG FUNCTIONS     ###
    ###############################

    def load_system(content: str, solution: bool = False):

        if not os.path.exists(f"{ROOT_DIR}"):
            raise Exception(f"ERROR: {ROOT_DIR} not found! Mounting may have failed.")
        with open(f"{ROOT_DIR}/tests/meta.json", 'r') as info:
            grading_info = json_loads(info.read())
        if not os.path.exists(WORK_DIR):
            os.mkdir(WORK_DIR)

        os.system(f"rm -rf {WORK_DIR}/*")
        os.system(f"cp -r {APP_DIR}/* {WORK_DIR}")

        write_to(
            content,
            out_file=f"{WORK_DIR}/{grading_info['submission_file']}",
            line=grading_info['submit_to_line']
        )

    def load_sol():
        """Load the solution and prepare `/grade/tests/working`"""
        if not os.path.exists(f"{ROOT_DIR}"):
            raise FileNotFoundError(f"ERROR: {ROOT_DIR} not found! Mounting may have failed.")
        with open(f"{ROOT_DIR}/tests/meta.json", 'r') as info:
            grading_info = json_loads(info.read())
        with open(f"{ROOT_DIR}/tests/solution", 'r') as sol:
            solution = sol.read()

        load_system(
            grading_info.get('pre-text', '') + "\n" +
                solution + "\n" +
                grading_info.get('post-text', ''),
            solution=True
        )

    def load_sub():
        """Load the submission and prepare `/grade/tests/working`"""
        if not os.path.exists(f"{ROOT_DIR}"):
            raise FileNotFoundError(f"ERROR: {ROOT_DIR} not found! Mounting may have failed.")
        with open(f"{ROOT_DIR}/tests/meta.json", 'r') as info:
            grading_info = json_loads(info.read())
        with open(f"{ROOT_DIR}/data/data.json", 'r') as data:
            submission_data = json_loads(data.read())

        load_system(
            grading_info.get('pre-text', '') + "\n" +
                submission_data['submitted_answers']['student-parsons-solution'] + "\n" +
                grading_info.get('post-text', ''),
            solution=False
        )
