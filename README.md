# University of Toronto Course Selection

**NOTE** This repository is obsolete, as U of T now does course selection using a different system.

## About

This University of Toronto used to have two separate webpages: one with course descriptions, prerequisites, and breadth requirement categories;
another with offering information for the upcoming session (such as lecture and tutorial times).

This made it difficult to plan a course schedule. I therefore created a visualizer and parser for that data.
My main motivation was to find all available courses that fit my last remaining breadth requirement category.

## Run

See `requirements.txt` for dependencies.

`python -m (calendar_page_parser.py | timetable_page_parser.py)`

The scripts will download and parse HTML pages from the U of T timetable or calendar pages. There are also commented-out portions which will parse the main page. The parsed data will be saved in the `courses.db` database. Metadata will be extracted and saved in `(timetable|calendar)_inventory.data` pickle files.

## Data Files

**timetable_inventory.data** - map from name of program to a URL where the timetable for that program can be found

**calendar_inventory.data** - map from name of program to a URL where the calendar for that program can be found

**courses.db** - SQLite3 database that contains course and timetable information.
You can read the SQLite3 database contents using `sqlite3` tool or similar.
It has 2 tables: couses and timetable

### Server

Please note that this is not the original server. The original server was written in PHP. I have no idea where that code is.

```
yarn install
yarn start
```


## Linting

```
pyflakes uoft
mypy uoft --ignore-missing-imports
```