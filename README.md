**NOTE**: if you are looking for LibrarianSync, it has been moved to [its own repository](https://github.com/barsanuphe/librariansync).

# Librarian

Epub Ebook managerwhich can import epub ebooks, rename them from metadata, convert them to mobi,
and sync with a Kindle Paperwhite.
It can also run queries using all metadata, and add and remove tags which
can be converted to Kindle collections with [LibrarianSync](https://github.com/barsanuphe/librariansync).
There is experimental support to write metadata, and to serve ebooks over http
to LibrarianSync on a Kindle.
It is in early stages. See disclaimer below.

## Quick disclaimer about librarian

*librarian* is in development and not even close to being stable. This means:

- Expect the commands and database formats to change any time.
- Keep backups of your ebooks, both on your computer and your Kindle.
- *librarian* is tested on Archlinux, it should work on other distributions/platforms,
    but then again it may not because reasons.

## Table of Contents

- [Requirements](#requirements)
- [Configuration](#configuration)
- [Usage](#usage)
- [Example Commands](#example-commands)

## Librarian


### Requirements

- Python 3
- Calibre (librarian relies on ebook-convert, which are part of Calibre)
- pyyaml
- python-lxml
- python-colorama (optional)

### Configuration

*librarian* uses several special folders, as specified in the configuration
file *librarian.yaml*:

- *library_root*: where all ebooks are kept. More specifically, it will be divided in subfolders:
    - **import**: temporary place to dump ebooks before they are imported into the library proper
    - **imported**: when an ebook is imported (and renamed), a copy of the original is optionnally placed here.
    - **kindle**: a mirror of the library, with all epubs converted into mobis. This is what will be synced with the Kindle.
    - **library**: where all imported ebooks are safely kept.
- *kindle_root*: where the Kindle is mounted when it is connected by USB. This may depend on your Linux distribution.
- *scrape_root*: if you have ebooks lying around on a drive at random, for example, scraping it will copy them all into the import subfolder.

An example configuration would be:

    author_aliases:
        Alexandre Dumas Père: Alexandre Dumas
        China Mieville: China Miéville
        Richard Morgan: Richard K. Morgan
    backup_imported_ebooks: true
    interactive: true
    ebook_filename_template: $a/$a ($y) $t
    kindle_documents_subdir: library
    kindle_root: /run/media/login/Kindle
    library_root: /home/login/ebooks
    scrape_root: /home/login/documents
    server:
        IP: 192.168.0.5
        port: 13698

*kindle_root* and *library_root* are mandatory. The rest is optional.

*interactive* decides if importing ebooks is automatic or if manual confirmation
is required for each book.

*ebook_filename_template* is the template for epub filenames inside the library,
by default '$a/$a ($y) $t'.
Available information are: *$a* (author), *$y* (year), *$t* (title), *$s* (series),
*$i* (series_index).
Refreshing the database automatically applies the template.

The *server* configuration allows *librarian* to serve a selection of ebooks over
http. It is then possible to use a well configured *LibrarianSync* to automatically
connect, download the ebooks, and update the Kindle collections accordingly.

**Note**: Only epub ebooks can be added to the library. They are converted to
mobi while syncing with the Kindle.
If mobi ebooks are present in the *import* folder, they are converted to epub,
then imported. Both the original mobi and the resulting epub are then backed up
in the *imported* folder.

The library database is kept in a Python dictionary saved and loaded as a json
file.

### Usage

Note: if python2 is the default version on your Linux distribution, launch with *python3 librarian*.

    $ librarian -h
    usage: librarian [-h] [-i] [-r] [--scrape] [-s [PATH]] [-k] [--serve]
                    [-f [STRING [STRING ...]]] [-l [STRING [STRING ...]]]
                    [-x STRING [STRING ...]] [-t TAG [TAG ...]]
                    [-d TAG [TAG ...]] [-c [COLLECTION]]
                    [--progress {read,reading,unread}]
                    [--info [METADATA_FIELD [METADATA_FIELD ...]]]
                    [--openlibrary]
                    [-w METADATA_FIELD_AND_VALUE [METADATA_FIELD_AND_VALUE ...]]
                    [--config CONFIG_FILE] [--readable-db]

    Librarian. A very early version of it.

    optional arguments:
    -h, --help            show this help message and exit

    Library management:
    Import, analyze, and sync with Kindle.

    -i, --import          import ebooks
    -r, --refresh         refresh library
    --scrape              scrape for ebooks
    -s [PATH], --sync [PATH]
                            sync library (or a subset with --filter or --list)
    -k, --kindle          when syncing, sync to kindle
    --serve               serve filtered ebooks over http

    Tagging:
    Search and tag ebooks. For --list, --filter and --exclude, STRING can
    begin with author:, title:, tag:, series: or progress: for a more precise
    search.

    -f [STRING [STRING ...]], --filter [STRING [STRING ...]]
                            list ebooks in library matching ALL patterns
    -l [STRING [STRING ...]], --list [STRING [STRING ...]]
                            list ebooks in library matching ANY pattern
    -x STRING [STRING ...], --exclude STRING [STRING ...]
                            exclude ALL STRINGS from current list/filter
    -t TAG [TAG ...], --add-tag TAG [TAG ...]
                            tag listed ebooks in library
    -d TAG [TAG ...], --delete-tag TAG [TAG ...]
                            remove tag(s) from listed ebooks in library
    -c [COLLECTION], --collections [COLLECTION]
                            list all tags or ebooks with a given tag or "untagged"
    --progress {read,reading,unread}
                            Set filtered ebooks as read.

    Metadata:
    Display and write epub metadata.

    --info [METADATA_FIELD [METADATA_FIELD ...]]
                            Display all or a selection of metadata tags for
                            filtered ebooks.
    --openlibrary         Search OpenLibrary for filtered ebooks.
    -w METADATA_FIELD_AND_VALUE [METADATA_FIELD_AND_VALUE ...], --write-metadata METADATA_FIELD_AND_VALUE [METADATA_FIELD_AND_VALUE ...]
                            Write one or several field:value metadata.

    Configuration:
    Configuration options.

    --config CONFIG_FILE  Use an alternative configuration file.
    --readable-db         Save the database in somewhat readable form.


While syncing with Kindle, *librarian* will keep track of previous conversions
to the mobi format (for epub ebooks), and of previously synced ebooks on the Kindle,
and will try to work no more than necessary.

**Syncing** means: copy the mobi versions of all filtered ebooks to the Kindle,
and *remove from the Kindle all previously existing mobis not presently filtered*.
Do make sure the *kindle_documents_subdir* of the configuration file only contains
ebooks that are inside the library.

**Writing metadata is very, very experimental.**

Note that if books are imported successfully, a refresh is automatically added.
Also, only .epubs and .mobis are imported/scraped, with a preference for .epub
when both formats are available.

### Example commands

Scrape a directory (specified in the configuration file) and automatically add
to the library everything that was found:

    ./librarian --scrape -i

Refresh the library after adding "Richard Morgan: Richard K. Morgan" to the
author aliases in the configuration file, so that all "Richard Morgan" ebooks get
renamed as "Richard K. Morgan":

    ./librarian -r

List all tags and the number of ebooks for each:

    ./librarian -c

List all yet untagged ebooks:

    ./librarian -c untagged

Display all ebooks in the library with the tag *sf/space opera*:

    ./librarian -f "tag:sf/space opera"

or

    ./librarian -c "sf/space opera"

Display all ebooks in the library with the tag *sf/space opera*, but not the Peter
F. Hamilton books you just read:

    ./librarian -f "tag:sf/space opera" -x hamilton

Display all ebooks in the library with the tag *sf/space opera*, but not the Peter
F. Hamilton books you just read, and also everything by Alexandre Dumas:

    ./librarian -l tag:opera dumas -x hamilton

Tag as *best category* and *random* all ebooks in the library with the tag *sf/space opera*, but not the Peter
F. Hamilton books you just read, and also everything by Alexandre Dumas:

    ./librarian -l tag:opera dumas -x hamilton -t "best category" random

Change tag from *best category* to *best category!* for all ebooks in the library with the tag *sf/space opera*, but not the Peter
F. Hamilton books you just read, and also everything by Alexandre Dumas:

    ./librarian -l tag:opera dumas -x hamilton -d "best category" -t "best category!"

Sync to your Kindle all ebooks in the library with the tag *sf/space opera*, but not the Peter
F. Hamilton books you just read, and also everything by Alexandre Dumas:

    ./librarian -l tag:opera dumas -x hamilton -s -k

Serve over http for your Kindle, all ebooks (in .mobi forma) in the library with
the tag *sf/space opera*, but not the Peter F. Hamilton books you just read, and
also everything by Alexandre Dumas:

    ./librarian -l tag:opera dumas -x hamilton --serve -k

Display the title and description for all of your Aldous Huxley ebooks:

    ./librarian -f author:huxley --info title description

Mark all ebooks by Alexandre Dumas as read:

    ./librarian -f author:dumas --progress read

