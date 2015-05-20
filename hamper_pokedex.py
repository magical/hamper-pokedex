# coding: utf-8

# Copyright 2015 Andrew Ekstedt
# NO WARRANTY. See LICENSE for details.

from hamper import interfaces
import pokedex.db
import pokedex.db.tables as t
import pokedex.lookup

__all__ = ('Plugin',)

class Plugin(interfaces.ChatCommandPlugin):
    name = 'pokedex'

    valid_types = [
        u'pokemon_species',
        u'pokemon_form',
        u'ability',
        u'item',
        u'move',
        u'nature',
        u'type',
    ]

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
            results = self.lookup.lookup(query, valid_types=self.valid_types)
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
            return self.format_pokemon(thing.species, thing)
        if type(thing) is t.PokemonSpecies:
            return self.format_pokemon(thing, thing.default_form)

        if type(thing) is t.Ability:
            return self.format_ability(thing)
        if type(thing) is t.Item:
            return self.format_item(thing)
        if type(thing) is t.Move:
            return self.format_move(thing)
        if type(thing) is t.Nature:
            return self.format_nature(thing)
        if type(thing) is t.Type:
            return self.format_type(thing)

        return thing.name

    def format_pokemon(self, species, form):
        types = u"/".join(type.name for type in form.pokemon.types)
        stats = [
            form.pokemon.base_stat(u'hp'),
            form.pokemon.base_stat(u'attack'),
            form.pokemon.base_stat(u'defense'),
            form.pokemon.base_stat(u'special-attack'),
            form.pokemon.base_stat(u'special-defense'),
            form.pokemon.base_stat(u'speed'),
        ]
        stat_text = u"{0} HP, {1}/{2} physical, {3}/{4} special, {5} speed".format(*stats)
        return u"#{0.id} {0.name}, the {0.genus} Pokémon. {types}-type. {stats}; {total} total.".format(
            species, form, types=types, stats=stat_text, total=sum(stats))

    def format_ability(self, ability):
        return u"{0.name}, an ability. {0.short_effect}".format(ability)

    def format_item(self, item):
        return u"{0.name}, an item. {0.short_effect}".format(item)

    def format_move(self, move):
        if move.power is not None:
            power = "{0.power}".format(move)
        else:
            power = "variable"

        if move.accuracy is not None:
            accuracy = "{0.accuracy}%".format(move)
        else:
            accuracy = "perfect"

        if move.damage_class.identifier == 'status':
            stats = "{0} accuracy".format(accuracy)
        else:
            stats = "{0} power; {1} accuracy".format(power, accuracy)

        return u"{0.name}, a {0.type.name}-type move. {stats}; {0.pp} PP. {0.short_effect}".format(
            move, stats=stats.capitalize())

    def format_nature(self, nature):
        if nature.is_neutral:
            return u"{0.name}, a neutral nature.".format(nature)
        return u"{0.name}, a nature. Raises {0.increased_stat.name}; lowers {0.decreased_stat.name}.".format(nature)

    def format_type(self, type):
        return u"{0.name}, a type.".format(type)


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
            bot.reply(comm, u"Done.")


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
        self.assertEqual(response, u"#25 Pikachu, the Mouse Pokémon. Electric-type. 35 HP, 55/40 physical, 50/50 special, 90 speed; 320 total.")

    def test_lookup_potion(self):
        response = self.do_lookup("potion")
        self.assertEqual(response, u"Potion, an item. Restores 20 HP.")

    def test_lookup_neutral_nature(self):
        response = self.do_lookup("quirky")
        self.assertEqual(response, u"Quirky, a neutral nature.")

    def test_lookup_nature(self):
        response = self.do_lookup("modest")
        self.assertEqual(response, u"Modest, a nature. Raises Special Attack; lowers Attack.")

    def test_lookup_move(self):
        response = self.do_lookup("pound")
        self.assertEqual(response, u"Pound, a Normal-type move. 40 power; 100% accuracy; 35 PP. Inflicts regular damage with no additional effect.")

    def test_lookup_status_move(self):
        response = self.do_lookup("growl")
        self.assertEqual(response, u"Growl, a Normal-type move. 100% accuracy; 40 PP. Lowers the target's Attack by one stage.")

    def test_lookup_variable_move(self):
        response = self.do_lookup("psywave")
        self.assertEqual(response, u"Psywave, a Psychic-type move. Variable power; 100% accuracy; 15 PP. Inflicts damage between 50% and 150% of the user's level.")

    def test_lookup_perfect_accuracy(self):
        response = self.do_lookup("aerial ace")
        self.assertEqual(response, u"Aerial Ace, a Flying-type move. 60 power; perfect accuracy; 20 PP. Never misses.")

    def test_lookup_ability(self):
        response = self.do_lookup("levitate")
        self.assertEqual(response, u"Levitate, an ability. Evades Ground moves.")

    def test_lookup_type(self):
        response = self.do_lookup("grass")
        self.assertEqual(response, u"Grass, a type.")
