REMOTE="saasbook"

infer_image() {
    local current_dir
    current_dir="$(basename "$(pwd)")"

    case "$current_dir" in
        ruby)
            printf '%s\n' "pl-ruby-autograder"
            ;;
        rspec)
            printf '%s\n' "pl-rspec-autograder"
            ;;
        *)
            echo "Error: could not infer IMAGE from $(pwd)." 1>&2
            echo "Run dev_tools.sh from the ruby/ or rspec/ subdirectory." 1>&2
            return 1
            ;;
    esac
}

ensure_image() {
    local inferred_image
    inferred_image="$(infer_image)" || return 1

    if [[ "$IMAGE" != "$inferred_image" ]]; then
        IMAGE="$inferred_image"
        echo "Working on $REMOTE/$IMAGE"
    fi
}

TMP_OUT=/tmp/dev_out
indent() {
    local indent=1

    if [ -n "$1" ]; then indent=$1; fi
    pr -to $(($indent * 2))
    return $?
}

run_and_indent() {
    local indent_level output_file exit_code
    indent_level="${1:-1}"
    shift

    output_file="$(mktemp /tmp/dev_out.XXXXXX)"
    "$@" >"$output_file" 2>&1
    exit_code=$?
    cat "$output_file" | indent "$indent_level"
    rm -f "$output_file"
    return $exit_code
}

mount_root_path() {
    if [[ -n "$DEV_MOUNT_ROOT" ]]; then
        printf '%s\n' "$DEV_MOUNT_ROOT"
    else
        printf '%s/.container_mount\n' "`pwd`"
    fi
}

grade_mount_path() {
    printf '%s/grade\n' "$(mount_root_path)"
}

container_name() {
    printf '%s\n' "${DEV_CONTAINER_NAME:-autograder_test}"
}

build() { ensure_image && docker build -t $REMOTE/$IMAGE . ; }
push() { ensure_image && docker push $REMOTE/$IMAGE:latest ; }
build_push() { build && push ; }

build_image() { # build $IMAGE:dev
   # keep success output short, but show the full log if the build fails
    local build_log
    ensure_image || return 1
    build_log="$(mktemp /tmp/dev_out.XXXXXX)"

    if ! sudo docker build -q -t $IMAGE:dev . >"$build_log" 2>&1; then
        cat "$build_log"
        rm -f "$build_log"
        return 1
    fi

    hash="$(tail -n 1 "$build_log" | cut -d: -f2)"
    rm -f "$build_log"
    echo -e \> Image name / hash: \\n\\t $IMAGE:dev / $hash
}

delete_image() { # delete $IMAGE:dev locally
    ensure_image || return 1
    echo -n Deleting image ...
    sudo docker image rm $IMAGE:dev > /dev/null
    if [[ $? != "0" ]]; then return 1; fi
    echo done.
}

run_image() { # run $IMAGE:dev as `autograder_test`
    local mount_root grade_root stdout_file stderr_file container code
    ensure_image || return 1
    mount_root="$(mount_root_path)"
    grade_root="$(grade_mount_path)"
    stdout_file="$mount_root/stdout"
    stderr_file="$mount_root/stderr"
    container="$(container_name)"

    # silence both stderr and stdout
    delete_container &> /dev/null

    echo Running Image ...
    ( sudo docker run --name "$container" --network none --mount type=bind,source="$grade_root",target=/grade $IMAGE:dev /grader/run.py \
            2>"$stderr_file" \
            1>"$stdout_file" & )
    sleep 1
    docker container ls | indent 2
    code="$(docker container wait "$container")"
    echo \> Container exited with code $code | indent 2
    if [[ $code != "0" ]]; then
        echo \> Stdout:
        cat "$stdout_file" | indent

        echo \> Stderr:
        cat "$stderr_file" | indent
    fi
    rm -f "$stdout_file"
    rm -f "$stderr_file"
    #echo ==============================================================
    return $code
}

delete_container() { # delete the container named `autograder_test`
    sudo docker container rm "$(container_name)"
}

