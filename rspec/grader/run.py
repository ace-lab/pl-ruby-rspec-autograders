#!/usr/bin/python3
import sys
import shutil
import subprocess
import importlib.machinery

from collections import defaultdict
from pathlib import Path
from json import dumps as json_dumps
from json import loads as json_loads
from typing import Dict, Sequence, Tuple
from suite import VariantResult
from parse import parseOutput, verifyOutput, GRADING_SCRIPT, PRE_SCRIPT

ROOT_DIR = Path("/grade" if len(sys.argv) < 2 else sys.argv[1])
SUBMISSION_FILE = ROOT_DIR / "data" / "data.json"
RESULTS_FILE = ROOT_DIR / "results" / "results.json"

VARS_DIR = ROOT_DIR / "tests"
SOLUTION_DIR = VARS_DIR / "solution"
SUBMISSION_DIR = VARS_DIR / "submission"
METADATA_FILE = VARS_DIR / "meta.json"

VAR_GLOB: str = "var_*"
# this will be made when this script is run
WORK_DIR = ROOT_DIR / "working"
DEBUG = False

DataPath = Sequence[str]
DataDict = dict[str, "str | DataDict"]


class SubmissionPathError(Exception):
    """Could not locate the student submission in data.json"""


class InvalidSubmissionError(Exception):
    """Could not locate the student submission in data.json"""


def validate_file_structure():
    if not ROOT_DIR.exists():
        raise Exception(f"{ROOT_DIR} not found! Mounting may have failed.")

    out_path = ROOT_DIR / "results"
    out_path.mkdir(exist_ok=True)

    if not VARS_DIR.exists():
        raise Exception(f"{VARS_DIR} not found! Mounting may have failed.")

    if not METADATA_FILE.is_file():
        raise Exception(
            f"Metadata file {METADATA_FILE} not found! Check that your tests/ directory contains it."
        )

    if not SUBMISSION_FILE.is_file():
        raise Exception(f"Submission data file {SUBMISSION_FILE} not found!")

    WORK_DIR.mkdir(exist_ok=True)
    SUBMISSION_DIR.mkdir(exist_ok=True)


def write_result(json: Dict, *, gradable: bool):
    json["gradable"] = gradable
    with RESULTS_FILE.open("w") as results:
        json_data: str = json_dumps(json)
        results.write(json_data)


def write_invalid_result(err: str):
    """Reports that a submission is ungradable, does not count as a grading attmept"""
    write_result({"format_errors": err, "tests": []}, gradable=False)


def load_problem_data():
    with METADATA_FILE.open("r") as info:
        metadata = json_loads(info.read())

    with SUBMISSION_FILE.open("r") as data:
        submission_data = json_loads(data.read())

    return submission_data, metadata


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


def resolve_path(submission, metadata):
    if "data_path" in metadata:
        return metadata["data_path"]
    if "answers_name" in metadata:
        return ["submitted_answers", metadata["answers_name"]]

    inferred_path = infer_faded_parsons_submission_path(submission)
    if inferred_path is not None:
        return inferred_path

    raise SubmissionPathError(
        "Could not infer a submission path. Add 'answers_name' or 'data_path' "
        "to tests/meta.json, or provide tests/submission_processing.py."
    )


def prepare_submission_directory(submission, metadata):
    """Load the submission into {SUBMISSION_DIR}/_submission_file"""
    try:
        loader = importlib.machinery.SourceFileLoader(
            "submission_processing",
            str(ROOT_DIR / "tests" / "submission_processing.py"),
        )
        module = loader.load_module()
        module.prepSubmission(submission, str(ROOT_DIR), str(SUBMISSION_DIR))
    except:
        # there may not be files in student/, so we just hide the error
        # TODO: check if files exist before doing this
        student_dir = ROOT_DIR / "student"
        if student_dir.exists():
            copy_directory_contents(student_dir, SUBMISSION_DIR)

        # copy student submission from /grade/data/data.json
        #   into the end of f"{SUBMISSION_DIR}/_submission_file"
        #   and add the pre- and post- text
        sub_data = get_at_path(submission, resolve_path(submission, metadata))
        assert isinstance(sub_data, str)

        pre_text = metadata.get("pre-text", "")
        post_text = metadata.get("post-text", "")
        if pre_text and not pre_text.endswith("\n"):
            pre_text = pre_text + "\n"
        if post_text and not post_text.startswith("\n"):
            post_text = "\n" + post_text

        if DEBUG:
            print("DEBUG prepare_submission_directory")
            print("DEBUG submission path:", resolve_path(submission, metadata))
            print("DEBUG pre-text:", repr(pre_text))
            print("DEBUG student submission:", repr(sub_data))
            print("DEBUG post-text:", repr(post_text))
            print(
                "DEBUG combined submission:",
                repr(
                    pre_text
                    + sub_data
                    + post_text
                ),
            )

        with (SUBMISSION_DIR / "_submission_file").open("w") as sub:
            sub.write(pre_text)
            sub.write(sub_data)
            sub.write(post_text)


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


