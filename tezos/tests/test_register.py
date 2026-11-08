"""Registering artworks (floor, unique metadata), retiring a mistaken one, and the history log."""

import smartpy as sp

from deploy.metadata import utf8
from tests.setup import CID, DELAY, T0, at, deploy, ipfs, mint, register, some

NOW = T0 + DELAY


def try_register(env, uri=None, cap=None, mint_end=None, floor=1, sender=None, **kwargs):
    env.collection.register(
        metadata_uri=uri if uri is not None else ipfs(99),
        cap=some(cap),
        mint_end=some(None if mint_end is None else at(mint_end)),
        floor=sp.mutez(floor),
        _sender=sender or env.acc.admin,
        _now=at(NOW),
        **kwargs,
    )


@sp.add_test()
def test_register():
    sc = sp.test_scenario("register")
    env = deploy(sc)
    c = env.collection

    sc.h2("Ids are assigned in order and the metadata is stored as given")
    a = register(env, cap=1, floor=5_000_000)
    b = register(env, cap=None, mint_end=NOW + 10)
    sc.verify(c.data.next_token_id == 2)
    sc.verify(c.data.token_metadata[a].token_info[""] == ipfs(a))
    sc.verify(c.data.editions[a].floor == sp.mutez(5_000_000))
    sc.verify(c.data.editions[b].cap == None)
    sc.verify(c.data.editions[b].mint_end == sp.Some(at(NOW + 10)))
    sc.verify(c.data.supply[a] == 0)
    sc.verify(c.data.uris[ipfs(a)] == a)

    sc.h2("Refused registrations")
    try_register(env, sender=env.acc.stranger, cap=1, _valid=False, _exception="NOT_ADMIN")
    try_register(env, sender=env.acc.guardian, cap=1, _valid=False, _exception="NOT_ADMIN")
    try_register(env, cap=1, floor=0, _valid=False, _exception="FLOOR_ZERO")
    try_register(env, uri=ipfs(a), cap=1, _valid=False, _exception="URI_USED")
    try_register(env, cap=1, _amount=sp.mutez(1), _valid=False, _exception="NO_TEZ")
    try_register(env, cap=0, _valid=False, _exception="CAP_ZERO")
    try_register(env, cap=None, _valid=False, _exception="OPEN_EDITION_NEEDS_END")
    try_register(env, cap=5, mint_end=NOW, _valid=False, _exception="END_IN_PAST")
    try_register(env, uri=utf8("https://example.com/a.json"), cap=1,
                 _valid=False, _exception="NOT_IPFS")
    try_register(env, uri=utf8("ipfs://x"), cap=1, _valid=False, _exception="NOT_IPFS")
    try_register(env, uri=utf8("IPFS://" + CID), cap=1, _valid=False, _exception="NOT_IPFS")
    sc.h3("Only a base32 CIDv1: the same file's CIDv0 or base36 spelling is refused")
    try_register(env, uri=utf8("ipfs://QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"), cap=1,
                 _valid=False, _exception="NOT_IPFS")
    try_register(env, uri=utf8("ipfs://k2k4r8jl0yz8qjgqbmc2cdu5hkqek5rj6flgnlkyywynci20j0iuyfuj"),
                 cap=1, _valid=False, _exception="NOT_IPFS")
    try_register(env, uri=utf8("ipfs://" + CID[:58]), cap=1, _valid=False, _exception="BAD_URI")
    try_register(env, uri=utf8("ipfs://" + CID + "/" + "a" * 190), cap=1,
                 _valid=False, _exception="BAD_URI")
    try_register(env, uri=utf8("ipfs://" + CID), cap=1)
    try_register(env, uri=utf8("ipfs://" + CID + "/" + "a" * 189), cap=1)
    sc.verify(c.data.next_token_id == 4)


@sp.add_test()
def test_retire():
    sc = sp.test_scenario("retire")
    env = deploy(sc)
    c = env.collection
    mistake = register(env, cap=10)
    sold = register(env, cap=10)
    mint(env, sold, 1, env.acc.buyer)

    c.retire(sold, _sender=env.acc.admin, _now=at(NOW), _valid=False, _exception="ALREADY_MINTED")
    c.retire(mistake, _sender=env.acc.stranger, _now=at(NOW), _valid=False, _exception="NOT_ADMIN")
    c.retire(mistake, _sender=env.acc.guardian, _now=at(NOW), _valid=False, _exception="NOT_ADMIN")
    c.retire(mistake, _sender=env.acc.admin, _now=at(NOW))
    c.retire(mistake, _sender=env.acc.admin, _now=at(NOW), _valid=False, _exception="RETIRED")
    sc.verify(~c.data.uris.contains(ipfs(mistake)))
    c.retire(42, _sender=env.acc.admin, _now=at(NOW), _valid=False, _exception="UNKNOWN_TOKEN")
    mint(env, mistake, 1, env.acc.buyer, _valid=False, _exception="RETIRED")

    sc.h2("A retired artwork's metadata link can be registered again, as a new token")
    try_register(env, uri=ipfs(sold), cap=1, _valid=False, _exception="URI_USED")
    try_register(env, uri=ipfs(mistake), cap=3)
    sc.verify(c.data.uris[ipfs(mistake)] == 2)
    sc.verify(c.data.editions[mistake].retired)


@sp.add_test()
def test_history():
    sc = sp.test_scenario("history")
    env = deploy(sc)
    c = env.collection
    art = register(env, cap=1)

    def add(text, uri=None, sender=None, now=NOW, **kwargs):
        c.add_history(token_id=art, text=utf8(text), uri=some(None if uri is None else utf8(uri)),
                      _sender=sender or env.acc.admin, _now=at(now), **kwargs)

    sc.h2("Records append in order, with non-ASCII text, and never touch the metadata")
    add("Exhibited at Musée d'Orsay, Paris", "https://example.com/show")
    add("Published in a magazine — issue 12", now=NOW + 50)
    sc.verify(c.data.editions[art].history_count == 2)
    sc.verify(c.data.history[(art, 0)].text == utf8("Exhibited at Musée d'Orsay, Paris"))
    sc.verify(c.data.history[(art, 1)].added_at == at(NOW + 50))
    sc.verify(c.data.history[(art, 1)].uri == None)
    sc.verify(c.data.token_metadata[art].token_info[""] == ipfs(art))

    sc.h2("Refused records")
    add("x", sender=env.acc.stranger, _valid=False, _exception="NOT_ADMIN")
    add("", _valid=False, _exception="BAD_TEXT")
    add("a" * 501, _valid=False, _exception="BAD_TEXT")
    add("ok", "", _valid=False, _exception="BAD_URI")
    add("ok", "https://" + "h" * 293, _valid=False, _exception="BAD_URI")
    add("ok", "javascript:alert(1)", _valid=False, _exception="BAD_URI")
    add("ok", "http://example.com", _valid=False, _exception="BAD_URI")
    add("ok", "https://", _valid=False, _exception="BAD_URI")
    add("ok", "ipfs://bafyexample")
    add("x", _amount=sp.mutez(1), _valid=False, _exception="NO_TEZ")
    c.add_history(token_id=9, text=utf8("x"), uri=None, _sender=env.acc.admin, _now=at(NOW),
                  _valid=False, _exception="UNKNOWN_TOKEN")
    add("a" * 500)
    sc.verify(c.data.editions[art].history_count == 4)
