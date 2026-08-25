"""DevStat Teaching mode — guided, authored lessons that walk a learner through
a real medical-statistics workflow using a bundled synthetic RCT dataset.

Scenarios are plain Python data (no LLM): each is a list of steps. The frontend
renders each step kind and, for 'run' steps, actually executes the analysis via
the normal backend endpooints (with the teaching flag set so it is free but
still requires a sign-in).
"""
