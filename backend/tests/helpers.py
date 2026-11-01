import asyncio
import json

from app.evaluation.models import Claim, Source

TOWER = Source("S1", "The Eiffel Tower was completed in 1889. It is located in Paris, France. "
                     "The tower is 330 metres tall.", "Sample encyclopedia entry")


def run(coro):
    return asyncio.run(coro)


async def _no_sleep(_):
    return None


def verdict(claim_id, classification, supporting=(), contradicting=(), reasoning="because", confidence=None):
    return json.dumps({"claim_id": claim_id, "classification": classification,
                       "supporting": [{"source_id": s, "excerpt": e} for s, e in supporting],
                       "contradicting": [{"source_id": s, "excerpt": e} for s, e in contradicting],
                       "reasoning": reasoning, "confidence": confidence})


CLAIM = Claim("C1", "The Eiffel Tower was completed in 1889.", 0)
