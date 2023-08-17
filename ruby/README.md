# ruby-autograder

This is a Docker image made to autograde Ruby Faded Parsons Problems in Prairielearn.

## Quickstart

Assuming you have Prairielearn up and running locally (if not see [Installing PL locally](https://github.com/ace-lab/pl-ucb-faded-parsons-research/wiki/Getting-Set-Up#installing-prairielearn-locally) (even if you aren't making [Faded Parsons Problems](https://github.com/ace-lab/pl-ruby-rspec-autograders/wiki/Glossary#faded-parsons-problem))), the following steps will allow autograding for simple ruby problems:

1) In your `info.json` of the question, include the following:
```json
"gradingMethod": "External",
"externalGradingOptions": {
    "enabled": true,
    "image" : "saasbook/pl-fpp-ruby-autograder",
    "entrypoint": "/grader/run.py",
    "timeout" : 60
}
```

2) In the `tests/` directory in your question, create a file called `meta.json` that includes the following*
```json
{
    "submission_file": "file/to/submit/to.rb",
    "submission_root": "location/to/submit/additional/files/",
    "submit_to_line" : 3,
    "pre-text" : "any lines to precede\n  the student's submission\n", 
    "post-text": "any lines to succeed\n  the student's submission\n",
}
```
*Note that the key `submission_root` is optional, as the feature that requires it is not yet implemented as of 21 Aug 2023

3) In the `tests/` directory in your question, include the complete application that the student submits to
   in `tests/app/`. Note: do not include the text included in `meta.json`'s `"pre-text"` and `"post-text"` 
   fields as those will be inserted during grading.

4) Also in the `tests/` directory, include the instructor's solution (excluding the `"pre-text"` and 
   `"post-text"` fields) in a file named `solution` (with no file extension).

5) If you are not using the [Faded Parsons Element](https://github.com/ace-lab/pl-faded-parsons), include a python script called `submission_processing.py` in `tests/` (`tests/submission_processing.py`) with a function `get_submission(data: Dict) -> str`. This function takes in the entire submission data object and should return the student's submission as plaintext. You can see a [simple example](https://github.com/ace-lab/pl-ruby-rspec-autograders/blob/main/ruby/tests/no_file_submission/submission_processing.py#L4-L10) in the tests in this repository.

## Autograding process

1. The autograder checks if a file named `tests/submission_processing.py` was passed.
    - If so, it tries to import a function with the signature ```get_submission(data: Dict) -> str``` that takes in the submission data and returns the student's submission as plaintext
    - If not, the autograder extracts the student submission from `data['submitted_answers"]["student-parsons-solution"]`
2. The autograder then writes the student submission along with the pre-text and post-text (in `meta.json`) to the submission_file (in `meta.json`) at the line provided (in `meta.json`) to the application in `tests/app`.
3. Then RSpec is run on the application and the test results are gathered.
   - If there is an issue running RSpec, the output of `rspec --format json` is printed to the console hosting PL and the autograder exits, marking the submission ungradable.
4. All excluded tests are removed and the assertions below are run. If any fail, the autograder exits with an error.
   - The solution provided passes all non-excluded tests
5. If all assertions pass, the score is calculated as the number of tests the student passed. and feedback
   is their passing/failing status along with any stack traces if it was an unexpected error when running.
