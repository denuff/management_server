__all__ = ["Bank", "Query", "Player", "QuantityPrice", "BUY", "SELL", "Factory"]
import math

BUY = -1
SELL = 1

class QuantityPrice:

    def __init__(self, quantity=0, price=0):
        self.quantity = quantity
        self.price = price

    def __mul__(self, other):
        return QuantityPrice(math.trunc(self.quantity * other), self.price)

    def __str__(self):
        return "({0}, {1})".format(self.quantity, self.price)

    def __repr__(self):
        return "{0.__class__.__name__}({0.quantity}, {0.price})".format(self)

class Query:

    def __init__(self, buy_sell, ind, qp):
        self.buy_sell = buy_sell
        self.ind = ind
        self.qp = qp

    def __str__(self):
        return "({0.buy_sell}, {0.index}, {0.qp})".format(self)

    def __repr__(self):
        return "Query({0.buy_sell}, {0.ind}, {0.qp})".format(self)


class Player:
    def __init__(self, sock, name=""):
        self.sock = sock
        self.name = name
        self.money = 20000
        self.product = 2
        self.source = 4
        self.fact = 2
        self.produce_cnt = 0  # prod command
        self.msg_accum = bytearray()
        self.ready = False
        self.buy_queries = []  # player query for buying sources: quantity and price
        self.sell_queries = []  # player query for selling products: quantity and price
        self.building_fact = []

    def __str__(self):
        return self.name

    def __repr__(self):
        return str(self)


class Bank:

    def __init__(self, max_plrs=2):
        self.game_started = False
        self.plrs = []
        self.max_plrs = max_plrs
        self.curr_month_sources = None
        self.curr_month_products = None

class Factory:

    def __init__(self, quantity, months_left):  # quantity of factories, months left for building
        self.quantity = quantity
        self.months_left = months_left
