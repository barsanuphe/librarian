import tempfile, shutil, os, subprocess, hashlib, zipfile
from lxml import etree

from .epub_metadata import OpfFile, FakeOpfFile, ns

AUTHORIZED_TEMPLATE_PARTS = {
    "$a": "author",
    "$y": "year",
    "$t": "title",
    "$s": "series",
    "$i": "series_index",
}

class Epub(object):

    def __init__(self, path, library_dir, author_aliases, ebook_filename_template):
        self.path = path
        self.library_dir = library_dir
        self.author_aliases = author_aliases

        self.is_opf_open = False
        self.metadata_filename = ""
        self.metadata = None
        self.temp_dir = tempfile.mkdtemp()
        self.tags = []
        self.has_changed = False
        self.loaded_metadata = None
        self.template = ebook_filename_template
        self.was_converted_to_mobi = False
        self.converted_to_mobi_from_hash = ""
        self.converted_to_mobi_hash = ""
        self.last_synced_hash = ""

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def __str__(self):
        if self.metadata.series != "":
            if self.metadata.series_index != "":
                series_info = "[ %s %s ]"%(self.metadata.series, self.metadata.series_index)
            else:
                series_info = "[ %s ]"%(self.metadata.series)
        else:
            series_info = ""

        if self.tags == []:
            return "%s (%s) %s %s"%(self.metadata.author, self.metadata.year, self.metadata.title, series_info)
        else:
            return "%s (%s) %s %s [ %s ]"%(self.metadata.author, self.metadata.year, self.metadata.title, series_info, ", ".join(self.tags))

    @property
    def extension(self):
        return os.path.splitext(self.path)[1][1:].lower() # extension without the .

    @property
    def current_hash(self):
        return hashlib.sha1(open(self.path, 'rb').read()).hexdigest()

    def set_filename_template(self, template):
        self.template = template

    @property
    def filename(self):
        template = self.template
        for key in list(AUTHORIZED_TEMPLATE_PARTS.keys()):
            template = template.replace(key, str(getattr(self.metadata, AUTHORIZED_TEMPLATE_PARTS[key])))
        template = template.replace(":", "").replace("?","")
        return "%s.%s"%(template, self.extension)

    @property
    def exported_filename(self):
        return os.path.splitext(self.filename)[0] + ".mobi"

    def load_from_database_json(self, filename_dict, filename):
        if not os.path.exists(filename_dict["path"]):
            print("File %s in DB cannot be found, ignoring."%filename_dict["path"])
            return False
        try:
            self.loaded_metadata = filename_dict
            self.metadata = FakeOpfFile(filename_dict['metadata'], self.author_aliases) # for similar interface to OpfFile
            self.tags = [el.lower().strip() for el in filename_dict['tags'].split(",") if el.strip() != ""]
            self.converted_to_mobi_hash = filename_dict['converted_to_mobi_hash']
            self.converted_to_mobi_from_hash = filename_dict['converted_to_mobi_from_hash']
            self.last_synced_hash = filename_dict['last_synced_hash']
        except Exception as err:
            print("Incorrect db!", err)
            return False
        return True

    def to_database_json(self):
        if self.has_changed or self.is_opf_open:
            if not self.is_opf_open:
                self.open_metadata()
            return  {
                        "path": self.path,
                        "tags": ",".join(sorted([el for el in self.tags if el.strip() != ""])),
                        "last_synced_hash": self.last_synced_hash,
                        "converted_to_mobi_hash": self.converted_to_mobi_hash,
                        "converted_to_mobi_from_hash": self.converted_to_mobi_from_hash,
                        "metadata": self.metadata.to_dict()
                    }
        else:
            return self.loaded_metadata

    def open_metadata(self):
        if not self.is_opf_open:
            self.extract_opf_file()
            self.is_opf_open = True

    def extract_opf_file(self):
        zip = zipfile.ZipFile(self.path)
        # find the contents metafile
        txt = zip.read('META-INF/container.xml')
        tree = etree.fromstring(txt)

        self.metadata_filename = tree.xpath('n:rootfiles/n:rootfile/@full-path',namespaces=ns)[0]
        self.temp_opf = os.path.join(self.temp_dir, os.path.basename(self.metadata_filename))

        cf = zip.read(self.metadata_filename)
        with open(self.temp_opf, "w") as opf:
            opf.write(cf.decode("utf8"))

        self.metadata = OpfFile(self.temp_opf, self.author_aliases)

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
        if self.is_open and self.metadata.has_changed:
            print("Saving epub...")
            self.remove_from_zip(self.path, self.metadata_filename)
            with zipfile.ZipFile(self.path, 'a') as z:
                z.write(self.temp_opf, arcname = self.metadata_filename)

    def close_metadata(self):
        self.is_open = False
        #clean up
        self.__exit__(None, None, None)

    def add_to_collection(self, tag):
        if tag.strip() != "" and tag.strip().lower() not in self.tags:
            self.tags.append(tag.strip().lower())
        self.has_changed = True

    def remove_from_collection(self, tag):
        if tag.strip() != "" and tag.strip().lower() in self.tags:
            self.tags.remove(tag.strip().lower())
        self.has_changed = True

    def get_relative_path(self, path):
        return path.split(self.library_dir)[1][1:]

    def rename_from_metadata(self):
        if not self.is_opf_open:
            self.open_metadata()
        if self.metadata.is_complete and self.library_dir in self.path:
            new_name = os.path.join(self.library_dir, self.filename)
            if new_name != self.path:
                if not os.path.exists( os.path.dirname(new_name) ):
                    print("Creating directory", self.get_relative_path(os.path.dirname(new_name)) )
                    os.makedirs( os.path.dirname(new_name) )
                print("Renaming to ", self.get_relative_path(new_name))
                shutil.move(self.path, new_name)
                # refresh name
                self.path = new_name
                self.has_changed = True

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
        subprocess.check_call(['ebook-convert', self.path, output_filename, "--output-profile", "kindle_pw"], stdout=subprocess.DEVNULL)

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
            print("   - Skipping already synced .mobi: ", self.filename)
            return

        print("   + Syncing: ", self.filename)
        shutil.copy( os.path.join(mobi_dir, self.exported_filename), output_filename)
        self.last_synced_hash = self.converted_to_mobi_hash
        self.has_changed = True

    def info(self, field_list = None):
        info = str(self) + "\n" + "-"*len(str(self)) + "\n"
        for key in self.metadata.keys:
            if (field_list and key in field_list) or not field_list:
                info += "\t%s : \t%s\n"%(key, getattr(self.metadata, key))
        info += "\n"
        return info
