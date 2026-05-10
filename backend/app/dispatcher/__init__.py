"""Reward dispatcher.

Per `docs/dispatcher.md`: every observation submission runs through here
after the row is committed. Each registered Handler may emit Rewards; the
dispatcher catches per-handler exceptions so one broken handler never
fails the submission. Handlers run sequentially in the order defined by
`registry.HANDLERS`.
"""
