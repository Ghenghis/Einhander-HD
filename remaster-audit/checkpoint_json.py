"""Atomic authoring checkpoints that tolerate brief Windows reader locks."""
import json
import os
import time


def write_json(path, data):
    temporary = path.with_name(path.name+f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    deadline = time.monotonic()+5
    delay = .025
    while True:
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay*2, .25)
