# coding: utf-8
from hamper import interfaces
import pokedex.db
import pokedex.db.tables as t
import pokedex.lookup
import sqlalchemy
from sqlalchemy import orm

Session = orm.sessionmaker()

__all__ = ('Plugin',)

class Plugin(interfaces.ChatCommandPlugin):
    name = 'pokedex'
    def setup(self, loader):
        interfaces.ChatCommandPlugin.setup(self, loader)

        self.config = loader.config.get("pokedex", {})
        uri = self.config.get('db')
        self.session = pokedex.db.connect(uri)

        lookup_dir = self.config.get('lookup')
        self.lookup = pokedex.lookup.PokedexLookup(
            directory=lookup_dir,
            session=self.session,
        )

    def do_lookup(self, bot, comm, query):
        if type(query) is str:
            query = query.decode('utf-8', 'replace')
        try:
            results = self.lookup.lookup(query)
        except pokedex.lookup.UninitializedIndex.UninitializedIndexError:
            return bot.reply(comm, u"error: the lookup index does not exist. type !reindex to create it.")

        if len(results) == 0:
            return bot.reply(comm, u"I don't know what that is")

        if len(results) > 1:
            suggestions = []
            for r in results:
                suggestions.append(r.name)
            return bot.reply(comm, u"did you mean {0}", vars=[", ".join(suggestions)])

        thing = results[0].object
        bot.reply(comm, u"{0}", vars=[self.format_thing(thing)])

    def format_thing(self, thing):
        if type(thing) is t.PokemonForm:
            return self.format_pokemon_form(thing)
        if type(thing) is t.PokemonSpecies:
            return self.format_pokemon_species(thing)
        if type(thing) is t.Ability:
            return self.format_ability(thing)
        if type(thing) is t.Move:
            return self.format_move(thing)
        if type(thing) is t.Item:
            return self.format_item(thing)
        if type(thing) is t.Type:
            return self.format_item(thing)
        return thing.name

    def format_pokemon_form(self, form):
        return self.format_pokemon_species(form.species)
        
    def format_pokemon_species(self, species):
        return u"#{0.id} {0.name}, the {0.genus} Pokémon.".format(species)
    
    def format_item(self, item):
        return u"{0.name}, an item".format(item)

    def format_ability(self, ability):
        return u"{0.name}, an ability".format(ability)

    def format_move(self, move):
        return u"{0.name}, a move".format(move)

    def format_type(self, type):
        return u"{0.name}, a type".format(type)
    
    class Dex(interfaces.Command):
        name = 'pokedex'
        regex = '(?:dex|pokedex)(?: (.*)|$)'

        def command(self, bot, comm, groups):
            if not groups or not groups[0]:
                return bot.reply(comm, u"Please specify a pokemon to look up")

            query = groups[0].strip()
            self.plugin.do_lookup(bot, comm, query)
            
    class Reindex(interfaces.Command):
        name = 'reindex'
        regex = 'reindex'
        short_desc = u'reindex - rebuilds the pokedex search index'

        def command(self, bot, comm, groups):
            self.plugin.lookup.rebuild_index()
            bot.reply(comm, u"Done")

import unittest
import io

class MockLoader:
    config = {}

class MockBot:
    def __init__(self):
        self.response = io.StringIO()

    def reply(self, comm, message, vars=[], kwvars={}):
        message = message.format(*vars, **kwvars)
        self.response.write(message)

class HamperPokedexTests(unittest.TestCase):
    def setUp(self):
        # TODO: db configuration
        self.loader = MockLoader()
        self.plugin = Plugin()
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
