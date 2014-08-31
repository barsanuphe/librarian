import os, subprocess, shutil, sys, hashlib
import codecs, json

from .epub_metadata import EpubMetadata

class Ebook(object):

    def __init__(self, path, library_dir, author_aliases):
        self.path = path
        self.library_dir = library_dir
        self.author_aliases = author_aliases
        self.tags = []
        self.metadata = None
        self.loaded_metadata = None
        self.has_changed = False

        self.was_converted_to_mobi = False
        self.converted_to_mobi_from_hash = ""
        self.converted_to_mobi_hash = ""
        self.last_synced_hash = ""

    def __getattribute__(self, key):
        # for metadata, read from self.metadata
        if object.__getattribute__(self, "metadata") is not None and key in getattr( object.__getattribute__(self, "metadata"), "keys"):
            return getattr( object.__getattribute__(self, "metadata"), key)
        else:
            try:
                return object.__getattribute__(self, key)
            except:
                return ""

    @property
    def extension(self):
        return os.path.splitext(self.path)[1][1:].lower() # extension without the .

    @property
    def current_hash(self):
        return hashlib.sha1(open(self.path, 'rb').read()).hexdigest()

    @property
    def filename(self):
        return "%s/%s (%s) %s.%s"%(self.author, self.author, self.year, self.title, self.extension)

    @property
    def exported_filename(self):
        return os.path.splitext(self.filename)[0] + ".mobi"

    def add_to_collection(self, tag):
        if tag.strip() != "" and tag.strip().lower() not in self.tags:
            self.tags.append(tag.strip().lower())
        self.has_changed = True

    def remove_from_collection(self, tag):
        if tag.strip() != "" and tag.strip().lower() in self.tags:
            self.tags.remove(tag.strip().lower())
        self.has_changed = True

    def read_metadata(self):
        try:
            self.metadata = EpubMetadata(self.path, self.author_aliases)
        except Exception as err:
            print("Impossible to read metadata for ", self.path, err)
            return False
        self.rename_from_metadata()
        self.has_changed = True
        return True

    def rename_from_metadata(self):
        if self.metadata.is_complete and self.library_dir in self.path:
            new_name = os.path.join(self.library_dir, self.filename)
            if new_name != self.path:
                if not os.path.exists( os.path.dirname(new_name) ):
                    print("Creating directory", os.path.dirname(new_name) )
                    os.makedirs( os.path.dirname(new_name) )
                print("Renaming to ", new_name)
                shutil.move(self.path, new_name)
                # refresh name
                self.path = new_name

    def export_to_mobi(self, mobi_dir):
        output_filename = os.path.join(mobi_dir, self.exported_filename)
        if os.path.exists(output_filename):
            # check if ebook has changed since the mobi was created
            if self.current_hash == self.converted_to_mobi_from_hash:
                self.was_converted_to_mobi = True
                return

        if not os.path.exists( os.path.dirname(output_filename) ):
            print("Creating directory", os.path.dirname(output_filename) )
            os.makedirs( os.path.dirname(output_filename) )

        #conversion
        print("   + Converting to .mobi: ", self.filename)
        subprocess.call(['ebook-convert', self.path, output_filename, "--output-profile", "kindle_pw"], stdout=subprocess.DEVNULL)

        self.converted_to_mobi_hash = hashlib.sha1(open(output_filename, 'rb').read()).hexdigest()
        self.converted_to_mobi_from_hash = self.current_hash
        self.was_converted_to_mobi = True
        self.has_changed = True

    def sync_with_kindle(self, mobi_dir, kindle_documents_dir):
        if not self.was_converted_to_mobi:
            self.export_to_mobi(mobi_dir)

        output_filename = os.path.join(kindle_documents_dir, self.exported_filename)

        if not os.path.exists( os.path.dirname(output_filename) ):
            print("Creating directory", os.path.dirname(output_filename) )
            os.makedirs( os.path.dirname(output_filename) )

        # check if exists and with latest hash
        if os.path.exists(output_filename) and self.last_synced_hash == self.converted_to_mobi_hash:
            #print("   - Skipping already synced .mobi: ", self.filename)
            return

        print("   + Syncing: ", self.filename)
        shutil.copy( os.path.join(mobi_dir, self.exported_filename), output_filename)
        self.last_synced_hash = self.converted_to_mobi_hash
        self.has_changed = True

    def __str__(self):
        if self.series != "":
            if self.series_index != "":
                series_info = "[ %s %s ]"%(self.series, self.series_index)
            else:
                series_info = "[ %s ]"%(self.series)
        else:
            series_info = ""
        if self.tags == []:
            return "%s (%s) %s %s"%(self.author, self.year, self.title, series_info)
        else:
            return "%s (%s) %s %s [ %s ]"%(self.author, self.year, self.title, series_info, ", ".join(self.tags))

    def to_dict(self):
        if self.has_changed:
            if not self.metadata.was_refreshed:
                self.read_metadata()
            return  {
                        "path": self.path,
                        "tags": ",".join(sorted([el for el in self.tags if el.strip() != ""])),
                        "last_synced_hash": self.last_synced_hash,
                        "converted_to_mobi_hash": self.converted_to_mobi_hash,
                        "converted_to_mobi_from_hash": self.converted_to_mobi_from_hash,
                        "metadata": self.metadata.metadata
                    }
        else:
            return self.loaded_metadata

    def to_json(self, kindle_documents_subdir):
        exported_tags = ['"%s"'%tag for tag in self.tags]
        return """\t"%s": [%s],\n"""%(os.path.join(kindle_documents_subdir, self.exported_filename), ",".join(exported_tags))

    def try_to_load_from_json(self, everything, filename):
        if not os.path.exists(everything[filename]["path"]):
            print("File %s in DB cannot be found, ignoring."%everything[filename]["path"])
            return False
        try:
            self.loaded_metadata = everything[filename]
            self.metadata = EpubMetadata(everything[filename]["path"], self.author_aliases, everything[filename]['metadata'])
            self.tags = [el.lower().strip() for el in everything[filename]['tags'].split(",") if el.strip() != ""]
            self.converted_to_mobi_hash = everything[filename]['converted_to_mobi_hash']
            self.converted_to_mobi_from_hash = everything[filename]['converted_to_mobi_from_hash']
            self.last_synced_hash = everything[filename]['last_synced_hash']
        except Exception as err:
            print("Incorrect db!", err)
            return False
        return True

