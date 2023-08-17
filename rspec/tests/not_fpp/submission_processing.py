from base64 import b64decode

def prepSubmission(data, ROOT_DIR, SUBMISSION_DIR):
    files = data['submitted_answers']['_files']
    contents = [ str(b64decode(f['contents']), "utf-8") for f in files ]
    assert all(map(lambda potential_string: isinstance(potential_string, str), contents))
    content = "\n".join(contents)
    with open(f"{SUBMISSION_DIR}/_submission_file", 'w') as sub:
        sub.write( content )
    return
