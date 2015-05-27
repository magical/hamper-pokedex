# coding: utf-8

# Copyright 2015 Andrew Ekstedt
# NO WARRANTY. See LICENSE for details.

from collections import defaultdict
import urllib

from hamper import interfaces
import pokedex.db
import pokedex.db.tables as t
import pokedex.lookup
from sqlalchemy import sql

__all__ = ('Plugin',)

# TODO: Something more declarative
def red(s):    return u"\x0304"+s+u"\x0F"
def purple(s): return u"\x0306"+s+u"\x0F"
def orange(s): return u"\x0307"+s+u"\x0F"
def yellow(s): return u"\x0308"+s+u"\x0F"
def lime(s):   return u"\x0309"+s+u"\x0F"
def cyan(s):   return u"\x0311"+s+u"\x0F"
def blue(s):   return u"\x0312"+s+u"\x0F"
def pink(s):   return u"\x0313"+s+u"\x0F"

def color(n):
    if n < .15:
        return purple
    if n < .30:
        return blue
    if n < .45:
        return cyan
    if n < .60:
        return lime
    if n < .75:
        return yellow
    if n < .90:
        return orange
    return red

class Help:
    def __init__(self, name, short_desc, long_desc=u""):
        self.name = name
        self.short_desc = short_desc
        self.long_desc = long_desc

class Trigger:
    def __init__(self, regex, cmd, directed=True):
        self.regex = regex
        self.cmd = cmd
        self.directed = directed

