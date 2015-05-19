# coding: utf-8

import unittest
import hamper_pokedex
import pokedex.db
import pokedex.db.tables as t
import io

class MockLoader:
    config = {}


class MockBot:
    def __init__(self):
        self.response = io.StringIO()
    
    def reply(self, comm, message, vars=[], kwvars={}):
        message = message.format(*vars, **kwvars)
        self.response.write(message)

class PokedexTests(unittest.TestCase):
    def setUp(self):
        # TODO: db configuration
        self.loader = MockLoader()
        self.plugin = hamper_pokedex.Plugin()
        self.plugin.setup(self.loader)
        self.bot = MockBot()

    def do_lookup(self, query):
        self.plugin.do_lookup(self.bot, {}, query)
        return self.bot.response.getvalue()

    def test_lookup_pikachu(self):
        response = self.do_lookup("pikachu")
        self.assertEqual(response, u"#25 Pikachu, the Mouse Pokémon.")

    def test_lookup_potion(self):
        response = self.do_lookup("potion")
        self.assertEqual(response, u"Potion, an item")
