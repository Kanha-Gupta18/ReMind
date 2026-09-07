"""AI pipeline simulators + conversational agent (spec §18, §21).

In the professor's roadmap the backend integrates real ML services. For
v1 these modules stand in for them with deterministic, auditable
simulators that produce the exact same data shapes a real extractor
would, so the entire system (pipeline, graph, confidence engine,
conversation agent) runs end-to-end without model weights.
"""
