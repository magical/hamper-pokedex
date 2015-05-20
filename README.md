Hamper-pokedex is a plugin for [hamper][] which allows you to look up facts
about Pokémon.

[![Build Status](https://travis-ci.org/magical/hamper-pokedex.svg?branch=master)](https://travis-ci.org/magical/hamper-pokedex)

[hamper]: https://github.com/hamperbot/hamper

Installation
------------

The following steps assume that your database is `postgresql:///pokedex` and
your lookup index directory is `./dex-lookup`.

1. Install Whoosh version 2.5. (Pokedex doesn't work with the latest version of whoosh)

        $ pip install Whoosh==2.5.6

2. Run `python setup.py install`

   This will also install the [pokedex][] library.

[pokedex]: https://github.com/veekun/pokedex

3. Run `pokedex setup -v -e postgresql:///pokedex -i ./dex-lookup` to
   initialize the pokemon database and search index.

4. Add hamper-pokedex to your `hamper.conf`
    
        pokedex:
            db: postgresql:///pokedex
            lookup: ./dex-lookup

        plugins:
            - ...
            - pokedex
            - ...
