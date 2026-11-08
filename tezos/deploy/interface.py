"""Read a compiled contract's entry points and views from its Micheline JSON."""

CONTROL = {
    "propose_admin", "cancel_admin", "accept_admin",
    "propose_guardian", "cancel_guardian", "accept_guardian",
}

COLLECTION_ENTRYPOINTS = CONTROL | {
    "add_history", "balance_of", "burn", "mint", "register", "retire", "transfer",
    "update_operators", "propose_minter", "cancel_minter", "confirm_minter",
    "remove_minter",
}
COLLECTION_VIEWS = {"edition", "get_balance_of"}

PAYOUT_ENTRYPOINTS = CONTROL | {
    "default", "propose_payout", "cancel_payout", "accept_payout",
}
PAYOUT_VIEWS = set()

SALE_ENTRYPOINTS = CONTROL | {"buy", "remove_sale", "set_paused", "set_sale", "set_sale_paused"}
SALE_VIEWS = set()


def _section(code, prim):
    return [part for part in code if part["prim"] == prim]


def entrypoints(code):
    """The %annotated branches of the parameter's `or` tree."""
    found = []

    def walk(node):
        for annot in node.get("annots", []):
            if annot.startswith("%"):
                found.append(annot[1:])
                return
        if node.get("prim") == "or":
            for arg in node["args"]:
                walk(arg)

    walk(_section(code, "parameter")[0]["args"][0])
    return set(found)


def views(code):
    return {view["args"][0]["string"] for view in _section(code, "view")}
