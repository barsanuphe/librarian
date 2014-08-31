## librarian sync

This is the part that generates the Kindle collections from a json file.
It can be used completely independantly of librarian.py, provided the
collections.json file is correct (see example later) and in the correct location
(inside the **extensions** folder on the Kindle).

### Requirements

- [A jailbroken Kindle Paperwhite2](http://www.mobileread.com/forums/showthread.php?t=186645)
- [Mobiread Kindlet Kit installed](http://www.mobileread.com/forums/showthread.php?t=233932)
- [KUAL installed](http://www.mobileread.com/forums/showthread.php?t=203326)
- [Python installed](http://www.mobileread.com/forums/showthread.php?t=225030) (snapshot > 0.10N-r10867)

For instructions on how to do that, try the
[mobileread forum](http://www.mobileread.com/forums/forumdisplay.php?f=150) in
general.

This script is inspired by
[this thread](http://www.mobileread.com/forums/showthread.php?t=160855).


### Installation

Once the requirements are met, just copy the **librariansync** folder into the
**extensions** folder on the kindle.

### Usage

From the Kindle, launch KUAL. A new menu option *Librarian Sync* should appear,
which contains two entries:

- *Rebuild all collections (from json)* :
    to clear all existing collections and rebuild them using the json file
- *Add to collections (from json)* :
    to only add ebooks to existing or new collections, using the json file
- *Rebuild all collections (from folders)* :
    to clear all existing collections and rebuild them using the folder structure
    inside the **documents** folder.


### What it does

After syncing with the main script librarian.py, and if tags are defined in
library.yaml for entries, the **extensions** folder on the Kindle should contain
a file, collections.json.

When *rebuilding collections*, Librarian Sync removes all collections, then adds
the collections as defined in collections.json.

When *adding to them*, it preserves already existing collections, and only either
add entries to them or creates new collections as defined in collections.json.

When *rebuilding collection from folders*, it removes all collections and
recursively scans for any supported file inside the **documents** folder.
Subfolders will be treated as different collections.
Ebooks directly in the **documents** folder are ignored.

Allow for a few seconds for the Kindle database and interface to reflect the
changes made.

### collections.json example

Each ebook path (relative to the **documents** folder) is associated to a
list of collection names.

    {
        "library/Alexandre Dumas/Alexandre Dumas (2004) Les Trois Mousquetaires.mobi": ["gutenberg","french","already read"],
        "library/Alexandre Dumas/Alexandre Dumas (2004) Vingt Ans Après.mobi": ["gutenberg","french","not read yet"],
        "library/Alexandre Dumas/Alexandre Dumas (2011) Le Comte De Monte-Cristo.mobi": ["gutenberg","french","already read"]
    }

