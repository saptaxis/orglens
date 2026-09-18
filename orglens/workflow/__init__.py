"""Workflow: a linear workflow engine.

A workflow is an ordered list of nodes, each naming a program and the one file it
writes. A packet is a directory holding those files. The packet's session is
an append-only log; where the workflow stands is derived from the log's last
routing fact and never stored. A gate is a finished node whose question has
no answer yet.

The engine opens two files, the workflow's `WORKFLOW.yaml` and the packet's
`session.jsonl`, and never an artifact or a program. It names the program to run
and stands back; whoever is at the packet performs it.
"""
