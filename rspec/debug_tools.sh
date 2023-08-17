
run() {
    /grader/run.py
}

load_sub() {
    curr_dir=`pwd`

    cd /grader/
    python3 -c "import run ; run.load_var('$1', False)"

    cd $curr_dir
    return
}

load_sol() {
    curr_dir=`pwd`
    
    cd /grader/
    python3 -c "import run ; run.load_var('$1', True)"

    cd $curr_dir
    return
}

script_output() {
    curr_dir=`pwd`

    cd /grader/
    imports="from run import WORK_DIR, GRADING_SCRIPT ; import os ; from pprint import pprint"
    run_cmd="os.popen(f\"cd {WORK_DIR} && {GRADING_SCRIPT}\").read()"
    python3 -c "$imports ; null = None ; pprint(eval($run_cmd))"

    cd $curr_dir
    return
}
