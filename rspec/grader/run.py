#!/usr/bin/python3
import os
import sys
from pprint import pprint
from re import match as re_match
from json import dumps as json_dumps
from json import loads as json_loads
from typing import Dict, Tuple
from suite import Var
from parse import parseOutput, verifyOutput, GRADING_SCRIPT, PRE_SCRIPT, ENTRY_FILE
import importlib.machinery
import importlib.util

ROOT_DIR: str = '/grade' if len(sys.argv) < 2 else sys.argv[1]
SUBMISSION_FILE: str = f"{ROOT_DIR}/data/data.json"
RESULTS_FILE   : str = f'{ROOT_DIR}/results/results.json'

VARS_DIR: str = f"{ROOT_DIR}/tests"
SOLUTION_DIR  : str = f"{VARS_DIR}/solution"
SUBMISSION_DIR: str = f"{VARS_DIR}/submission"
METADATA_FILE : str = f"{VARS_DIR}/meta.json"

VAR_REGEX: str = '^var_.+$'
# this will be made when this script is run
WORK_DIR: str = f"{ROOT_DIR}/working"

# this can be defined properly in `parse.py`
PRE_SCRIPT    : str = PRE_SCRIPT    .format(work=WORK_DIR, file=f"{WORK_DIR}/{ENTRY_FILE}")
GRADING_SCRIPT: str = GRADING_SCRIPT.format(work=WORK_DIR, file=f"{WORK_DIR}/{ENTRY_FILE}")

def do_assertions():
    if not os.path.exists(f"{ROOT_DIR}"):
        raise Exception(f"{ROOT_DIR} not found! Mounting may have failed.")

    if not os.path.exists(f"{VARS_DIR}"):
        raise Exception(f"{VARS_DIR} not found! Mounting may have failed.")

    if not os.path.isfile(METADATA_FILE):
        raise Exception(f"Metadata file {METADATA_FILE} not found! Check that your tests/ directory contains it.")

    if not os.path.isfile(SUBMISSION_FILE):
        raise Exception(f"Submission data file {SUBMISSION_FILE} not found!")

def prep_directories():

    if not os.path.exists(WORK_DIR):
        os.mkdir(WORK_DIR)

    if not os.path.exists(SUBMISSION_DIR):
        os.mkdir(SUBMISSION_DIR)

def load_submission() -> Tuple[Dict, Dict]:
    """Load the submission object and the grading object from disk"""

    with open(METADATA_FILE, 'r') as info:
        grading_info = json_loads(info.read())
    with open(SUBMISSION_FILE, 'r') as data:
        content = data.read()
        # print("Ingested submission data:")
        # pprint(content)
        submission_data = json_loads(content)

    return submission_data, grading_info

def prep_submission():
    """Load the submission into {SUBMISSION_DIR}/_submission_file"""
    try:
        loader = importlib.machinery.SourceFileLoader(
            'submission_processing', '/grade/tests/submission_processing.py' )
        module = loader.load_module()
        module.prepSubmission(submission_data, ROOT_DIR, SUBMISSION_DIR)
    except:
        # there may not be files in student/, so we just hide the error
        # TODO: check if files exist before doing this
        os.system(f"cp {ROOT_DIR}/student/* {SUBMISSION_DIR} 2> /dev/null")
        
        # copy student submission from /grade/data/data.json 
        #   into the end of f"{SUBMISSION_DIR}/_submission_file"
        #   and add the pre- and post- text
        with open(f"{SUBMISSION_DIR}/_submission_file", 'w') as sub: 
            sub.write( grading_info.get('pre-text', '') )
            sub.write( submission_data['submitted_answers']['student-parsons-solution'] )
            sub.write( grading_info.get('post-text', '') )


def ls_vars(directory: str = VARS_DIR):
    """get the folder names that match VAR_REGEX"""
    yield from filter(
        lambda name: re_match(VAR_REGEX, name),
        os.listdir(directory)
    )

