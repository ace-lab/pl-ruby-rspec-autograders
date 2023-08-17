from typing import Callable, Dict, List, Set, Union
from dataclasses import dataclass
from json import loads as json_loads

@dataclass
class Failure:
    exception: str
    err_msg: str
    backtrace: List[str]

    def __eq__(self, other) -> bool:
        if other is None:
            return False

        same_ex = self.exception == other.exception

        backtrace_lens = len(self.backtrace) == len(other.backtrace)
        same_stack = backtrace_lens and all(
            [ stack_1 == stack_2 for stack_1, stack_2 in zip(self.backtrace, other.backtrace) ])

        return same_ex and same_stack

@dataclass
class Test:
    name: str
    failure: Failure = None

    def __eq__(self, other) -> bool:
        return self.failure == other.failure

@dataclass
class Suite:
    tests: Dict[str, Test]

    def get_test(self, test_name: str) -> Test:
        return self.tests.get(test_name, None)

    def grade(self, failure_case : Callable[[Test], Union[str, None]], exclude: Set[str]=set({})
                ) -> List[Dict[str, Union[str, int]]]:
        """Return a list of json objects representing the student's performance
        on the tests provided in the solution test suite."""
        out = []

        for name, test in self.tests.items():
            if name in exclude:
                continue

            points = 0
            max_pts = 1

            if test.failure is not None:
                # the test did not pass on the system under test
                msg = failure_case(test)
            elif test.failure is None:
                msg = "Passed."
                points = max_pts

            out.append({
                "name" : name,
                "output" : msg,
                "points" : points,
                "max_points" : max_pts
            })

        return out

def parse(stdout: str) -> Suite:
    """Produce a summary of a run test suite"""
    json = json_loads(stdout)
    tests: Dict[str, Test] = {}
    for rspec_test in json['examples']:

        if rspec_test['status'] == 'passed':
            failure = None
        else:
            ex = rspec_test['exception']

            failure = Failure(
                exception=ex['class'],
                err_msg=ex['message'],
                backtrace=ex['backtrace']
            )

        test_name: str = rspec_test['full_description']

        tests[test_name] = Test(
            name=test_name,
            failure=failure
        )

    return Suite(tests)