class Plugin(interfaces.ChatPlugin):
    name = 'pokedex'

    # Base URL for spline-pokedex.
    # In case you wanted to run your own instance, i guess.
    base_url = u"http://veekun.com/dex"

    # The version group to use for level-up moves.
    current_version_group = u'x-y'

    # What types of things do we want to search for?
    valid_types = [
        u'pokemon_species',
        u'pokemon_form',
        u'ability',
        u'item',
        u'move',
        u'nature',
        u'type',
    ]

    gender_ratio_text = {
        -1: u"Genderless",

        0: blue(u"Male♂")+u" only",
        8: pink(u"Female♀")+u" only",
        1: u"Predominantly "+blue(u"male♂")+u" (7:1)",
        7: u"Predominantly "+pink(u"female♀")+u" (7:1)",
        2: u"Mostly "+blue(u"male♂")+u" (3:1)",
        6: u"Mostly "+pink(u"female♀")+u" (3:1)",
        3: u"⅜ female♀, ⅝ male♂", # never occurs
        5: u"⅝ female♀, ⅜ male♂", # never occurs
        4: u"Half "+pink(u"female♀")+u", half "+blue(u"male♂"),

        # Other options that were considered:
        #
        #     Fractions: 1/8 female, 7/8 male
        #
        #     Unicode fractions: ⅛ female, ⅞ male
        #
        #     Ratio: 1 ♀ : 7 ♂
        #
        #     Bar chart: ♀♀♀♀♀♀♀♂
    }

    def setup(self, loader):
        self.commands = [] # actually help, for the help plugin
        self.triggers = [] # commands

        self.config = loader.config.get("pokedex", {})
        uri = self.config.get('db')
        self.session = pokedex.db.connect(uri)

        lookup_dir = self.config.get('lookup')
        self.lookup = pokedex.lookup.PokedexLookup(
            directory=lookup_dir,
            session=self.session,
        )

        self.add_help(u'dex', u'pokedex or dex [name] - looks up info about a pokemon, move, or item')
        self.add_help(u'reindex', u'reindex - rebuilds the pokedex search index')
        self.add_help(u'levelup', u'levelup [pokemon] - show level-up moves for a pokemon')

        self.add_trigger(ur'reindex$', self.cmd_reindex)
        self.add_trigger(ur'(?:dex|pokedex)(?:| (.*))$', self.cmd_lookup)
        self.add_trigger(ur'levelup(?:| (.*))$', self.cmd_levelup)

    def add_help(self, name, short_desc, long_desc=u""):
        self.commands.append(Help(name, short_desc, long_desc))

    def add_trigger(self, regex, cmd):
        if isinstance(regex, basestring):
            regex = re.compile(regex, re.IGNORECASE)
        self.triggers.append(Trigger(regex, cmd))

    def message(self, bot, comm):
        if not comm['directed']:
            return False
        for trigger in self.triggers:
            m = trigger.regex.match(comm['message'])
            if m is not None:
                trigger.cmd(bot, comm, m.groups())
                return True
        return False

    def cmd_reindex(self, bot, comm, groups):
        self.lookup.rebuild_index()
        bot.reply(comm, u"Done.")

    def _lookup(self, bot, comm, query):
        if type(query) is str:
            query = query.decode('utf-8', 'replace')
        elif query is None:
            query = u""

        query = query.strip()

        if not query:
            bot.reply(comm, u"please specify a pokemon to look up")
            return None

        try:
            results = self.lookup.lookup(query, valid_types=self.valid_types)
        except pokedex.lookup.UninitializedIndex.UninitializedIndexError:
            bot.reply(comm, u"error: the lookup index does not exist. type !reindex to create it.")
            return None

        if len(results) == 0:
            bot.reply(comm, u"I don't know what that is")
            return None

        if len(results) > 1:
            suggestions = []
            for r in results:
                suggestions.append(r.name)
            bot.reply(comm, u"did you mean {0}", vars=[", ".join(suggestions)])
            return None

        return results[0].object

    def cmd_lookup(self, bot, comm, groups):
        query, = groups
        thing = self._lookup(bot, comm, query)
        if thing:
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
        template = (
            u"#{0.id} {1.pokemon.name}, the {0.genus} Pokémon.  {types}-type.  {gender_ratio}.  " +
            u"Has {abilities}.  " +
            u"{stats}; {total} total.  " +
            u"Egg groups: {egg_groups}.  Hatch counter: {0.hatch_counter}.  " +
            u"{url}"
        )
        extra = {}

        q = self.session.query(t.PokemonStat).join(t.Stat)
        stat_idents = [u'hp', u'attack', u'defense', u'special-attack', u'special-defense', u'speed']
        stats = [form.pokemon.base_stat(ident) for ident in stat_idents]
        percentiles = [get_percentile(q.filter(t.Stat.identifier == ident), t.PokemonStat.base_stat, stat)
                       for ident, stat in zip(stat_idents, stats)]
        colored_stats = [color(pct)(unicode(stat)) for pct, stat in zip(percentiles, stats)]
        total_subquery = q.filter(~t.Stat.is_battle_only).group_by(t.PokemonStat.pokemon_id)\
            .with_entities(sql.func.sum(t.PokemonStat.base_stat).label('base_stat_total')).subquery()
        total_percentile = get_percentile(
            self.session.query(total_subquery),
            total_subquery.c.base_stat_total,
            sum(stats),
        )
        #print(percentiles)
        #print(total_percentile)

        extra["types"] = u"/".join(type.name for type in form.pokemon.types)
        extra["abilities"] = u" or ".join(ability.name for ability in form.pokemon.abilities)
        extra["stats"] = u"{0} HP, {1}/{2} physical, {3}/{4} special, {5} speed".format(*colored_stats)
        extra["total"] = color(total_percentile)(unicode(sum(stats)))
        extra["gender_ratio"] = self.gender_ratio_text[species.gender_rate]
        extra["egg_groups"] = namelist(species.egg_groups, u" and ")

        url = urljoin(self.base_url, u"pokemon", species.name.lower())
        if not form.pokemon.is_default:
            url += u"?form=" + urlquote(form.form_identifier)
        extra["url"] = url

        return template.format(species, form, **extra)

    def format_ability(self, ability):
        url = urljoin(self.base_url, u"abilities", ability.name.lower())
        return u"{0.name}, an ability. {0.short_effect} {url}".format(ability, url=url)

    def format_item(self, item):
        url = urljoin(self.base_url, u"items", item.pocket.identifier, item.name.lower())
        return u"{0.name}, an item. {0.short_effect} {url}".format(item, url=url)

    def format_move(self, move):
        if move.power is not None:
            power = u"{0.power}".format(move)
        else:
            power = u"variable"

        if move.accuracy is not None:
            accuracy = u"{0.accuracy}%".format(move)
        else:
            accuracy = u"perfect"

        if move.damage_class.identifier == 'status':
            stats = u"{0} accuracy".format(accuracy)
        else:
            stats = u"{0} power; {1} accuracy".format(power, accuracy)

        url = urljoin(self.base_url, u"moves", move.name.lower())
        return u"{0.name}, a {0.type.name}-type move. {stats}; {0.pp} PP. {0.short_effect} {url}".format(
            move, stats=stats.capitalize(), url=url)

    def format_nature(self, nature):
        if nature.is_neutral:
            template = u"{0.name}, a neutral nature. {url}"
        else:
            template = u"{0.name}, a nature. Raises {0.increased_stat.name}; lowers {0.decreased_stat.name}. {url}"
        url = urljoin(self.base_url, u"natures", nature.name.lower())
        return template.format(nature, url=url)

    def format_type(self, type):
        damage_taken = defaultdict(list)
        damage_given = defaultdict(list)
        for efficacy in type.damage_efficacies:
            damage_given[efficacy.damage_factor].append(efficacy.target_type)
        for efficacy in type.target_efficacies:
            damage_taken[efficacy.damage_factor].append(efficacy.damage_type)

        del damage_taken[100]
        del damage_given[100]

        text = u""
        if damage_given:
            clauses = []
            if damage_given[200]:
                clauses.append(u"2× to " + namelist(damage_given[200]))
            if damage_given[50]:
                clauses.append(u"½× to " + namelist(damage_given[50]))
            if damage_given[0]:
                clauses.append(u"0× to " + namelist(damage_given[0]))
            text += u".  Deals " + u"; ".join(clauses)

        if damage_taken:
            clauses = []
            if damage_taken[200]:
                clauses.append(u"2× from " + namelist(damage_taken[200]))
            if damage_taken[50]:
                clauses.append(u"½× from " + namelist(damage_taken[50]))
            if damage_taken[0]:
                clauses.append(u"0× from " + namelist(damage_taken[0]))
            text += u".  Takes " + u"; ".join(clauses)

        url = urljoin(self.base_url, u"types", type.name.lower())
        return u"{0.name}, a type{text}.  {url}".format(type, text=text, url=url)

    def cmd_levelup(self, bot, comm, groups):
        query, = groups
        thing = self._lookup(bot, comm, query)
        if not thing:
            return

        if type(thing) is t.PokemonSpecies:
            species = thing
            form = thing.default_form
        elif type(thing) is t.PokemonForm:
            species = thing.species
            form = thing
        else:
            return bot.reply(comm, u"that isn't a pokemon")

        bot.reply(comm, u"{0}", vars=[self.format_levelup_moves(species, form)])

    def format_levelup_moves(self, species, form):
        q = self.session.query(t.PokemonMove)
        q = q.filter_by(pokemon_id = form.pokemon_id)
        q = q.join(t.VersionGroup).filter_by(identifier=self.current_version_group)
        q = q.join(t.PokemonMoveMethod).filter_by(identifier=u'level-up')
        q = q.order_by(t.PokemonMove.level)

        move_text = u"; ".join(u"{0.level}. {0.move.name}".format(pokemove) for i, pokemove in enumerate(q.all()))

        return u"{1.pokemon.name}: {2}.".format(species, form, move_text)

