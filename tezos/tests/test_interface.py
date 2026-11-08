"""The compiled contracts expose exactly the planned entry points and views.

Nothing else: no way to change token or contract metadata, to pause or move
anyone's tokens, or to withdraw tez.
"""

import json
import os

import smartpy as sp

from deploy.interface import (
    COLLECTION_ENTRYPOINTS, COLLECTION_VIEWS, PAYOUT_ENTRYPOINTS, PAYOUT_VIEWS, SALE_ENTRYPOINTS,
    SALE_VIEWS, entrypoints, views,
)
from tests.setup import deploy


def compiled(scenario_dir, contract_index):
    suffix = "_cont_%d_contract.json" % contract_index
    name = [f for f in os.listdir(scenario_dir) if f.endswith(suffix)][0]
    with open(os.path.join(scenario_dir, name)) as handle:
        return json.load(handle)


@sp.add_test()
def test_interface():
    sc = sp.test_scenario("interface")
    deploy(sc, confirm_minter=False)

    problems = []
    for label, index, want_eps, want_views in [
        ("payout", 0, PAYOUT_ENTRYPOINTS, PAYOUT_VIEWS),
        ("collection", 1, COLLECTION_ENTRYPOINTS, COLLECTION_VIEWS),
        ("sale", 2, SALE_ENTRYPOINTS, SALE_VIEWS),
    ]:
        code = compiled("interface", index)
        if entrypoints(code) != want_eps:
            problems.append("%s entry points: %s" % (label, sorted(entrypoints(code) ^ want_eps)))
        if views(code) != want_views:
            problems.append("%s views: %s" % (label, sorted(views(code) ^ want_views)))
    if problems:
        raise AssertionError("; ".join(problems))
    print("interface ok")