def load_var(var_name: str, solution: bool) -> Var:
    """Empties the working directory, copies in the necessary files
       from common/, the variant, and the submission"""
    # nuke working directory
    os.system(f"rm -rf {WORK_DIR}/*")
    # copy common files
    os.system(f"cp -r {VARS_DIR}/common/* {WORK_DIR}")
    # copy in files from the variant
    os.system(f"cp -r {VARS_DIR}/{var_name}/* {WORK_DIR}")

    # copy the submitted files
    if solution:
        sub_dir = SOLUTION_DIR
    else:
        sub_dir = SUBMISSION_DIR

    ## append the submitted code snippet
    os.system(f"cat {sub_dir}/_submission_file >> {WORK_DIR}/{grading_info['submission_file']}")
    ## and all additionally submitted files
    if 'submission_root' in grading_info.keys():
        os.system(f"cp {sub_dir}/* {WORK_DIR}/{grading_info['submission_root']}/")
    ## but we accidentally copy in the submission again, so let's remove that
    os.system(f"rm {WORK_DIR}/{grading_info['submission_root']}/_submission_file")

def run_var(var_name: str, solution: bool) -> Tuple[Var, str]:
    """Prepares, runs, and parses the execution of a variant from its name (its folder)"""
    load_var(var_name=var_name, solution=solution)

    vname = var_name[len("var_"):] # cut out the "var_" at the front
    vname = vname.capitalize() # fix capitalization ("hello_There" -> "Hello_there")
    vname = vname.replace("_", " ")

    os.popen(f"cd {WORK_DIR} && {PRE_SCRIPT}")
    output = os.popen(f"cd {WORK_DIR} && {GRADING_SCRIPT}").read()
    verification = verifyOutput(output)

    def panic(var_name: str, stdout: str) -> None:
        suite = "instructor" if solution else "student"
        print(f"Error when running variant \"{var_name}\" on {suite} suite. Output:")
        print(f"> {stdout}")
        sys.exit(1)

    # if not solution:
    #     print(f"Contents of {WORK_DIR}/spec/giftcard_spec.rb")
    #     with open(f"{WORK_DIR}/spec/giftcard_spec.rb", "r") as f:
    #         print(f.read())

    return parseOutput(output=output, name=vname, result=verification, exit_func=panic), output

if __name__ == '__main__':

    if not os.path.exists(out_path := f"{ROOT_DIR}/results"):
        os.mkdir(out_path)
    # in case something goes wrong, write "ungradable" until a full grading run is done
    with open(RESULTS_FILE, 'w') as results:
        json_data: str = json_dumps({
            'gradable' : False,
            'tests' : [],
            "format_errors" : "Unexpected Error. If you are developing this locally, check the" + \
            "output of your local server. Otherwise, consult your system administrator."
        })
        results.write(json_data)

    try:
        do_assertions()
    except Exception as e:
        with open(RESULTS_FILE, 'w') as results:
            json_data: str = json_dumps({
                'gradable' : False,
                'tests' : [],
                "format_errors" : f"Instructor Error: {e.args[0]}"
            })
            results.write(json_data)
        print(f"The autograder was not passed a valid submission: {e.args[0]}")
        exit(0)

    submission_data, grading_info = load_submission()

    gradingData: Dict = {
        'gradable' : True,
        # this will store reports generated by Var.grade()
        'tests' : []
    }

    prep_directories()
    prep_submission()

    variants = ls_vars()
    emptyTest = { 'message': '', 'points': 0, 'max_points': 0 }
    out = { }

    for var in variants:
        ref_var, ref_out = run_var(var_name=var, solution=True)
        sub_var, sub_out = run_var(var_name=var, solution=False)

        report = Var.grade(ref_var, sub_var)

        for testID, data in report.items(): 
            out[testID] = {
                'message' : out.get(testID, emptyTest)['message'] + \
                            f"Variant \"{ref_var.id}\" : {data['message']}",
                'points' : out.get(testID, emptyTest)['points'] + int(data['correct']),
                'max_points' : out.get(testID, emptyTest)['max_points'] + 1
            }

    gradingData['tests'] = [
        {
            "name" : testID,
            "output" : data['message'],
            "points" : data['points'],
            "max_points" : data['max_points']
        }
        for testID, data in out.items()
    ]

    if len(gradingData['tests']) > 0:
        pts = sum([ test['points'] for test in gradingData['tests'] ])
        max_pts = sum([ test['max_points'] for test in gradingData['tests'] ])
        gradingData['score'] = pts / max_pts
    else:
        print("No gradable test-mutant pairs found!")
        gradingData['score'] = 0

    with open(RESULTS_FILE, 'w') as results:
        json_data: str = json_dumps(gradingData)
        # print("Returned grading data:")
        # pprint(gradingData)
        results.write(json_data)
