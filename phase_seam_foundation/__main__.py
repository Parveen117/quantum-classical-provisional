import json

from .qualification import report

print(json.dumps(report(), indent=2))