def get_percentile(q, column, value):
    """Return the percent of rows in a query in which the
    given column is less than the given value."""
    def oneif(expr):
        return sql.case([(expr, 1)], else_=0)
    less = sql.func.sum(oneif(column < value))
    equal = sql.func.sum(oneif(column == value))
    total = sql.func.count(column)
    return float(q.value((less + equal*0.5) / total))

def namelist(list, sep=u", "):
    """Format a list of objects as a sorted, comma-separated list of their names."""
    return sep.join(sorted(x.name for x in list))

def urljoin(base, *parts):
    """Append parts of a URL to a base, quoted and separated by slashes."""
    return u"/".join([base] + [urlquote(part) for part in parts])

def urlquote(s):
    """Unicode-safe version of urllib.quote"""
    if type(s) is unicode:
        s = s.encode('utf-8')
    return urllib.quote(s, '').decode('ascii')


import io
import unittest
import re

def strip_colors(s):
    return re.sub(u"\x03[0-9][0-9]|\x0F", u"", s)

class MockLoader:
    config = {}

class MockBot:
    def __init__(self):
        self.response = io.StringIO()

    def reply(self, comm, message, vars=[], kwvars={}):
        message = message.format(*vars, **kwvars)
        self.response.write(message)

class HamperPokedexTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        # TODO: db configuration
        self.loader = MockLoader()
        self.plugin = Plugin()
        self.plugin.setup(self.loader)

    def do_lookup(self, query):
        bot = MockBot()
        self.plugin.cmd_lookup(bot, {}, (query,))
        return strip_colors(bot.response.getvalue())

    def test_lookup_nothing(self):
        self.assertEqual(self.do_lookup(None), u"please specify a pokemon to look up")
        self.assertEqual(self.do_lookup(""), u"please specify a pokemon to look up")

    def test_lookup_pikachu(self):
        response = self.do_lookup("pikachu")
        self.assertEqual(response, u"#25 Pikachu, the Mouse Pokémon.  Electric-type.  Half female♀, half male♂.  Has Static.  35 HP, 55/40 physical, 50/50 special, 90 speed; 320 total.  Egg groups: Fairy and Field.  Hatch counter: 10.  http://veekun.com/dex/pokemon/pikachu")

    def test_lookup_nidoran(self):
        "this one is tricky because nidoran has unicode characters in its name"
        response = self.do_lookup(u"nidoran♀")
        self.assertEqual(response, u"#29 Nidoran♀, the Poison Pin Pokémon.  Poison-type.  Female♀ only.  Has Poison Point or Rivalry.  55 HP, 47/52 physical, 40/40 special, 41 speed; 275 total.  Egg groups: Field and Monster.  Hatch counter: 20.  http://veekun.com/dex/pokemon/nidoran%E2%99%80")

    def test_lookup_potion(self):
        response = self.do_lookup("potion")
        self.assertEqual(response, u"Potion, an item. Restores 20 HP. http://veekun.com/dex/items/medicine/potion")

    def test_lookup_neutral_nature(self):
        response = self.do_lookup("quirky")
        self.assertEqual(response, u"Quirky, a neutral nature. http://veekun.com/dex/natures/quirky")

    def test_lookup_nature(self):
        response = self.do_lookup("modest")
        self.assertEqual(response, u"Modest, a nature. Raises Special Attack; lowers Attack. http://veekun.com/dex/natures/modest")


    def test_lookup_move(self):
        response = self.do_lookup("pound")
        self.assertEqual(response, u"Pound, a Normal-type move. 40 power; 100% accuracy; 35 PP. Inflicts regular damage with no additional effect. http://veekun.com/dex/moves/pound")

    def test_lookup_status_move(self):
        response = self.do_lookup("growl")
        self.assertEqual(response, u"Growl, a Normal-type move. 100% accuracy; 40 PP. Lowers the target's Attack by one stage. http://veekun.com/dex/moves/growl")

    def test_lookup_variable_move(self):
        response = self.do_lookup("psywave")
        self.assertEqual(response, u"Psywave, a Psychic-type move. Variable power; 100% accuracy; 15 PP. Inflicts damage between 50% and 150% of the user's level. http://veekun.com/dex/moves/psywave")

    def test_lookup_perfect_accuracy_move(self):
        response = self.do_lookup("aerial ace")
        self.assertEqual(response, u"Aerial Ace, a Flying-type move. 60 power; perfect accuracy; 20 PP. Never misses. http://veekun.com/dex/moves/aerial%20ace")


    def test_lookup_ability(self):
        response = self.do_lookup("levitate")
        self.assertEqual(response, u"Levitate, an ability. Evades Ground moves. http://veekun.com/dex/abilities/levitate")

    def test_lookup_type(self):
        response = self.do_lookup("grass")
        self.assertEqual(response, u"Grass, a type.  Deals 2× to Ground, Rock, Water; ½× to Bug, Dragon, Fire, Flying, Grass, Poison, Steel.  Takes 2× from Bug, Fire, Flying, Ice, Poison; ½× from Electric, Grass, Ground, Water.  http://veekun.com/dex/types/grass")
