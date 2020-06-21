import sys
import socket
import select
import random
import collections
from new_bank import *

QUANTITY = 0
PRICE = 1
BUILD_MONTH = 2  #

class Server:

    def __init__(self, port):
        self.port = port
        self.srvsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srvsock.bind(("", port))
        self.srvsock.listen(3)
        self.descriptors = [self.srvsock]
        self.plr_num = 0
        self.bank = Bank()
        self.zero_args_coms = {'r', 'end', 'help', 'market', 'm'}
        self.one_args_coms = {'player', 'prod', 'build', 'name', 'player'}
        self.two_args_coms = {'buy', 'sell', }
        self.month = 1
        self.market_lvl = 2  # 0..4
        self.all_buy_queries = []
        self.all_sell_queries = []
        self.init_tables()
        self.set_sources_products()

    def set_sources_products(self):
        """ must be called after bankrupt players were kicked"""
        self.bank.curr_month_sources = self.source_qp[self.market_lvl] * len(self.bank.plrs)
        self.bank.curr_month_products = self.prod_qp[self.market_lvl] * len(self.bank.plrs)

    def init_tables(self):
        self.commands = {'buy': self.buy, 'r': self.ready, 'm': self.market,
                         'sell': self.sell, 'player': self.player, 'name': self.name,
                         'prod': self.prod, 'me': self.me, 'build': self.build}
        self.source_qp = (QuantityPrice(1, 800), QuantityPrice(1.5, 650),
                          QuantityPrice(2, 500), QuantityPrice(2.5, 400),
                          QuantityPrice(3, 300))
        self.prod_qp = (QuantityPrice(3, 6500), QuantityPrice(2.5, 6000),
                        QuantityPrice(2, 5500), QuantityPrice(1.5, 5000),
                        QuantityPrice(1, 4500))
        self.lvl_change_table = (
            (4, 4, 2, 1, 1),
            (3, 4, 3, 1, 1),
            (1, 3, 4, 3, 1),
            (1, 1, 3, 4, 3),
            (1, 1, 2, 4, 4))

    def accum_test(self, accum_buf):
        a = 0
        for i in accum_buf:
            if i == b'8':
                c = i
            a = i

    def delete_backspaced(self, buf):
        while buf.count(8) > 0:
            ind = buf.index(8)
            del buf[ind - 1: ind + 1]

    def run(self):
        while True:
            (sread, swrite, serr) = select.select(self.descriptors, [], [])
            for sock in sread:
                if sock == self.srvsock:  # new user joined
                    self.accept_new_connection()
                else:
                    msg = sock.recv(40)
                    if len(msg) == 0:  # player disconnected
                        host, port = sock.getpeername()
                        self.descriptors.remove(sock)
                        ind = self.get_plr_index(sock)
                        print("{2} has left the game {0}:{1}".format(host, port, self.bank.plrs[ind].name))
                        del self.bank.plrs[ind]
                        self.check_end_turn()
                    else:
                        print(msg)
                        ind = self.get_plr_index(sock)
                        if ind is not None:
                            if b"\r\n" in msg:
                                before_len = len(self.bank.plrs)
                                self.delete_backspaced(self.bank.plrs[ind].msg_accum)
                                self.parse_msg(self.bank.plrs[ind].msg_accum.decode(), sock)
                                curr_len = len(self.bank.plrs)
                                if before_len == curr_len:  # if player was not kicked from the game - clear buffer
                                    print("DEBUG: ", self.bank.plrs[ind].msg_accum)
                                    self.bank.plrs[ind].msg_accum.clear()
                            else:
                                self.bank.plrs[ind].msg_accum += msg

    def parse_msg(self, msg, plr_sock):
        msg = msg.split()
        if len(msg) == 0:
            return
        com_type = msg[0]
        com_args = msg[1:]
        # print("message: ", msg)
        com_func = self.get_com_func(com_type)
        print("command: '", com_type, "',", " args: ", com_args, sep='')
        if com_func is None:
            plr_sock.sendall("\r\nERROR. '{0}': No such command.\r\n".format(com_type).encode())
            return
        ok = self.check_arg_count(com_type, com_args, plr_sock)
        if ok and com_func is not None:
            com_func(plr_sock, *com_args)

    def check_arg_count(self, com_type, com_args, plr_sock):
        if com_type in self.zero_args_coms:
            return True
        elif com_type in self.one_args_coms:
            if len(com_args) >= 1:  # need at least 1 argument
                return True
            else:
                plr_sock.sendall("\r\nError. {0}: need 1 argument\r\n".format(com_type).encode())
                return False
        elif com_type in self.two_args_coms:
            if len(com_args) >= 2:  # need a least 2 arguments
                return True
            else:
                plr_sock.sendall("\r\nError. {0}: need 2 arguments\r\n".format(com_type).encode())
                return False
        return True

    def get_com_func(self, com_type):
        if com_type in self.commands:
            return self.commands[com_type]
        return None

    def fake_buy_sell(self):
        print("fake buy sell()")
        self.sell(self.bank.plrs[0].sock, '2', '4000')
        self.sell(self.bank.plrs[1].sock, '2', '4000')
        self.ready(self.bank.plrs[0].sock)
        self.ready(self.bank.plrs[1].sock)

    def accept_new_connection(self):
        newsock, (remhost, remport) = self.srvsock.accept()
        if not self.bank.game_started:
            newsock.send("Welcome to the hub\r\n".encode())
            self.descriptors.append(newsock)
            print("new player{0} has joined the game.".format(str(self.plr_num)), remhost, remport)
            plr = Player(newsock, "player{0}".format(self.plr_num))
            self.bank.plrs.append(plr)
            self.plr_num += 1
            if self.plr_num == self.bank.max_plrs:
                self.bank.game_started = True
                self.set_sources_products()
                self.broadcast_plrs("game started. Good Luck!\r\n")
                print("{0} players connected. Game started.".format(self.bank.max_plrs))
                # self.fake_buy_sell()
        else:
            newsock.sendall("Sorry, game has already started\r\n".encode())

    def broadcast_plrs(self, line):
        msg = line.encode()
        for plr in self.bank.plrs:
            plr.sock.sendall(msg)

    def get_plr_index(self, sock):
        for ind, plr in enumerate(self.bank.plrs):
            if plr.sock == sock:
                return ind
        return None

    def build(self, plr_sock, *args):
        ind = self.get_plr_index(plr_sock)
        plr = self.bank.plrs[ind]
        try:
            quantity = int(args[QUANTITY])
        except ValueError as err:
            plr_sock.sendall("Wrong argument: build (quantity). {0}\r\n".format(err).encode())
            print("Wrong arguments: build (quantity)")
            return
        if quantity < 0:
            plr_sock.sendall("Wrong arguments: build (quantity)")
            return
        plr.building_fact.append(Factory(quantity, BUILD_MONTH))

    def name(self, plr_sock, new_name, *args):
        if new_name == "":
            plr_sock.sendall("Can't set empty name\r\n".encode())
        lst_same_name = list(filter(lambda x: x.name == new_name, [x for x in self.bank.plrs]))
        print("len same name = ", len(lst_same_name))
        ind = self.get_plr_index(plr_sock)
        if ind is not None:
            print("{0} changed name to '{1}'".format(self.bank.plrs[ind], new_name))
            self.bank.plrs[ind].name = new_name

    def player(self, plr_sock, *args):
        try:
            num = int(args[0])  # from 1 to N, N - current players number in game
        except ValueError as err:
            plr_sock.sendall("Wrong argument: player (player number): {0}\r\n".format(err).encode())
            print("Wrong argument: player (player number)")
            return
        ind = num - 1  #indexing in list: -1
        if not 0 <= ind < len(self.bank.plrs):
            plr_sock.sendall("Wrong argument: no player with such number - {0}\r\n".format(ind).encode())
            return
        print("plr num = ", ind, "len(bank.plrs) = ", len(self.bank.plrs))
        plr = self.bank.plrs[ind]
        msg = """\r\n{0} has:
        \r\nmoney: {1}
        \r\nfactories {2}
        \r\nproducts: {3}
        \r\nsources: {4}\r\n""".format(plr.name, plr.money, plr.fact, plr.product, plr.source)
        plr_sock.sendall(msg.encode())

    def me(self, plr_sock, *args):
        ind = self.get_plr_index(plr_sock)
        self.player(plr_sock, ind + 1)

    def prod(self, plr_sock, *args):
        ind = self.get_plr_index(plr_sock)
        plr = self.bank.plrs[ind]
        try:
            quantity = int(args[QUANTITY])
        except ValueError as err:
            plr_sock.sendall("Wrong arguments: prod (quantity). {0}\r\n".format(err).encode())
            print("Wrong arguments: prod")
            return
        if quantity < 0:
            plr_sock.sendall("ERROR. Wrong number\r\n".encode())
            return
        if plr.source < quantity:
            plr_sock.sendall("ERROR. Not enough sources\r\n".encode())
            return
        plr.produce_cnt = quantity

    def buy(self, plr_sock, *args):
        ind = self.get_plr_index(plr_sock)
        try:
            quantity = int(args[QUANTITY])
            price = int(args[PRICE])
        except ValueError as err:
            plr_sock.sendall("Wrong arguments: buy (quantity) (price). {0}\r\n".format(err).encode())
            print("Wrong arguments: buy (quantity) (price)")
            return
        # if quantity < 10:  # FIXME
        #     plr_sock.sendall("ERROR. Product quantity must be > 0: {0}\r\n".format(quantity).encode())
        #     return
        if quantity < 0:
            plr_sock.sendall("ERROR. Wrong number\r\n".encode())
            return
        if quantity > self.bank.curr_month_sources.quantity:
            plr_sock.sendall("ERROR. Bank has only {0} sources, not {1}\r\n".format(
                self.bank.curr_month_sources.quantity, quantity).encode())
            return
        if price < self.source_qp[self.market_lvl].price:
            plr_sock.sendall("ERROR. Minimum price is {0}\r\n".format(
                self.source_qp[self.market_lvl].price).encode())
            return
        if price > 2500:
            plr_sock.sendall("Buying price is very high. Are you sure?\r\n".encode())
        self.bank.plrs[ind].buy_queries.append(QuantityPrice(quantity, price))
        print("{0} wants to buy {1} for {2}".format(self.bank.plrs[ind], quantity, price))

    def sell(self, plr_sock, *args):
        ind = self.get_plr_index(plr_sock)
        try:
            quantity = int(args[QUANTITY])
            price = int(args[PRICE])
        except ValueError as err:
            plr_sock.sendall("Wrong arguments: buy (quantity) (price). "
                             "err: {0}\r\n".format(err).encode())
            print("Wrong arguments: buy (quantity) (price)")
            return
        if quantity < 1:
            plr_sock.sendall('ERROR. Incorrect product quantity\r\n'.encode())
            return
        if quantity > self.bank.plrs[ind].product:
            plr_sock.sendall("ERROR. You don't have enough products\r\n".encode())
            return
        if price > self.prod_qp[self.market_lvl].price:
            plr_sock.sendall("ERROR. Bank buys for maximum {0}\r\n".format(
                self.prod_qp[self.market_lvl].price).encode())
            return
        self.bank.plrs[ind].sell_queries.append(QuantityPrice(quantity, price))
        print("{0} wants to sell {1} for {2}\r\n".format(self.bank.plrs[ind], quantity, price))


    def market(self, plr_sock, *args):
        msg = """\r\nCurrent month is {0}
        \r\nPlayers still in game: {1}
        \r\nbank buys {2} for {3}
        \r\nbank sells {4} for {5}
        \r\n\r\n""".format(self.month, len(self.bank.plrs),
                   self.bank.curr_month_products.quantity, self.bank.curr_month_products.price,
                   self.bank.curr_month_sources.quantity, self.bank.curr_month_sources.price)
        plr_sock.sendall(msg.encode())

    def ready(self, plr_sock, *args):
        ind = self.get_plr_index(plr_sock)
        self.bank.plrs[ind].ready = True
        plr_sock.sendall("\r\nREADY\r\n".encode())
        self.check_end_turn()

    def check_end_turn(self):
        ready_arr = (x.ready for x in self.bank.plrs)
        if all(ready_arr):
            self.end_turn()

    def kick_bankrupt_plrs(self):
        to_remove = []
        for plr in self.bank.plrs:
            if plr.money < 0:
                plr.sock.sendall("Game over! Good buy.".encode())
                plr.sock.close()
                self.descriptors.remove(plr.sock)
                to_remove.append(plr)
                print(plr.name, "was kicked from the game")
        for plr in to_remove:
            self.bank.plrs.remove(plr)

    def check_winner(self):
        if len(self.bank.plrs) == 1:
            plr_sock = self.bank.plrs[0].sock
            plr_sock.sendall("Congratulations! You won.".encode())
            for sock in self.descriptors:
                sock.close()
            print("{0} won.".format(self.bank.plrs[0].name))
            sys.exit(0)
        if len(self.bank.plrs) == 0:
            self.descriptors[0].close()
            print("All players lost. Game over.")
            sys.exit(0)

    def collect_plrs_queries(self, all_buy_queries, all_sell_queries):
        for plr in self.bank.plrs:
            ind = self.get_plr_index(plr.sock)
            for query in plr.buy_queries:
                all_buy_queries.append(Query(BUY, ind, query))
            for query in plr.sell_queries:
                all_sell_queries.append(Query(SELL, ind, query))
            plr.buy_queries.clear()
            plr.sell_queries.clear()

    def indexies_with_eq_price(self, all_queries):
        """ returns indexies with equal prices includingly, quantity with equal price"""
        if len(all_queries) == 0:
            return
        i = 0
        end_ind = 0
        eq_price_total = all_queries[0].qp.quantity
        while i < len(all_queries) - 1:
            if all_queries[i].qp.price == all_queries[i+1].qp.price:
                end_ind += 1
                eq_price_total += all_queries[i+1].qp.quantity
            i += 1
        return 0, end_ind, eq_price_total

    def satisfy_all(self, queries):
        for query in queries:
            self.satisfy_query(query)

    def satisfy_partially(self, queries, bank_qp):
        print("satisfy_partially")
        query = random.choice(queries)
        query.qp.quantity = bank_qp.quantity  # satisfy only the number that the bank has
        self.satisfy_query(query)

    def satisfy_randomly(self, queries, bank_qp):
        while bank_qp.quantity > 0:
            query = random.choice(queries)
            if query.qp.quantity <= bank_qp.quantity:
                self.satisfy_query(query)
                bank_qp.quantity -= query.qp.quantity
                queries.remove(query)
            else:
                self.satisfy_partially(queries, bank_qp)  # all queries satisfied, nothing to do
                return

    def satisfy(self, all_queries, bank_qp):
        if len(all_queries) == 0:
            return
        if bank_qp.quantity > 0:
            min_ind, max_ind, eq_price_total = self.indexies_with_eq_price(all_queries)
            print('equal price: ', min_ind, max_ind, eq_price_total)
            if eq_price_total <= bank_qp.quantity:
                self.satisfy_all(all_queries[min_ind:max_ind + 1])  # max_ind includingly
                del all_queries[min_ind:max_ind + 1]
            else:
                self.satisfy_randomly(all_queries[min_ind:max_ind + 1], bank_qp)
                all_queries.clear() # all queries satisfied, nothing to do
                return

    def auction(self):
        all_buy_queries = []
        all_sell_queries = []
        self.collect_plrs_queries(all_buy_queries, all_sell_queries)
        all_buy_queries.sort(key=lambda x: x.qp.price)
        all_sell_queries.sort(key=lambda x: x.qp.price)
        print("all_buy_queries: {0!r}".format(all_buy_queries))
        # self.bank.curr_month_products
        # curr_month_sources
        self.satisfy(all_buy_queries, self.bank.curr_month_sources)
        self.satisfy(all_sell_queries, self.bank.curr_month_products)

        # for query in self.all_buy_queries:
        #     self.satisfy_query(query)
        # for query in self.all_sell_queries:
        #     self.satisfy_query(query)

    def satisfy_query(self, query):
        plr = self.bank.plrs[query.ind]
        if query.buy_sell == BUY:
            plr.money = plr.money - query.qp.quantity * query.qp.price
            plr.source += query.qp.quantity
        else:
            plr.money = plr.money + query.qp.quantity * query.qp.price
            plr.product -= query.qp.quantity
        print("{4} satisfied. {0} now has {1} money, {2} products, {3} sources".format(
            plr.name, plr.money, plr.product, plr.source, query.qp.quantity))

    def remove_expenses(self):
        for plr in self.bank.plrs:
            plr.money -= 1000 * plr.fact + 500 * plr.product + 300 * plr.source

    def make_products(self):
        for plr in self.bank.plrs:
            if plr.produce_cnt == 0:
                continue
            plr.money -= 1000 * plr.produce_cnt
            plr.product += plr.produce_cnt
            plr.produce_cnt = 0

    def end_turn(self):
        self.month += 1
        self.remove_expenses()  # FIXME поправить, не снимать издержки с проданных продуктов
        self.auction()
        self.make_products()
        self.build_factories()
        self.kick_bankrupt_plrs()
        self.check_winner()
        self.change_market_lvl()
        self.set_sources_products()
        print("turn ended. Current month is {0}\n".format(self.month))
        self.broadcast_plrs("turn ended. Current month is {0}\r\n".format(self.month))
        for plr in self.bank.plrs:
            plr.ready = False

    def change_market_lvl(self):
        """ must be called after bankrupt players were kicked"""
        new_lvl = 0
        r = random.randint(1, 12)
        print("current market is {0}".format(self.market_lvl), end='. ')
        for ind, item in enumerate(self.lvl_change_table[self.market_lvl]):
            new_lvl += item
            if new_lvl >= r:
                break
        self.market_lvl = ind
        print("new market lvl is {0}".format(self.market_lvl))

    def build_factories(self):
        for plr in self.bank.plrs:
            for fact in plr.building_fact:
                if fact.months_left != 1:
                    fact.months_left -= 1
                else:  # new factories are builded
                    plr.fact += fact.quantity
                    del fact


PORT = 7878
HOST = '127.0.0.1'

if __name__ == "__main__":
    print("Management game simulator.")
    srv = Server(PORT)
    srv.run()