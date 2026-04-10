from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field

VALID_EXPECTATION_ERRORS = (
    "RSpec::Expectations::ExpectationNotMetError",
    "RSpec::Mocks::MockExpectationError",
)


@dataclass(frozen=True)
class Failure(object):
    exception: str
    err_msg: str = field(compare=False)
    backtrace: List[str] = field(compare=False)

    def __str__(self) -> str:
        return f"Failure({self.exception}: {self.err_msg})"


@dataclass(frozen=True)
class Test:
    description: str
    failure: Optional[Failure] = None

    @property
    def passed(self):
        return self.failure is None

    def __str__(self) -> str:
        return f"{self.description}: {'passed' if self.passed else 'failed'}"


def first_line(s: str) -> str:
    i = s.find("\n")
    if i < 0:
        return s
    return s[:i]


@dataclass(frozen=True)
class Var:
    tests: Dict[str, Test]
    id: str
    feedback_banner: str = ""

    def __str__(self) -> str:
        info_str = "\n\t" + "\n\t".join([f"{test}" for test in self.tests])
        return f"Var({self.id},{info_str}\n)"

    def get_feedback_prefix(self) -> str:
        if self.feedback_banner.strip() == "":
            return self.id
        return f"{self.id} (\n{self.feedback_banner}\n)"

    @staticmethod
    def grade(*, reference: "Var", submission: "Var") -> Dict:
        """Produce a scoring report from two Variants, first as reference, second as submission"""
        out = {}

        for testID, ref in reference.tests.items():
            sub = submission.tests.get(testID)

            # if the reference test was not responsible for killing this variant, don't grade
            if (
                ref.failure is None
                or ref.failure.exception not in VALID_EXPECTATION_ERRORS
            ):
                continue

            out[testID] = {"correct": False}

            # cases in order:
            #   Student did not submit test case
            #   Student test did not kill mutant (but instructor did)
            #   Student test fails, but not due to an assertion
            #   Student test fails by wrong assertion

            if sub is None:
                msg = ("Test not found\n" + submission.feedback_banner).strip()

            else:
                msg = diff_test_failures(ref_fail=ref.failure, sub_fail=sub.failure)
                if msg is None:
                    msg = 'Failed as intended'
                    out[testID]["correct"] = True

            out[testID].update({"message": msg + '\n'})

        return out


def diff_test_failures(*, ref_fail: Failure, sub_fail: Optional[Failure]) -> Optional[str]:
    if sub_fail is None:
        return f"Should fail but passed"

    sub_fail_err_first = first_line(sub_fail.err_msg)

    if sub_fail.exception != ref_fail.exception:
        student_err_msg = sub_fail_err_first.replace("with backtrace:", "")
        return f"Failed to unexpected error\n> {student_err_msg}"

    if sub_fail_err_first != first_line(ref_fail.err_msg):
        student_err_msg = sub_fail_err_first.replace("with backtrace:", "")
        return f"Failed by wrong assertion\n> {student_err_msg}"

    return None
