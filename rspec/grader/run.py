#!/usr/bin/python3
import os
import sys
import shutil
import subprocess
import importlib.machinery

from pathlib import Path
from re import match as re_match
from json import dumps as json_dumps
from json import loads as json_loads
from typing import Dict, Sequence, Tuple
from suite import Var
from parse import parseOutput, verifyOutput, GRADING_SCRIPT, PRE_SCRIPT, ENTRY_FILE

ROOT_DIR = Path("/grade" if len(sys.argv) < 2 else sys.argv[1])
SUBMISSION_FILE = ROOT_DIR / "data" / "data.json"
RESULTS_FILE = ROOT_DIR / "results" / "results.json"

VARS_DIR = ROOT_DIR / "tests"
SOLUTION_DIR = VARS_DIR / "solution"
SUBMISSION_DIR = VARS_DIR / "submission"
METADATA_FILE = VARS_DIR / "meta.json"

VAR_REGEX: str = "^var_.+$"
# this will be made when this script is run
WORK_DIR = ROOT_DIR / "working"
# this can be defined properly in `parse.py`
PRE_SCRIPT: str = PRE_SCRIPT.format(work=WORK_DIR, file=WORK_DIR / ENTRY_FILE)
GRADING_SCRIPT: str = GRADING_SCRIPT.format(work=WORK_DIR, file=WORK_DIR / ENTRY_FILE)

DataPath = Sequence[str]
DataDict = dict[str, "str | DataDict"]


class SubmissionPathError(Exception):
    """Could not locate the student submission in data.json"""


def do_assertions():
    if not ROOT_DIR.exists():
        raise Exception(f"{ROOT_DIR} not found! Mounting may have failed.")

    if not VARS_DIR.exists():
        raise Exception(f"{VARS_DIR} not found! Mounting may have failed.")

    if not METADATA_FILE.is_file():
        raise Exception(
            f"Metadata file {METADATA_FILE} not found! Check that your tests/ directory contains it."
        )

    if not SUBMISSION_FILE.is_file():
        raise Exception(f"Submission data file {SUBMISSION_FILE} not found!")


def prep_directories():
    WORK_DIR.mkdir(exist_ok=True)
    SUBMISSION_DIR.mkdir(exist_ok=True)


def load_submission() -> Tuple[Dict, Dict]:
    """Load the submission object and the grading object from disk"""

    with METADATA_FILE.open("r") as info:
        grading_info = json_loads(info.read())
    with SUBMISSION_FILE.open("r") as data:
        content = data.read()
        # print("Ingested submission data:")
        # pprint(content)
        submission_data = json_loads(content)

    return submission_data, grading_info


def get_at_path(data: DataDict, path: DataPath):
    try:
        current = data
        for path_item in path:
            assert isinstance(current, dict)
            current = current[path_item]
        return current
    except KeyError as error:
        raise SubmissionPathError(
            f"Could not locate the student submission at data path {path}."
        ) from error


def infer_faded_parsons_submission_path(data: DataDict):
    """Resolve the canonical faded parsons submission path from raw submitted inputs."""
    raw_answers = data.get("raw_submitted_answers", {})
    assert isinstance(raw_answers, dict)
    submitted_answers = data.get("submitted_answers", {})
    answers_names = sorted(
        {
            key[: -len(".main")]
            for key in raw_answers.keys()
            if key.endswith(".main") and key[: -len(".main")] in submitted_answers
        }
    )

    if len(answers_names) == 1:
        return ["submitted_answers", answers_names[0]]
    if len(answers_names) > 1:
        raise SubmissionPathError(
            "Multiple pl-faded-parsons submissions found. Add "
            "'answers_name' or 'data_path' to tests/meta.json."
        )
    return None


def resolve_submission_path(data: Dict, grading_info: Dict):
    if "data_path" in grading_info:
        return grading_info["data_path"]
    if "answers_name" in grading_info:
        return ["submitted_answers", grading_info["answers_name"]]

    inferred_path = infer_faded_parsons_submission_path(data)
    if inferred_path is not None:
        return inferred_path

    raise SubmissionPathError(
        "Could not infer a submission path. Add 'answers_name' or 'data_path' "
        "to tests/meta.json, or provide tests/submission_processing.py."
    )


def prep_submission():
    """Load the submission into {SUBMISSION_DIR}/_submission_file"""
    try:
        loader = importlib.machinery.SourceFileLoader(
            "submission_processing",
            str(ROOT_DIR / "tests" / "submission_processing.py"),
        )
        module = loader.load_module()
        module.prepSubmission(submission_data, str(ROOT_DIR), str(SUBMISSION_DIR))
    except:
        # there may not be files in student/, so we just hide the error
        # TODO: check if files exist before doing this
        student_dir = ROOT_DIR / "student"
        if student_dir.exists():
            copy_directory_contents(student_dir, SUBMISSION_DIR)

        # copy student submission from /grade/data/data.json
        #   into the end of f"{SUBMISSION_DIR}/_submission_file"
        #   and add the pre- and post- text
        sub_data = get_at_path(
            submission_data, resolve_submission_path(submission_data, grading_info)
        )
        assert isinstance(sub_data, str)

        with (SUBMISSION_DIR / "_submission_file").open("w") as sub:
            sub.write(grading_info.get("pre-text", ""))
            sub.write(sub_data)
            sub.write(grading_info.get("post-text", ""))


