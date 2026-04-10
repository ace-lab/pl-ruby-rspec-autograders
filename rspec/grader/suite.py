from typing import Dict, List, Literal, Optional, Union
from dataclasses import dataclass, field

VALID_EXPECTATION_ERRORS = (
    "RSpec::Expectations::ExpectationNotMetError",
    "RSpec::Mocks::MockExpectationError",
)


def first_line(s: str) -> str:
    i = s.find("\n")
    if i < 0:
        return s
    return s[:i]


@dataclass(frozen=True)
class Failure:
    exception: str
    err_msg: str = field(compare=False)
    backtrace: List[str] = field(compare=False)

    def __str__(self) -> str:
        return f"Failure({self.exception}: {self.err_msg})"

    @staticmethod
    def diff(*, ref: "Failure", sub: "Optional[Failure]") -> Optional[str]:
        # cases:
        #   Student test did not kill mutant (but instructor did)
        if sub is None:
            return f"Should fail but passed"

        sub_fail_err_first = first_line(sub.err_msg)

        #   Student test fails, but not due to an assertion
        if sub.exception != ref.exception:
            student_err_msg = sub_fail_err_first.replace("with backtrace:", "")
            return f"Failed to unexpected error\n> {student_err_msg}"

        #   Student test fails by wrong assertion
        if sub_fail_err_first != first_line(ref.err_msg):
            student_err_msg = sub_fail_err_first.replace("with backtrace:", "")
            return f"Failed by wrong assertion\n> {student_err_msg}"

        return None


@dataclass(frozen=True)
class TestResult:
    description: str
    failure: Optional[Failure] = None

    @property
    def passed(self):
        return self.failure is None

    def __str__(self) -> str:
        return f"{self.description}: {'passed' if self.passed else 'failed'}"


@dataclass(frozen=True)
class VariantResult:
    tests: Dict[str, TestResult]
    id: str
    feedback_banner: str = ""

    def __str__(self) -> str:
        info_str = "\n\t" + "\n\t".join([f"{test}" for test in self.tests])
        return f"VariantResult({self.id},{info_str}\n)"

    def get_feedback_prefix(self) -> str:
        if self.feedback_banner.strip() == "":
            return self.id
        return f"{self.id} (\n{self.feedback_banner}\n)"

    @staticmethod
    def grade(
        *, reference: "VariantResult", submission: "VariantResult"
    ) -> Dict[str, Dict[Literal["correct", "message"], str]]:
        """Produce a scoring report from two Variants, first as reference, second as submission"""
        out = {}

        for testID, ref in reference.tests.items():
            # if the reference test was not responsible for killing this variant, don't grade
            if ref.failure is None:
                continue

            if ref.failure.exception not in VALID_EXPECTATION_ERRORS:
                continue

            sub = submission.tests.get(testID)

            if sub is None:
                correct = False
                msg = f"Test not found\n\n{submission.feedback_banner}".strip()
            else:
                diff = Failure.diff(ref=ref.failure, sub=sub.failure)
                correct = diff is None
                msg = diff or "Failed as intended"

            out[testID] = {"correct": correct, "message": msg + "\n"}

        return out
