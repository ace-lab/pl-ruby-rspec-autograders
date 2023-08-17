from base64 import b64decode
from typing import Dict

def get_submission(data: Dict) -> str:
    """Extract the file contents of `script.rb` in a student submission"""
    contents = next(
        ( file['contents'] for file in data['submitted_answers']["_files"] if file['name'] == 'script.rb' ),
        ""
    )
    return str(b64decode(contents), "utf-8")