def copy_directory_contents(source: Path, destination: Path):
    if not source.exists():
        return

    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def reset_directory_contents(directory: Path):
    for item in directory.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def ls_vars(directory: Path = VARS_DIR):
    """get the folder names that match VAR_REGEX"""
    yield from (
        path.name for path in directory.iterdir() if re_match(VAR_REGEX, path.name)
    )


def load_var(var_name: str, solution: bool) -> Var:
    """Empties the working directory, copies in the necessary files
    from common/, the variant, and the submission"""
    # nuke working directory
    reset_directory_contents(WORK_DIR)
    # copy common files
    copy_directory_contents(VARS_DIR / "common", WORK_DIR)
    # copy in files from the variant
    copy_directory_contents(VARS_DIR / var_name, WORK_DIR)

    # copy the submitted files
    if solution:
        sub_dir = SOLUTION_DIR
    else:
        sub_dir = SUBMISSION_DIR

    ## append the submitted code snippet
    with (sub_dir / "_submission_file").open("r") as submission_file:
        with (WORK_DIR / grading_info["submission_file"]).open("a") as grading_file:
            grading_file.write(submission_file.read())
    ## and all additionally submitted files
    if "submission_root" in grading_info.keys():
        copy_directory_contents(sub_dir, WORK_DIR / grading_info["submission_root"])
    ## but we accidentally copy in the submission again, so let's remove that
    if "submission_root" in grading_info.keys():
        submission_copy = (
            WORK_DIR / grading_info["submission_root"] / "_submission_file"
        )
        if submission_copy.exists():
            submission_copy.unlink()


def run_var(var_name: str, solution: bool) -> Tuple[Var, str]:
    """Prepares, runs, and parses the execution of a variant from its name (its folder)"""
    load_var(var_name=var_name, solution=solution)

    vname = var_name[len("var_") :]  # cut out the "var_" at the front
    vname = vname.capitalize()  # fix capitalization ("hello_There" -> "Hello_there")
    vname = vname.replace("_", " ")

    subprocess.run(PRE_SCRIPT, cwd=WORK_DIR, shell=True, check=False)
    output = subprocess.run(
        GRADING_SCRIPT,
        cwd=WORK_DIR,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
    ).stdout
    verification = verifyOutput(output)

    def panic(var_name: str, stdout: str):
        suite = "instructor" if solution else "student"
        print(f'Error when running variant "{var_name}" on {suite} suite. Output:')
        print(f"> {stdout}")
        return sys.exit(1)

    # if not solution:
    #     print(f"Contents of {WORK_DIR}/spec/giftcard_spec.rb")
    #     with open(f"{WORK_DIR}/spec/giftcard_spec.rb", "r") as f:
    #         print(f.read())

    return (
        parseOutput(output=output, name=vname, result=verification, exit_func=panic),
        output,
    )


if __name__ == "__main__":
    out_path = ROOT_DIR / "results"
    if not out_path.exists():
        out_path.mkdir()
    # in case something goes wrong, write "ungradable" until a full grading run is done
    with RESULTS_FILE.open("w") as results:
        json_data: str = json_dumps(
            {
                "gradable": False,
                "tests": [],
                "format_errors": "Unexpected Error. If you are developing this locally, check the"
                + "output of your local server. Otherwise, consult your system administrator.",
            }
        )
        results.write(json_data)

    try:
        do_assertions()
    except Exception as e:
        with RESULTS_FILE.open("w") as results:
            json_data: str = json_dumps(
                {
                    "gradable": False,
                    "tests": [],
                    "format_errors": f"Instructor Error: {e.args[0]}",
                }
            )
            results.write(json_data)
        print(f"The autograder was not passed a valid submission: {e.args[0]}")
        exit(0)

    submission_data, grading_info = load_submission()

    gradingData: Dict = {
        "gradable": True,
        # this will store reports generated by Var.grade()
        "tests": [],
    }

    prep_directories()
    try:
        prep_submission()
    except SubmissionPathError as error:
        with RESULTS_FILE.open("w") as results:
            json_data: str = json_dumps(
                {
                    "gradable": False,
                    "tests": [],
                    "format_errors": f"Instructor Error: {error.args[0]}",
                }
            )
            results.write(json_data)
        print(f"The autograder could not locate the submission: {error.args[0]}")
        exit(0)

    variants = ls_vars()
    emptyTest = {"message": "", "points": 0, "max_points": 0}
    out = {}

    for var in variants:
        ref_var, ref_out = run_var(var_name=var, solution=True)
        sub_var, sub_out = run_var(var_name=var, solution=False)

        report = Var.grade(reference=ref_var, submission=sub_var)

        for testID, data in report.items():
            out[testID] = {
                "message": out.get(testID, emptyTest)["message"]
                + f"{ref_var.get_feedback_prefix()} : {data['message']}",
                "points": out.get(testID, emptyTest)["points"] + int(data["correct"]),
                "max_points": out.get(testID, emptyTest)["max_points"] + 1,
            }

    gradingData["tests"] = [
        {
            "name": testID,
            "output": data["message"],
            "points": data["points"],
            "max_points": data["max_points"],
        }
        for testID, data in out.items()
    ]

    if len(gradingData["tests"]) > 0:
        pts = sum([test["points"] for test in gradingData["tests"]])
        max_pts = sum([test["max_points"] for test in gradingData["tests"]])
        gradingData["score"] = pts / max_pts
    else:
        print("No gradable test-mutant pairs found!")
        gradingData["score"] = 0

    with RESULTS_FILE.open("w") as results:
        json_data: str = json_dumps(gradingData)
        # print("Returned grading data:")
        # pprint(gradingData)
        results.write(json_data)