package_gems() {
    local tests_dir bundle_dir grade_root
    ensure_image || return 1
    grade_root="$(grade_mount_path)"
    tests_dir="$grade_root/tests"

    if [[ -d "$tests_dir/app" ]]; then
        bundle_dir="/grade/tests/app"
    else
        bundle_dir="/grade/tests/common"
    fi

    sudo docker run --rm \
        --mount type=bind,source="$tests_dir",target=/grade/tests \
        "$IMAGE:dev" sh -lc "cd $bundle_dir && bundle package --all --all-platforms --quiet"
}

prep_mount() { # assuming $1 is the variants_dir (the question/tests/ directory)
    local mount_root grade_root variant_dir
    mount_root="$(mount_root_path)"
    grade_root="$(grade_mount_path)"

    which jq > /dev/null
    if [[ $? != "0" ]]; then
        (echo "jq is required to run this script, please install and add it to your \$PATH" 1>&2)
        return 1
    fi

    echo "Preparing mount files ... "

    clean_grades 2>/dev/null

    # make all the necessary dirs
    mkdir -p "$grade_root"
    mkdir "$grade_root/data"
    mkdir "$grade_root/serverFilesCourse"
    mkdir "$grade_root/student"
    mkdir "$grade_root/tests"

    # load the variants
    # script_dir="$(pwd)/${0::-18}"
    variant_dir="$(pwd)/$1"
    cp -r "$variant_dir"/. "$grade_root/tests/"
    rm -f "$grade_root/tests/data.json"
    rm -f "$grade_root/tests/expected.json"

    # load submission files
    if [[ -f "$variant_dir/data.json" ]]; then
        cp "$variant_dir/data.json" "$grade_root/data/"
    elif [[ -d "$variant_dir/submission" ]]; then
        local submission_file_contents
        cp -r "$variant_dir"/submission/. "$grade_root/student"

        submission_file_contents="$(jq -Rs . < "$grade_root/student/_submission_file")"
        printf '%s\n' "{\"submitted_answers\": {\"submission\": $submission_file_contents}, \"raw_submitted_answers\": {\"submission.main\": \"[]\", \"submission.log\": \"[]\"}}" \
            > "$grade_root/data/data.json"
        ## double-check that _submission_file isn't in /grade/student
        rm -f "$grade_root/student/_submission_file"
    else
        (echo "No submission found: Exiting" 1>&2)
        return 1
    fi

    package_gems
    return $?
}

clean_grades() {
    local mount_root grade_root
    mount_root="$(mount_root_path)"
    grade_root="$(grade_mount_path)"

    if [[ ! -d "$mount_root" ]]; then return 0; fi

    if [[ -d "$grade_root" ]]; then
        sudo chown -R $USER "$grade_root"
        if [[ $? != "0" ]]; then return 1; fi
    fi

    rm -rf "$mount_root"
    if [[ $? != "0" ]]; then return 1; fi
    return
}

clean() { # Remove .container_mount/ and delete $IMAGE:dev and $IMAGE:latest locally
    clean_grades
    delete_image
}

compare() { # assuming $1 is the variant directory, $2 is the script directory
    local output_file exit_code
    # compare the result
    echo Comparison:

    output_loc="$(grade_mount_path)/results/results.json"
    expect_loc="$1/expected.json"
    script="$2/tests/verify_result.py"

    output_file="$(mktemp /tmp/dev_out.XXXXXX)"
    python3 $script $expect_loc $output_loc >"$output_file" 2>&1
    exit_code=$?
    cat "$output_file" | indent 2
    rm -f "$output_file"
    return $exit_code
}

