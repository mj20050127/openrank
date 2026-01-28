"""Skill base class (placeholder)"""

class Skill:
    name: str = "base"

    def run(self, query: str, ctx: dict):
        raise NotImplementedError
