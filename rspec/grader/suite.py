from typing import Dict, List

VALID_EXPECTATION_ERRORS = (
    "RSpec::Expectations::ExpectationNotMetError",
    "RSpec::Mocks::MockExpectationError",
)

class Failure(object):
    def __init__(self, exception: str, err_msg: str, backtrace: List[str]) -> None:
        self.exception = exception
        self.err_msg = err_msg
        self.backtrace = backtrace

    def asdict(self) -> Dict[str, str]:
        return {
            'error_message' : self.err_msg,
            'exception' : self.exception
        }

    def __eq__(self, o) -> bool:
        same_ex = self.exception == o.exception
        
        return same_ex # and same_stack # maybe include stack ?

    def __repr__(self) -> str:
        return f"Failure({self.exception}: {self.err_msg})"

class Test(object):
    def __init__(self, desc: str, fail: Failure) -> None:
        # self.id = id
        self.description = desc
        self.passed = fail is None
        self.failure = fail

    def __repr__(self) -> str:
        base = f"{self.description}: {'passed' if self.passed else 'failed'}"
        return base #+ ("pass" if self.passed else f"{self.failure}")

class Var(object):
    def __init__(self, tests: Dict[str, Test], id: str, feedback_banner: str = "") -> None:
        self.tests: Dict[str, Test] = tests
        self.id: str = id
        self.feedback_banner: str = f"\n{feedback_banner}\n"

    def __repr__(self) -> str:
        # if len(self.tests) > 0:
        info_str = '\n\t' +'\n\t'.join([f"{test}" for test in self.tests])
        # else:
            # info_str = ' "Failed to Unexpected Error"'
        return f"Var({self.id},{info_str}\n)"

    def get_feedback_prefix(self) -> str:
        if self.feedback_banner.strip() == "":
            return self.id
        return f"{self.id} ({self.feedback_banner})"

    def grade(self, reference) -> Dict:
        return Var.grade(self, reference)

    @classmethod
    def grade(cls, reference, submission) -> Dict:
        """Produce a scoring report from two Variants, first as reference, second as submission"""
        out = { }

        for testID in reference.tests.keys():
            ref: Test = reference.tests.get(testID)
            sub: Test = submission.tests.get(testID)
            
            # if the reference test was not responsible for killing this variant, don't grade
            if ref.passed or ref.failure.exception not in VALID_EXPECTATION_ERRORS:
                continue
            
            out[testID] = { 'correct' : False }

            # cases in order:
            #   Student did not submit test case
            #   Student test did not kill mutant (but instructor did)
            #   Student test fails, but not due to an assertion
            #   Student test fails by wrong assertion

            if sub is None: 
                msg = ("Test not found\n" + submission.feedback_banner).strip() + "\n"

            elif sub.passed:
                msg = f"Should fail but passed\n"

            elif sub.failure.exception != ref.failure.exception:
                student_err_msg = sub.failure.err_msg.split('\n')[0].replace("with backtrace:", "")
                msg = f"Failed to unexpected error\n> {student_err_msg}\n"

            elif sub.failure.err_msg.split('\n')[0] != ref.failure.err_msg.split('\n')[0]:
                student_err_msg = sub.failure.err_msg.split('\n')[0].replace("with backtrace:", "")
                msg = f"Failed by wrong assertion\n> {student_err_msg}\n"

            else:
                msg = f"Failed as intended\n"
                out[testID]['correct'] = True

            out[testID].update({ "message" : msg })

        return out