run_test() { # $1 is variant_dir (the question/tests/ directory)
    if [[ $1 == "" ]]; then
        echo Test not provided, assuming \`run_tests\`
        run_tests
        return $?
    fi

    # basically remove "run_test.sh" from the script call to get the directory
    script_dir=`pwd`

    run_and_indent 1 build_image
    if [[ $? != "0" ]]; then return 1; fi

    prep_mount "$1"
    if [[ $? != "0" ]]; then return 1; fi

    echo Running the grader
    run_and_indent 1 run_image
    if [[ $? == "0" ]]; then
        delete_container > /dev/null
        if [[ $? != "0" ]]; then return 1; fi

        run_and_indent 1 delete_image
        if [[ $? != "0" ]]; then return 1; fi
    else return 1; fi
    echo done.

    compare "$1" "$script_dir"

    return $?
}

run_variant_test() { # $1 is variant_dir, $2 is the script directory
    local variant_dir script_dir mount_root variant_name
    variant_dir="$1"
    script_dir="$2"
    mount_root="$(mktemp -d /tmp/dev_mount.XXXXXX)"
    if [[ $? != "0" ]]; then
        echo "Failed to create temporary mount directory"
        return 1
    fi

    variant_name="$(basename "${variant_dir%/}" | tr -c '[:alnum:]_.-' '-')"

    (
        export DEV_MOUNT_ROOT="$mount_root"
        export DEV_CONTAINER_NAME="autograder_test_${variant_name}_${RANDOM}_$$"

        cleanup_variant_test() {
            delete_container > /dev/null 2>&1
            clean_grades > /dev/null 2>&1
        }

        trap cleanup_variant_test EXIT

        echo Running test $variant_dir

        run_and_indent 2 prep_mount "$variant_dir"
        if [[ $? != "0" ]]; then
            echo "Preparing Mount Failed!" | indent 2
            exit 1
        fi

        run_and_indent 2 run_image
        if [[ $? != "0" ]]; then
            exit 1
        fi

        run_and_indent 2 compare "$variant_dir" "$script_dir"
        exit $?
    )
}

run_tests() { # run all tests in tests/
    local script_dir logs_dir jobs_file variant_dir variant_name log_file pid exit_status
    script_dir=`pwd`

    failures=0
    failed=""

    run_and_indent 1 build_image
    if [[ $? != "0" ]]; then return 1; fi

    logs_dir="$(mktemp -d /tmp/dev_tests.XXXXXX)"
    if [[ $? != "0" ]]; then
        echo "Failed to create temporary log directory"
        return 1
    fi
    jobs_file="$logs_dir/jobs.tsv"
    touch "$jobs_file"

    for variant_dir in tests/*/; do
        if [[ ! -d "$variant_dir" ]]; then
            continue
        fi

        variant_name="$(basename "${variant_dir%/}")"
        log_file="$logs_dir/$variant_name.log"

        run_variant_test "$variant_dir" "$script_dir" > "$log_file" 2>&1 &
        printf '%s\t%s\t%s\n' "$!" "$variant_dir" "$log_file" >> "$jobs_file"
    done

    while IFS=$'\t' read -r pid variant_dir log_file; do
        if [[ -z "$pid" ]]; then
            continue
        fi

        wait "$pid"
        exit_status=$?
        cat "$log_file"

        if [[ "$exit_status" != "0" ]]; then
            failures=$((failures+1))
            failed="$failed\n> $variant_dir"
        fi
    done < "$jobs_file"

    rm -rf "$logs_dir"

    if [[ $failures == "0" ]]; then
        delete_image
    fi

    echo -e "Failures: $failures $failed"
    return $((1 - ($failures == 0)))
}

new_test() { # $1 is the new test name (must be a valid filename)

    if [[ $1 == "" ]]; then
        echo Error: Please supply a test name that is a valid filename
        return 1
    fi

    # make the base folders and files
    cd tests/
    mkdir $1
    mkdir $1/app
    mkdir $1/app/spec

    touch $1/app/script.rb
    touch $1/app/Gemfile
    touch $1/solution

    # initialize the spec file
    echo -e "require_relative '../script.rb'\n" > $1/app/spec/script_spec.rb

    # populate the json objects with filler
    meta_content="{\n    \"submission_file\": \"script.rb\",\n    \"submission_root\": \"\"\n}\n"
    expected_content="{\n    \"gradable\":true,\n    \"tests\":[],\n    \"score\":0.0\n}\n"
    data_content="{\n    \"submitted_answers\" : {\n        \"submission\": \"\"\n    },\n    \"raw_submitted_answers\": {\n        \"submission.main\": \"[]\",\n        \"submission.log\": \"[]\"\n    },\n    \"gradable\": true\n}\n"
    echo -e "$meta_content" >> $1/meta.json
    echo -e "$expected_content" >> $1/expected.json
    echo -e "$data_content" >> $1/data.json


    # return to base directory
    cd ../
    return
}

debug() {
    local grade_root
    ensure_image || return 1
    grade_root="$(grade_mount_path)"

    sudo docker run -it --rm \
        --mount type=bind,source="$grade_root",target=/grade \
        --mount type=bind,source=`pwd`/debug_tools.sh,target=/tools.sh \
        $IMAGE:dev
    return
}
