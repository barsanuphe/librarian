import tempfile
import shutil
import os
import subprocess
import hashlib
import zipfile
from lxml import etree
from enum import Enum
from .epub_metadata import OpfFile, FakeOpfFile, ns

try:
    from colorama import init
    init(autoreset=True)
    from colorama import Fore, Style

    def unread(text):
        return Fore.YELLOW + Style.BRIGHT + text

    def reading(text):
        return Fore.GREEN + Style.BRIGHT + text

    def read(text):
        return Fore.BLUE + Style.BRIGHT + text
except:
    def unread(text):
        return "** " + text

    def reading(text):
        return ":: " + text

    def read(text):
        return text


def has_changed(f, *args):
    def new_f(*args):
        res = f(*args)
        if res:
            args[0].has_changed = True
        return res
    return new_f


def strip_lower(f, *args):
    def new_f(*args):
        tag = args[1].strip().lower()
        f(args[0], tag)
    return new_f

AUTHORIZED_TEMPLATE_PARTS = {
    "$a": "author",
    "$y": "year",
    "$t": "title",
    "$s": "series",
    "$i": "series_index",
    "$p": "progress",
}

class ReadStatus(Enum):
    unread = 0
    reading = 1
    read = 2


class Epub(object):

    def __init__(self, path, library_dir, author_aliases,
                 ebook_filename_template):
        self.path = path
        self.library_dir = library_dir
        self.author_aliases = author_aliases

        self.librarian_metadata = None
        self.ebook_metadata = None
        self.is_opf_open = False
        self.metadata_filename = ""

        self.tags = []
        self.has_changed = False
        self.loaded_metadata = None
        self.template = ebook_filename_template
        self.was_converted_to_mobi = False
        self.converted_to_mobi_from_hash = ""
        self.converted_to_mobi_hash = ""
        self.last_synced_hash = ""
        self.read = ReadStatus(0)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def __str__(self):
        metadata = self.librarian_metadata
        if metadata.get_values("series") != []:
            first_series = metadata.get_values("series")[0]
            if metadata.get_values("series_index") != []:
                first_series_idx = metadata.get_values("series_index")[0]
                series_info = "[ %s #%s ]" % (first_series, first_series_idx)
            else:
                series_info = "[ %s ]" % (first_series)
        else:
            series_info = ""

        first_author = metadata.get_values("author")[0]
        first_title = metadata.get_values("title")[0]
        first_year = metadata.get_values("year")[0]
        str = ""
        if self.tags == []:
            str = "%s (%s) %s %s" % (first_author,
                                     first_year,
                                     first_title,
                                     series_info)
        else:
            str = "%s (%s) %s %s [ %s ]" % (first_author,
                                            first_year,
                                            first_title,
                                            series_info,
                                            ", ".join(self.tags))

        if self.read == ReadStatus.unread:
            return unread(str)
        elif self.read == ReadStatus.reading:
            return reading(str)
        else:
            return read(str)

    @property
    def extension(self):
        # extension without the .
        return os.path.splitext(self.path)[1][1:].lower()

    @property
    def current_hash(self):
        return hashlib.sha1(open(self.path, 'rb').read()).hexdigest()

    def set_filename_template(self, template):
        self.template = template

    @property
    def filename(self):
        template = self.template
        for key in AUTHORIZED_TEMPLATE_PARTS.keys():
            relevant_parts = self.librarian_metadata.get_values(
                AUTHORIZED_TEMPLATE_PARTS[key])
            if len(relevant_parts) >= 1:
                template = template.replace(key, relevant_parts[0])
            elif AUTHORIZED_TEMPLATE_PARTS[key] == "progress":
                template = template.replace(key, self.read.name)
        template = template.replace(":", "").replace("?", "")
        return "%s.%s" % (template, self.extension)

    @property
    def exported_filename(self):
        return os.path.splitext(self.filename)[0] + ".mobi"

    def load_from_database_json(self, filename_dict, filename):
        if not os.path.exists(filename_dict["path"]):
            print("File %s in DB cannot be found, ignoring." %
                  filename_dict["path"])
            return False
        try:
            self.loaded_metadata = filename_dict
            # for similar interface to OpfFile
            self.librarian_metadata = FakeOpfFile(filename_dict['metadata'],
                                        self.author_aliases)
            self.tags = [el.lower().strip()
                         for el in filename_dict['tags'].split(",")
                         if el.strip() != ""]
            self.converted_to_mobi_hash = \
                filename_dict['converted_to_mobi_hash']
            self.converted_to_mobi_from_hash = \
                filename_dict['converted_to_mobi_from_hash']
            self.last_synced_hash = filename_dict['last_synced_hash']
            self.read = ReadStatus(int(filename_dict['read']))
        except Exception as err:
            print("Incorrect db!", err)
            return False
        return True

    def to_database_json(self):
        if self.has_changed:
            return {
                "path": self.path,
                "tags": ",".join(sorted([el for el in self.tags
                                        if el.strip() != ""])),
                "last_synced_hash": self.last_synced_hash,
                "converted_to_mobi_hash": self.converted_to_mobi_hash,
                "converted_to_mobi_from_hash":
                    self.converted_to_mobi_from_hash,
                "metadata": self.librarian_metadata.metadata_dict,
                "read": self.read.value
                }
        else:
            return self.loaded_metadata

    def open_ebook_metadata(self):
        if not self.is_opf_open:
            self.temp_dir = tempfile.mkdtemp()
            self.extract_opf_file()
            self.is_opf_open = True

    def extract_opf_file(self):
        zip = zipfile.ZipFile(self.path)
        # find the contents metafile
        txt = zip.read('META-INF/container.xml')
        tree = etree.fromstring(txt)

        self.metadata_filename = tree.xpath(
            'n:rootfiles/n:rootfile/@full-path',
            namespaces=ns)[0]
        self.temp_opf = os.path.join(self.temp_dir,
                                     os.path.basename(self.metadata_filename))

        cf = zip.read(self.metadata_filename)
        with open(self.temp_opf, "w") as opf:
            opf.write(cf.decode("utf8"))

        self.ebook_metadata = OpfFile(self.temp_opf, self.author_aliases)
        # first import
        if self.librarian_metadata is None:
            self.librarian_metadata = self.ebook_metadata

    def remove_from_zip(self, zipfname, *filenames):
        tempdir = tempfile.mkdtemp()
        try:
            tempname = os.path.join(tempdir, 'new.zip')
            with zipfile.ZipFile(zipfname, 'r') as zipread:
                with zipfile.ZipFile(tempname, 'w') as zipwrite:
                    for item in zipread.infolist():
                        if item.filename not in filenames:
                            data = zipread.read(item.filename)
                            zipwrite.writestr(item, data)
            shutil.move(tempname, zipfname)
        finally:
            shutil.rmtree(tempdir)

    def save_metadata(self):
        if self.is_opf_open and self.ebook_metadata.has_changed:
            print("Saving epub...")
            self.remove_from_zip(self.path, self.metadata_filename)
            with zipfile.ZipFile(self.path, 'a') as z:
                z.write(self.temp_opf, arcname=self.metadata_filename)

    def close_metadata(self):
        if self.is_opf_open:
            self.is_opf_open = False
            # clean up
            self.__exit__(None, None, None)

    def sync_ebook_metadata(self):
        print("Writing metadata to ebook file is disabled for now.")
        return False

        self.open_ebook_metadata()
        # TODO: clear ebook_metadata ??

        # copy to ebook_metadata
        for key in self.librarian_metadata.keys:
            values = self.librarian_metadata.get_values(key)
            for value in values:
                self.ebook_metadata.set_value(key, value, replace=True)
        self.ebook_metadata.has_changed = True
        #TODO: go through ebook_metadata and set all values to opf
        self.save_metadata()
        self.close_metadata()

    @strip_lower
    @has_changed
    def add_to_collection(self, tag):
        if tag != "" and tag not in self.tags:
            self.tags.append(tag)
            return True
        return False

    @strip_lower
    @has_changed
    def remove_from_collection(self, tag):
        if tag != "" and tag in self.tags:
            self.tags.remove(tag)
            return True
        return False

    def get_relative_path(self, path):
        return path.split(self.library_dir)[1][1:]

    @has_changed
    def rename_from_metadata(self, force=False):
        # open ebook metadata if necessary or forced
        self.open_ebook_metadata()
        if self.librarian_metadata.is_complete and self.library_dir in self.path:
            new_name = os.path.join(self.library_dir, self.filename)
            if new_name != self.path:
                if not os.path.exists(os.path.dirname(new_name)):
                    print("Creating directory",
                          self.get_relative_path(os.path.dirname(new_name)))
                    os.makedirs(os.path.dirname(new_name))
                print("Renaming to ", self.get_relative_path(new_name))
                shutil.move(self.path, new_name)
                # refresh name
                self.path = new_name
                return True
        return False

    @has_changed
    def export_to_mobi(self, mobi_dir):
        output_filename = os.path.join(mobi_dir, self.exported_filename)
        if os.path.exists(output_filename):
            # check if ebook has changed since the mobi was created
            if self.current_hash == self.converted_to_mobi_from_hash:
                self.was_converted_to_mobi = True
                return False

        if not os.path.exists(os.path.dirname(output_filename)):
            print("Creating directory", os.path.dirname(output_filename))
            os.makedirs(os.path.dirname(output_filename))

        # conversion
        print("   + Converting to .mobi: ", self.filename)
        subprocess.check_call(['ebook-convert',
                               self.path,
                               output_filename,
                               "--output-profile",
                               "kindle_pw"], stdout=subprocess.DEVNULL)

        self.converted_to_mobi_hash = \
            hashlib.sha1(open(output_filename, 'rb').read()).hexdigest()
        self.converted_to_mobi_from_hash = self.current_hash
        self.was_converted_to_mobi = True
        return True

    @has_changed
    def sync_with_kindle(self, destination_dir, mobi_dir=None):
        if mobi_dir is not None and not self.was_converted_to_mobi:
            self.export_to_mobi(mobi_dir)

        if mobi_dir is not None:
            output_filename = os.path.join(destination_dir,
                                           self.exported_filename)
        else:
            output_filename = os.path.join(destination_dir,
                                           self.filename)

        if not os.path.exists(os.path.dirname(output_filename)):
            print("Creating directory", os.path.dirname(output_filename),
                  flush=True)
            os.makedirs(os.path.dirname(output_filename))

        # check if exists and with latest hash
        already_synced_epub = (mobi_dir is None and
                               self.last_synced_hash == self.current_hash)
        already_synced_mobi = (mobi_dir is not None and
                               self.last_synced_hash ==
                               self.converted_to_mobi_hash)
        if (os.path.exists(output_filename) and
           (already_synced_mobi or already_synced_epub)):
                print("   - Skipping already synced ebook: ", self.filename,
                      flush=True)
                return False

        print("   + Syncing: ", self.filename, flush=True)

        if mobi_dir is None:
            shutil.copy(os.path.join(self.library_dir, self.filename),
                        output_filename)
            self.last_synced_hash = self.current_hash
        else:
            shutil.copy(os.path.join(mobi_dir, self.exported_filename),
                        output_filename)
            self.last_synced_hash = self.converted_to_mobi_hash
        return True

    def info(self, field_list=None):
        return str(self) + "\n" + "-"*len(str(self)) + "\n" + \
            self.librarian_metadata.show_fields(field_list)

    def write_metadata(self, key, value):
        if key not in self.librarian_metadata.keys:
            print("Adding new metadata field", key)
        self.librarian_metadata.set_value(key, value)

    @has_changed
    def update_metadata(self, update_list):
        # force metadata refresh
        if not self.is_opf_open:
            self.open_ebook_metadata()

        changes = ""
        for part in update_list:
            try:
                key, value = part.split(":")
                # TODO: get all values for field
                old_values = self.librarian_metadata.get_values(key)
                if value.title() not in old_values:
                    # TODO: list of unique fields
                    changes += "%s  -> %s\n" % (old_values, value.title())
                    self.write_metadata(key, value.title())

            except Exception as err:
                print("Error writing metadata", part, ":", err)
                continue  # ignore this part only

        if changes == "":
            print("No change detected.")
            return  # nothing to do

        print("Updating epub metadata:")
        print(changes)

        answer = input("Confirm update? y/n ").lower()
        if answer == 'y':
            print("Saving changes.")
            print(self.info())
            return True
        else:
            print("Discarding changes, nothing will be saved.")
            return False

    @has_changed
    def set_progress(self, read_value):
        if read_value not in ReadStatus.__members__.keys():
            return False
        print("Setting ", str(self), "as ", ReadStatus[read_value].name)
        self.read = ReadStatus[read_value]
        return True
