"""Chain: a linear workflow engine.

A deck is an ordered list of stages, each naming a card and the one file it
writes. A packet is a directory holding those files. The packet's session is
an append-only log; where the chain stands is derived from the log's last
routing fact and never stored. A gate is a finished stage whose question has
no answer yet.

The engine opens two files, the deck's `CHAIN.yaml` and the packet's
`session.jsonl`, and never an artifact or a card. It names the card to run
and stands back; whoever is at the packet performs it.
"""
