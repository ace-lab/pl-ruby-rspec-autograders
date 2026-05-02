from typing import Dict, Optional
from suite import TestResult, Failure, VariantResult
from json import loads as json_loads
from json.decoder import JSONDecodeError
from enum import Enum
from re import sub as str_replace

# Both commands are
PRE_SCRIPT = "&&".join(
    (
        "bundle _2.3.26_ config set --local without 'production'",
        "bundle _2.3.26_ install --local --quiet",
    )
)
GRADING_SCRIPT = "&&".join(["rspec --format json"])


class Result(Enum):
    Pass = 0
    MalformedInput = 1
    UnexpectedError = 2


def verifyOutput(output: str) -> Result:
    """Returns if the passed string is a valid output"""
    try:
        data = json_loads(output)
    except JSONDecodeError:
        return Result.MalformedInput

    summary = data.get("summary", None)
    if not summary or summary.get("errors_outside_of_examples_count", 1) > 0:
        return Result.UnexpectedError

    return Result.Pass


def parseOutput(
    output: str,
    name: str,
    result: Result,
) -> Optional[VariantResult]:
    """Function to parse the output of the GRADING_SCRIPT into a <VariantResult> instance"""

    if result == Result.MalformedInput:
        return None

    out = json_loads(output)
    if result == Result.UnexpectedError:
        return VariantResult({}, name, feedback_banner=out["messages"][0])

    parsed_tests: Dict[str, TestResult] = {}
    for rspec_test in out["examples"]:
        test_id = rspec_test["full_description"]  # [-(ID_LEN):]
        # test_name = rspec_test['full_description'][:-(ID_LEN)]

        if rspec_test["status"] == "passed":
            failure = None
        else:
            ex = rspec_test["exception"]
            # import code
            # code.interact(local=locals())
            failure = Failure(
                exception=ex["class"],
                err_msg=str_replace("0x[0-9a-f]+", "0x0000", ex["message"]),
                backtrace=ex["backtrace"],
            )

        parsed_tests[test_id] = TestResult(test_id, failure)

    return VariantResult(parsed_tests, name)
