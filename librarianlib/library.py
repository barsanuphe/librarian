import os
import subprocess
import shutil
import hashlib
import codecs
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
import json

from librarianlib.epub import Epub
from librarianlib.librarian_server import LibrarianServer, LibrarianHandler


class Library(object):

    def __init__(self, config, db):
        self.ebooks = []
        self.backup_imported_ebooks = True
        self.scrape_root = None
        self.ebook_filename_template = config.get("ebook_filename_template",
                                                  "$a/$a ($y) $t")
        self.config = config
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        # cleaning up temp opf files
        for epub in self.ebooks:
            if epub.is_opf_open:
                epub.close_metadata()

    def _load_ebook(self, everything, filename):
        if "path" not in everything[filename].keys():
            return False, None
        eb = Epub(everything[filename]["path"], self.config["library_dir"],
                  self.config["author_aliases"], self.ebook_filename_template)
        return eb.load_from_database_json(everything[filename], filename), eb

    def open_db(self):
        if os.path.exists(self.db):
            start = time.perf_counter()
            everything = json.load(open(self.db, 'r'))

            with ThreadPoolExecutor(max_workers=cpu_count()) as executor:
                future_to_ebook = {
                    executor.submit(self._load_ebook,
                                    everything,
                                    f): f for f in everything.keys()
                    }
                for future in as_completed(future_to_ebook):
                    success, ebook = future.result()
                    if success:
                        self.ebooks.append(ebook)
            print("Database opened in %.2fs: loaded %s ebooks." %
                  ((time.perf_counter() - start), len(self.ebooks)))
        else:
            print("No DB, refresh!")

    def _return_or_create_new_ebook(self, full_path, known_ebooks):
        is_already_in_db = False
        for eb in known_ebooks:
            if eb.path == full_path:
                is_already_in_db = True
                eb.open_ebook_metadata()
                return eb
        if not is_already_in_db:
            eb = Epub(full_path, self.config["library_dir"],
                      self.config["author_aliases"],
                      self.ebook_filename_template)
            eb.open_ebook_metadata()
            print(" ->  NEW EBOOK: ", eb)
            return eb
        return None

    def refresh_db(self):
        print("Refreshing library...")
        start = time.perf_counter()
        old_db = list(self.ebooks)  # copy
        self.ebooks = []

        # list all books in library root
        all_ebooks_in_library_dir = []
        for root, dirs, files in os.walk(self.config["library_dir"]):
            all_ebooks_in_library_dir.extend([os.path.join(root, el)
                                              for el in files
                                              if el.lower().endswith(".epub")])

        # refresh list
        for (i,ebook) in enumerate(sorted(all_ebooks_in_library_dir)):
            eb = self._return_or_create_new_ebook(ebook, old_db)
            if eb is not None:
                print(" %.2f%%" % (100*i/len(all_ebooks_in_library_dir)),
                          end="\r", flush=True)
                # rename if necessary
                eb.rename_from_metadata()
                self.ebooks.append(eb)

        # display missing ebooks
        deleted = [eb for eb in old_db if eb not in self.ebooks]
        for eb in deleted:
            print(" -> DELETED EBOOK: ", eb)

        # remove empty dirs in library root
        for root, dirs, files in os.walk(self.config["library_dir"],
                                         topdown=False):
            for dir in [os.path.join(root, el) for el in dirs if
                        os.listdir(os.path.join(root, el)) == []]:
                os.rmdir(dir)

        is_incomplete = self.list_incomplete_metadata()
        print("Database refreshed in %.2fs." % (time.perf_counter() - start))
        return is_incomplete

    def save_db(self, readable=False, sync_with_files=False):
        print("Saving dabatase...")
        data = {}
        # adding ebooks in alphabetical order
        for ebook in sorted(self.ebooks, key=lambda x: x.filename):
            data[ebook.filename] = ebook.to_database_json()
            if sync_with_files:
                ebook.sync_ebook_metadata()

        # copy previous db
        if os.path.exists("%s_backup" % self.db):
            os.remove("%s_backup" % self.db)
        shutil.copyfile(self.db, "%s_backup" % self.db)

        # dumping in json file
        with open(self.db, "w") as data_file:
            if readable:
                data_file.write(json.dumps(data, sort_keys=True, indent=2,
                                           separators=(',', ': '),
                                           ensure_ascii=False))
            else:
                data_file.write(json.dumps(data, ensure_ascii=False))

    def scrape_dir_for_ebooks(self):
        scrape_root = self.config.get("scrape_root", None)
        if scrape_root is None:
            print("scrape_root not defined in librarian.yaml, nothing to do.")
            return

        start = time.perf_counter()
        all_ebooks_in_scrape_dir = []
        print("Finding ebooks in %s..." % scrape_root)
        for root, dirs, files in os.walk(scrape_root):
            all_ebooks_in_scrape_dir.extend([os.path.join(root, el)
                                             for el in files
                                             if os.path.splitext(el.lower())[1]
                                             in [".epub", ".mobi"]])
        # if an ebook has an epub and mobi version, only take epub
        filtered_ebooks_in_scrape_dir = []
        for ebook in all_ebooks_in_scrape_dir:
            if os.path.splitext(ebook)[1].lower() == ".epub":
                filtered_ebooks_in_scrape_dir.append(ebook)
            if os.path.splitext(ebook)[1].lower() == ".mobi":
                epub_version = os.path.splitext(ebook)[0] + ".epub"
                if epub_version not in all_ebooks_in_scrape_dir:
                    filtered_ebooks_in_scrape_dir.append(ebook)

        if len(filtered_ebooks_in_scrape_dir) == 0:
            print("Nothing to scrape.")
            return False
        else:
            print("Scraping ", scrape_root)

        for ebook in filtered_ebooks_in_scrape_dir:
            print(" -> Scraping ", os.path.basename(ebook))
            shutil.copyfile(ebook, os.path.join(self.config["import_dir"],
                                                os.path.basename(ebook)))

        print("Scraped ebooks in %.2fs." % (time.perf_counter() - start))
        return True

    def _convert_to_epub_before_importing(self, mobi):
        epub_name = mobi.replace(".mobi", ".epub")
        if not os.path.exists(epub_name):
            print("   + Converting to .epub: ", mobi)
            return subprocess.call(['ebook-convert',
                                    mobi,
                                    epub_name,
                                    "--output-profile", "kindle_pw"],
                                    stdout=subprocess.DEVNULL)
        else:
            return 0

    def import_new_ebooks(self):
        # multithreaded conversion to epub before import, if necessary
        cpt = 1
        all_mobis = [os.path.join(self.config["import_dir"], el)
                     for el in os.listdir(self.config["import_dir"])
                     if el.endswith(".mobi")]
        with ThreadPoolExecutor(max_workers=cpu_count()) as executor:
            future_epubs = {
                executor.submit(self._convert_to_epub_before_importing,
                                mobi): mobi for mobi in all_mobis
                }
            for future in as_completed(future_epubs):
                if future.result() == 0:
                    print(" %.2f%%" % (100*cpt/len(all_mobis)),
                          end="\r", flush=True)
                    cpt += 1
                else:
                    raise Exception("Error converting to epub!")

        all_ebooks = [el for el in os.listdir(self.config["import_dir"])
                      if el.endswith(".epub")]
        if len(all_ebooks) == 0:
            print("Nothing new to import.")
            return False
        else:
            print("Importing.")

        all_already_imported_ebooks = [el
                                       for el
                                       in os.listdir(
                                           self.config["imported_dir"])
                                       if el.endswith(".epub")]
        already_imported_hashes = []
        for eb in all_already_imported_ebooks:
            already_imported_hashes.append(
                hashlib.sha1(open(os.path.join(self.config["imported_dir"],
                                               eb),
                                  'rb').read()).hexdigest())

        start = time.perf_counter()
        imported_count = 0
        for ebook in all_ebooks:
            ebook_candidate_full_path = os.path.join(self.config["import_dir"],
                                                     ebook)

            # check for duplicate hash
            new_hash = hashlib.sha1(open(ebook_candidate_full_path,
                                         'rb').read()).hexdigest()
            if new_hash in already_imported_hashes:
                print(" -> skipping already imported: ", ebook)
                continue

            # check for complete metadata
            temp_ebook = Epub(ebook_candidate_full_path,
                              self.config["library_dir"],
                              self.config["author_aliases"],
                              self.ebook_filename_template)
            temp_ebook.open_ebook_metadata()
            if not temp_ebook.librarian_metadata.is_complete:
                print(" -> skipping ebook with incomplete metadata: ", ebook)
                continue

            # check if book not already in library
            already_in_db = False
            for eb in self.ebooks:
                same_authors = (eb.librarian_metadata.get_values("author") ==
                                temp_ebook.librarian_metadata.get_values("author"))
                same_title = (eb.librarian_metadata.get_values("title") ==
                              temp_ebook.librarian_metadata.get_values("title"))
                if same_authors and same_title:
                    already_in_db = True
                    break
            if already_in_db:
                print(" -> library already contains an entry for: ",
                      temp_ebook.librarian_metadata.get_values("author")[0],
                      " - ", temp_ebook.librarian_metadata.get_values("title")[0],
                      ": ", ebook)
                continue

            if self.config.get("interactive", True):
                print("About to import: %s" % str(temp_ebook))
                answer = input("Confirm? \ny/n? ")
                if answer.lower() == "n":
                    print(" -> skipping ebook ", ebook)
                    continue

            # if all checks are ok, importing
            print(" ->", ebook)
            # backup
            if self.config["backup_imported_ebooks"]:
                # backup original mobi version if it exists
                mobi_full_path = ebook_candidate_full_path.replace(".epub",
                                                                   ".mobi")
                if os.path.exists(mobi_full_path):
                    shutil.move(mobi_full_path,
                                os.path.join(self.config["imported_dir"],
                                             ebook.replace(".epub", ".mobi")))
                shutil.copyfile(ebook_candidate_full_path,
                                os.path.join(self.config["imported_dir"],
                                             ebook))
            # import
            shutil.move(ebook_candidate_full_path,
                        os.path.join(self.config["library_dir"], ebook))
            imported_count += 1
        print("Imported ebooks in %.2fs." % (time.perf_counter() - start))

        if imported_count != 0:
            return True
        else:
            return False

    def update_kindle_collections(self, outfile, filtered=[]):
        # generates the json file that is used
        # by the kual script in librariansync/
        if filtered == []:
            ebooks_to_sync = self.ebooks
        else:
            ebooks_to_sync = filtered
        tags_json = {}
        for eb in sorted(ebooks_to_sync, key=lambda x: x.filename):
            relative_path = os.path.join(
                self.config["kindle_documents_subdir"],
                eb.exported_filename)
            tags_json[relative_path] = [eb.read.name]
            if eb.tags != []:
                tags_json[relative_path].append(eb.tags)

        f = codecs.open(outfile, "w", "utf8")
        f.write(json.dumps(tags_json, sort_keys=True, indent=2,
                           separators=(',', ': '), ensure_ascii=False))
        f.close()

    def sync_with_kindle(self, filtered=[], kindle_sync=True,
                         destination_dir=None):
        if filtered == []:
            ebooks_to_sync = self.ebooks
        else:
            ebooks_to_sync = filtered

        if kindle_sync:
            print("Syncing with kindle.")
            if not os.path.exists(self.config["kindle_root"]):
                print("Kindle is not connected/mounted. Abandon ship.")
                return
            if not os.path.exists(self.config["kindle_documents"]):
                os.makedirs(self.config["kindle_documents"])
        else:
            if destination_dir is None:
                print("Missing destination dir for sync. Abandon ship.")
                return
            if not os.path.exists(destination_dir):
                os.makedirs(destination_dir)

        start = time.perf_counter()

        if kindle_sync:
            output_dir = self.config["kindle_documents"]
            file_type = ".mobi"
        else:
            output_dir = destination_dir
            file_type = ".epub"

        # list all mobi/epub files in KINDLE_DOCUMENTS/destination_dir
        print(" -> Listing existing ebooks.")
        all_ebooks = []
        for root, dirs, files in os.walk(output_dir):
            all_ebooks.extend([os.path.join(root, file)
                               for file in files
                               if os.path.splitext(file)[1] == file_type])

        # sync books / convert to mobi
        print(" -> Syncing library.")
        cpt = 0
        if kindle_sync:
            threads = cpu_count()
        else:
            # when syncing epubs, only one thread,
            # to prevent race conditions when creating
            # directories.
            threads = 1

        with ThreadPoolExecutor(max_workers=threads) as executor:
            sorted_ebooks = sorted(ebooks_to_sync, key=lambda x: x.filename)
            if kindle_sync:
                all_sync = {
                    executor.submit(eb.sync_with_kindle,
                                    self.config["kindle_documents"],
                                    self.config["mobi_dir"]): eb for eb
                    in sorted_ebooks
                    }
            else:
                all_sync = {
                    executor.submit(eb.sync_with_kindle,
                                    destination_dir,
                                    None): eb for eb in sorted_ebooks
                    }
            for future in as_completed(all_sync):
                ebook = all_sync[future]
                print(" %.2f%%" % (100*cpt/len(self.ebooks)),
                      end="\r", flush=True)
                cpt += 1
                # remove ebook from the list of previously exported ebooks
                if kindle_sync:
                    obsolete = os.path.join(output_dir,
                                            ebook.exported_filename)
                else:
                    obsolete = os.path.join(output_dir, ebook.filename)
                if obsolete in all_ebooks:
                    all_ebooks.remove(obsolete)

        # delete mobis on kindle that are not in library anymore
        print(" -> Removing obsolete ebooks.")
        for eb in all_ebooks:
            print("    + ", eb)
            os.remove(eb)

        # remove empty dirs in KINDLE_DOCUMENTS
        for root, dirs, files in os.walk(output_dir, topdown=False):
            for dir in [os.path.join(root, el)
                        for el in dirs
                        if os.listdir(os.path.join(root, el)) == []]:
                os.rmdir(dir)

        # sync collections.json
        if kindle_sync:
            print(" -> Generating and copying database for \
                collection generation.")
            self.update_kindle_collections(self.config["collections"],
                                           filtered)
            shutil.copy(self.config["collections"],
                        self.config["kindle_extensions"])

        print("Library synced in %.2fs." % (time.perf_counter() - start))

    def list_incomplete_metadata(self):
        found_incomplete = False
        incomplete_list = ""
        for eb in self.ebooks:
            if not eb.librarian_metadata.is_complete:
                found_incomplete = True
                incomplete_list += " -> %s\n" % eb.path
        if found_incomplete:
            print("The following ebooks have incomplete metadata:")
            print(incomplete_list)
        return found_incomplete

    def serve(self, filtered=[], kindle_sync=True):
        if filtered == []:
            ebooks_to_serve = self.ebooks
        else:
            ebooks_to_serve = filtered

        if not kindle_sync:
            allowed = [el.path for el in ebooks_to_serve]
            local_root = self.config["library_dir"]
        else:
            for eb in ebooks_to_serve:
                eb.export_to_mobi(self.config["mobi_dir"])
            allowed = [os.path.join(self.config["mobi_dir"],
                                    el.exported_filename)
                       for el in ebooks_to_serve]
            local_root = self.config["mobi_dir"]

        # create partial collections
        self.update_kindle_collections(self.config["collections"], filtered)

        print("Serving.")
        server = LibrarianServer((self.config["server"]["IP"],
                                  self.config["server"]["port"]),
                                 LibrarianHandler, allowed,
                                 local_root, self.config["collections"])
        server.serve_forever()

        # removing collections json
        os.remove(self.config["collections"])
