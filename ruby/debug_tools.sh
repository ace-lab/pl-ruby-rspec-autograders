
run() {
    /grader/run.py
}

load() {
    curr_dir=`pwd`

    cd /grader/
    # $1 can be "sub" or "sol"
    python3 -c "import run ; run.load_$1()"

    cd $curr_dir
    return
}

script_output() {
    curr_dir=`pwd`

    cd /grader/
    imports="from run import WORK_DIR ; from lib.executing import GRADING_SCRIPT ; import os ; from pprint import pprint"
    run_cmd="os.popen(f'cd {WORK_DIR} && {GRADING_SCRIPT.format(work=WORK_DIR)}').read()"
    python3 -c "$imports ; null = None ; pprint(eval($run_cmd))"

    cd $curr_dir
    return
}