def variant_directories(directory: Path = VARS_DIR):
    """get the folder names that match VAR_GLOB"""
    yield from (path.name for path in directory.glob(VAR_GLOB))


def load_var(var_name: str, sub_metadata: Dict, solution: bool):
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
        with (WORK_DIR / sub_metadata["submission_file"]).open("a") as grading_file:
            grading_file.write(submission_file.read())
    if DEBUG:
        print("DEBUG working file:", WORK_DIR / sub_metadata["submission_file"])
        with (WORK_DIR / sub_metadata["submission_file"]).open("r") as grading_file:
            print("DEBUG working file contents:")
            print(grading_file.read())
    ## and all additionally submitted files
    if "submission_root" in sub_metadata.keys():
        copy_directory_contents(sub_dir, WORK_DIR / sub_metadata["submission_root"])
    ## but we accidentally copy in the submission again, so let's remove that
    if "submission_root" in sub_metadata.keys():
        submission_copy = (
            WORK_DIR / sub_metadata["submission_root"] / "_submission_file"
        )
        if submission_copy.exists():
            submission_copy.unlink()


def run_var(var_name: str, sub_metadata: Dict, solution: bool):
    """Prepares, runs, and parses the execution of a variant from its name (its folder)"""
    load_var(var_name=var_name, sub_metadata=sub_metadata, solution=solution)

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
    if DEBUG:
        print("DEBUG rspec output:")
        print(output)
    verification = verifyOutput(output)

    # if not solution:
    #     print(f"Contents of {WORK_DIR}/spec/giftcard_spec.rb")
    #     with open(f"{WORK_DIR}/spec/giftcard_spec.rb", "r") as f:
    #         print(f.read())
    parsed = parseOutput(output=output, name=vname, result=verification)

    if parsed is not None:
        return parsed, output

    suite = "instructor" if solution else "student"
    print(f'Error when running variant "{vname}" on {suite} suite. Output:')
    print(f"> {output}")
    return sys.exit(1)


def grade_all_vars(metadata) -> Dict[str, VariantResult.Feedback]:
    """returns a dict of (testId, testGrade) pairs consolidated across all vars"""
    tests = defaultdict(VariantResult.Feedback)

    for var in variant_directories():
        ref_var, _ref_out = run_var(var, metadata, solution=True)
        sub_var, _sub_out = run_var(var, metadata, solution=False)

        report = VariantResult.grade(reference=ref_var, submission=sub_var)

        # TODO: this compression could cause collision across vars if there
        # are two tests with the same ID (fn name iirc)
        for testID, data in report.items():
            test_result = tests[testID]
            prefix = ref_var.get_feedback_prefix()
            test_result.output += f"{prefix} : {data.output}"
            test_result.points += data.points
            test_result.max_points += 1

    return dict(tests)


def format_final_output(test_grades: Dict[str, VariantResult.Feedback]):
    pts = sum(t.points for t in test_grades.values())
    max_pts = sum(t.max_points for t in test_grades.values())
    return {
        "score": max(0, max_pts) and (pts / max_pts),
        # this will store reports generated by VariantResult.grade()
        "tests": [
            {
                "name": testID,
                "points": data.points,
                "max_points": data.max_points,
                "output": data.output,
            }
            for testID, data in test_grades.items()
        ],
    }


def __main__():
    try:
        validate_file_structure()
    except Exception as error:
        write_invalid_result(f"Instructor Error: {error.args[0]}")
        raise InvalidSubmissionError(
            f"The autograder expected a different file structure"
        ) from error

    try:
        submission_data, metadata = load_problem_data()
        prepare_submission_directory(submission_data, metadata)
    except (SubmissionPathError, FileNotFoundError) as error:
        write_invalid_result(f"Instructor Error: {error.args[0]}")
        raise InvalidSubmissionError(
            f"The autograder could not locate the submission data"
        ) from error

    try:
        test_grades = grade_all_vars(metadata)
    except Exception as error:
        write_invalid_result(f"Instructor Error: {error.args[0]}")
        raise InvalidSubmissionError(
            f"The autograder variant harness crashed"
        ) from error

    try:
        if not test_grades:
            print("No gradable test-mutant pairs found!")

        gradingData = format_final_output(test_grades)
        write_result(gradingData, gradable=True)
    except Exception as error:
        write_invalid_result(f"Instructor Error: {error.args[0]}")
        raise InvalidSubmissionError(
            f"The autograder could not write grading results"
        ) from error


if __name__ == "__main__":
    __main__()
