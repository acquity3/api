from copy import deepcopy

import networkx as nx
from networkx.algorithms.matching import max_weight_matching


def match_buyers_and_sellers(buy_orders, sell_orders, banned_user_matches):
    """
    The matching algorithm.

    Currently, this operates on the assumption that all securities passed in are the same.

    Params:
    buy_orders: e.g. [{'id': 'UUID', 'user_id': 'UUID', 'security_id': 'UUID',
                       'number_of_shares': 20.0, 'price': 30.0}]
    sell_orders: e.g. [{'id': 'UUID', 'user_id': 'UUID', 'security_id': 'UUID',
                        'number_of_shares': 20.0, 'price': 30.0}]
    banned_user_matches: users that cannot be matched together. Pass in enumerable of pairs.
    e.g. set(('buyer_uuid', 'seller_uuid'), ('buyer2_uuid', 'seller2_uuid'))

    Returns:
    Set of pairs of order IDs as matches.
    e.g. set(('buy_order_uuid', 'sell_order_uuid'),
             ('buy_order2_uuid', 'sell_order2_uuid'))
    """

    max_number_of_shares = max(o["number_of_shares"] for o in buy_orders + sell_orders)
    buy_orders_copy = deepcopy(buy_orders)
    sell_orders_copy = deepcopy(sell_orders)

    first_iteration = match_seller_with_nearest_buyer(
        buy_orders_copy, sell_orders_copy, banned_user_matches, max_number_of_shares
    )

    matched_buy_order_ids = {
        buy_order_id for buy_order_id in [p[0] for p in first_iteration]
    }
    remaining_buy_orders = []
    for buy_order in buy_orders_copy:
        if buy_order["id"] not in matched_buy_order_ids:
            remaining_buy_orders.append(buy_order)

    subsequent = distribute_remaining_buyers(
        remaining_buy_orders, sell_orders_copy, banned_user_matches
    )

    return first_iteration | subsequent


def match_seller_with_nearest_buyer(
    buy_orders, sell_orders, banned_user_matches, max_number_of_shares
):
    def get_cost(buy_order, sell_order):
        if buy_order["price"] < sell_order["price"] or (
            (buy_order["user_id"], sell_order["user_id"]) in banned_user_matches
        ):
            return None
        return abs(
            buy_order["price"] - sell_order["price"]
        ) * max_number_of_shares * 2 + abs(
            buy_order["number_of_shares"] - sell_order["number_of_shares"]
        )

    graph = nx.Graph()
    for sell_order in sell_orders:
        for buy_order in buy_orders:
            cost = get_cost(buy_order, sell_order)
            if cost is not None:
                # Invert the cost, since the algorithm computes the maximum total instead of the
                # minimum
                graph.add_edge(buy_order["id"], sell_order["id"], weight=-cost)

    matching = max_weight_matching(graph, maxcardinality=True)

    buy_order_ids = {buy_order["id"] for buy_order in buy_orders}

    result = set()
    for pair in matching:
        buy_order_id = pair[0] if pair[0] in buy_order_ids else pair[1]
        sell_order_id = pair[1] if pair[0] in buy_order_ids else pair[0]
        result.add((buy_order_id, sell_order_id))

    return result


def distribute_remaining_buyers(buy_orders, sell_orders, banned_user_matches):
    """
    NOTE: Mutates buy_orders by removing those that are matched.
    """

    def cmp(sell_order, buy_order):
        return (
            -buy_order["price"],  # most desperate: greatest price
            abs(sell_order["number_of_shares"] - buy_order["number_of_shares"]),
        )

    result = set()

    # Sort by most --> least desperate: increasing price, then decreasing number of shares
    sorted_sell_orders = sorted(
        sell_orders, key=lambda o: (o["price"], -o["number_of_shares"])
    )

    while len(sorted_sell_orders) > 0:
        unmatched_sell_orders = []

        for sell_order in sorted_sell_orders:
            eligible_buy_orders = [
                buy_order
                for buy_order in buy_orders
                if (buy_order["price"] >= sell_order["price"])
                and (
                    (buy_order["user_id"], sell_order["user_id"])
                    not in banned_user_matches
                )
            ]

            if len(eligible_buy_orders) == 0:
                unmatched_sell_orders.append(sell_order)
                continue

            buy_order = min(eligible_buy_orders, key=lambda o: cmp(sell_order, o))
            result.add((buy_order["id"], sell_order["id"]))
            buy_orders.remove(buy_order)

        for sell_order in unmatched_sell_orders:
            sorted_sell_orders.remove(sell_order)

    return result
