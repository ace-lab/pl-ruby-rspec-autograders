REMOTE="saasbook"
if [[ $IMAGE == "" ]]; then
    IMAGE="pl-fpp-ruby-autograder"
fi

echo Working on $REMOTE/$IMAGE

TMP_OUT=/tmp/dev_out
indent() {
    local indent=1

    if [ -n "$1" ]; then indent=$1; fi
    pr -to $(($indent * 2))
    return $?
}

build() { docker build -t $REMOTE/$IMAGE . ; }
push() { docker push $REMOTE/$IMAGE:latest ; }
buildPush() { build && push ; }

buildImage() { # build $IMAGE:dev
    # only report errors
    hash="$(sudo docker build -q -t $IMAGE:dev .  | cut -d: -f2)"
    echo -e \> Image name / hash: \\n\\t $IMAGE:dev / $hash
}

deleteImage() { # delete $IMAGE:dev locally
    echo -n Deleting image ...
    sudo docker image rm $IMAGE:dev > /dev/null
    if [[ $? != "0" ]]; then return 1; fi
    echo done.
}

runImage() { # run $IMAGE:dev as `autograder_test`
    # silence both stderr and stdout 
    deleteCont &> /dev/null

    echo Running Image ...
    ( sudo docker run --name autograder_test --network none --mount type=bind,source=`pwd`/.container_mount/grade,target=/grade $IMAGE:dev /grader/run.py \
            2>.container_mount/stderr \
            1>.container_mount/stdout & )
    sleep 1
    docker container ls | indent 2
    code="$(docker container wait autograder_test)"
    echo \> Container exited with code $code | indent 2
    if [[ $code != "0" ]]; then 
        echo \> Stdout:
        cat .container_mount/stdout | indent 

        echo \> Stderr:
        cat .container_mount/stderr | indent 
    fi
    rm .container_mount/stdout
    rm .container_mount/stderr
    #echo ==============================================================
    return $code
}

deleteCont() { # delete the container named `autograder_test`
    sudo docker container rm autograder_test
}

prep_mount() { # assuming $1 is the variants_dir (the question/tests/ directory)

    which jq > /dev/null
    if [[ $? != "0" ]]; then 
        (echo "jq is required to run this script, please install and add it to your \$PATH" 1>&2)
        return 1
    fi

    echo "Preparing mount files ... "

    clean 2>/dev/null

    # make all the necessary dirs
    mkdir .container_mount

    mkdir .container_mount/grade
    mkdir .container_mount/grade/data
    mkdir .container_mount/grade/serverFilesCourse
    mkdir .container_mount/grade/student
    mkdir .container_mount/grade/tests

    # load the variants
    # script_dir="$(pwd)/${0::-18}"
    variant_dir="$(pwd)/$1/"
    cp -r $variant_dir/* .container_mount/grade/tests/
    rm .container_mount/grade/tests/data.json
    rm .container_mount/grade/tests/expected.json

    # load submission files
    if [[ -f $variant_dir/data.json ]]; then
        cp $variant_dir/data.json .container_mount/grade/data/
    elif [[ -d $variant_dir/submission ]]; then
        cp -r $variant_dir/submission/* .container_mount/grade/student

        echo {\"submitted_answers\": {\"student-parsons-solution\": `jq -Rs . < .container_mount/grade/student/_submission_file`}} \
            > .container_mount/grade/data/data.json
        ## double-check that _submission_file isn't in /grade/student
        rm .container_mount/grade/student/_submission_file
    else 
        (echo "No submission found: Exiting" 1>&2)
        return 1
    fi

    # now that the files are in place, install the packages
    pd=`pwd`
    rvm use 2.6.10 | indent 
    if [[ "${PIPESTATUS[0]}" != "0" ]]; then return 1; fi
    
    cd .container_mount/grade/tests/app 2&> /dev/null
    if [[ $? != "0" ]]; then cd .container_mount/grade/tests/common; fi

    bundle package --all --all-platforms --quiet > /dev/null
    if [[ $? != "0" ]]; then 
        cd $pd
        return 1
    fi
    # bundle install --local > /dev/null
    cd $pd
}

clean() {
    sudo chown -R $USER .container_mount/grade/
    if [[ $? != "0" ]]; then return 1; fi
    rm -r .container_mount/
    if [[ $? != "0" ]]; then return 1; fi
    return
}

clean_up() { # Remove .container_mount/ and delete $IMAGE:dev and $IMAGE:latest locally
    clean
    deleteImage
}

compare() { # assuming $1 is the variant directory, $2 is the script directory
    # compare the result
    echo Comparison:
    
    output_loc="`pwd`/.container_mount/grade/results/results.json"
    expect_loc="$1/expected.json"
    script="$2/tests/verify_result.py"
    
    python3 $script $expect_loc $output_loc | indent 2

    return "${PIPESTATUS[0]}"
}

run_test() { # $1 is variant_dir (the question/tests/ directory)

    if [[ $1 == "" ]]; then 
        echo Test not provided, assuming \`run_tests\`
        run_tests
        return $?
    fi

    # basically remove "run_test.sh" from the script call to get the directory
    script_dir=`pwd`

    prep_mount $1
    if [[ $? != "0" ]]; then return 1; fi

    echo Running the grader
    buildImage | indent
    runImage | indent

    if [[ "${PIPESTATUS[0]}" == 0 ]]; then
        deleteCont > /dev/null
        if [[ $? != "0" ]]; then return 1; fi

        deleteImage | indent
        if [[ "${PIPESTATUS[0]}" != "0" ]]; then return 1; fi
    else return 1; fi
    echo done.

    compare $1 $script_dir 

    return $?
}

run_tests() { # run all tests in tests/
    tests=`ls -d tests/*/`
    script_dir=`pwd`

    failures=0
    failed=""

    buildImage

    while IFS= read -r variant_dir; do
        
        echo Running test $variant_dir

        prep_mount $variant_dir | indent 2
        if [[ "${PIPESTATUS[0]}" != "0" ]]; then 
            echo "Preparing Mount Failed!" | indent 2
            return 1
        fi
        

        runImage | indent 2
        if [[ "${PIPESTATUS[0]}" != "0" ]]; then 
            failures=$((failures+1)); 
            failed="$failed\n> $variant_dir"
        else
            compare $variant_dir $script_dir | indent 2
            if [[ "${PIPESTATUS[0]}" != "0" ]]; then 
                failures=$((failures+1)); 
                failed="$failed\n> $variant_dir"
            fi
        fi

    done  <<< "$tests"

    if [[ $failures == "0" ]]; then 
        deleteCont
        deleteImage
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
    data_content="{\n    \"submitted_answers\" : {\n        \"student-parsons-solution\": \"\"\n    },\n    \"gradable\": true\n}\n"
    echo -e "$meta_content" >> $1/meta.json
    echo -e "$expected_content" >> $1/expected.json
    echo -e "$data_content" >> $1/data.json


    # return to base directory
    cd ../
    return
}

debug() {
    sudo docker run -it --rm \
        --mount type=bind,source=`pwd`/.container_mount/grade,target=/grade \
        --mount type=bind,source=`pwd`/debug_tools.sh,target=/tools.sh \
        $IMAGE:dev
    return
}
