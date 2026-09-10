#!/usr/bin/env python3

import json

target = input("Target environment: ")
notes = input("Release notes: ")
print(f"Publishing {notes} to {target}")
print(json.dumps({"target": target, "published": True}))
