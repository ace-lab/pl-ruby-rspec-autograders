from typing import Callable, Dict
from suite import Var, Test, Failure
from json import loads as json_loads
from json.decoder import JSONDecodeError
from enum import Enum
from re import sub as str_replace

# can use {work} for the working dir and {file} for ENTRY_FILE absolute path for both
# PRE_SCRIPT and GRADING_SCRIPT
# Both commands are 
PRE_SCRIPT = "&&".join([
    'bundle _2.3.26_ config set --local without \'production\'',
    'bundle _2.3.26_ install --local --quiet',
])
GRADING_SCRIPT = "&&".join([
    'rspec --format json' 
])

# this may be helpful if we want to grade a particular script in the submission
ENTRY_FILE = ' ' # rspec will do everything for us, no need to specify a specific file

Result = Enum('Result', ['Pass', 'MalformedInput', 'UnexpectedError'])

def verifyOutput(output: str) -> Result:
    """Returns if the passed string is a valid output"""
    try:
        data = json_loads(output)
    except JSONDecodeError:
        return Result.MalformedInput
    if data['summary']['errors_outside_of_examples_count'] > 0:
        return Result.UnexpectedError
    return Result.Pass

def parseOutput(output: str, name: str, result: Result, exit_func: Callable[[str, str], Var] = lambda: exit(1)) -> Var:
    """Function to parse the output of the GRADING_SCRIPT into a <Var> instance"""

    if result == Result.MalformedInput:
        exit_func(name, output)
        return None
    
    out = json_loads(output)
    if result == Result.UnexpectedError:
        return Var({}, name, feedback_banner=out['messages'][0])

    parsed_tests: Dict[str, Test] = {}
    for rspec_test in out['examples']:
        test_id = rspec_test['full_description']#[-(ID_LEN):]
        # test_name = rspec_test['full_description'][:-(ID_LEN)]
        
        if rspec_test['status'] == 'passed':
            failure = None
        else:
            ex = rspec_test['exception']
            # import code
            # code.interact(local=locals())
            failure = Failure(
                exception=ex['class'], 
                err_msg=str_replace("0x[0-9a-f]+", "0x0000", ex['message']), 
                backtrace=ex['backtrace']
            )

        test = Test(test_id, failure)

        parsed_tests[test_id] = test

    return Var(parsed_tests, name)