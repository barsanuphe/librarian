import zipfile, xml.dom.minidom

class EpubMetadata(object):

    def __init__(self, epub_filename, author_aliases = {}, from_db = None):
        self.path = epub_filename
        self.author_aliases = author_aliases
        self.raw_metadata = {}
        self.metadata = {}
        self.is_complete = False
        self.was_refreshed = False
        if from_db is None:
            self.get_epub_metadata()
            self.sanitize_epub_metadata()
        else:
            self.metadata = from_db
            self.is_complete = ("author" in self.keys and "title" in self.keys and "year" in self.keys)

    @property
    def keys(self):
        return list(self.metadata.keys())

    def __getattr__(self, key):
        if key in list(self.metadata.keys()):
            return self.metadata[key]
        else:
            return ""

    def get_epub_metadata(self):
        # prepare to read from the .epub file
        zip = zipfile.ZipFile(self.path)

        # find the contents metafile
        txt = zip.read('META-INF/container.xml')
        tree = xml.dom.minidom.parseString(txt)
        rootfile = tree.getElementsByTagName("rootfile")[0]
        filename = rootfile.getAttribute("full-path")

        # grab the metadata block from the contents metafile
        cf = zip.read(filename)
        tree = xml.dom.minidom.parseString(cf)
        try:
            md = tree.getElementsByTagName("metadata")[0]
        except:
            md = tree.getElementsByTagName("opf:metadata")[0]
        res = {}
        for child in md.childNodes:
            if child.nodeName == "meta":
                if child.hasAttribute("name") and child.getAttribute("name") == "calibre:series":
                    res["series"] = child.getAttribute("content")
                elif child.hasAttribute("name") and child.getAttribute("name") == "calibre:series_index":
                    res["series_index"] = child.getAttribute("content")

            elif child.hasChildNodes() and child.firstChild.nodeType == xml.dom.Node.TEXT_NODE:
                if child.nodeName in list(res.keys()):
                    res[child.nodeName].append(child.firstChild.data)
                else:
                    res[child.nodeName] = [child.firstChild.data]
        self.raw_metadata = res

    def sanitize_epub_metadata(self):
        res = {}
        try:
            if len(self.raw_metadata["dc:creator"]) >= 2:
                res["author"] = "Various"
            else:
                res["author"] = self.raw_metadata["dc:creator"][0]
                if ',' in res["author"]:
                    parts = res["author"].split(",")
                    if len(parts) == 2:
                        res["author"] = "%s %s"%(parts[1].strip(), parts[0].strip())
                    if len(parts) > 2:
                        res["author"] = "Various"
            res["author"] = res["author"].title()
            if res["author"] in list(self.author_aliases.keys()):
                res["author"] = self.author_aliases[res["author"]]

            res["title"] = self.raw_metadata["dc:title"][0].replace(":", "").replace("?","").replace("/", "-").title()
            res["year"] = int(self.raw_metadata["dc:date"][0][:4])
            res["lang"] = self.raw_metadata["dc:language"][0]
            if "series" in list(self.raw_metadata.keys()):
                res["series"] = self.raw_metadata["series"].title()
            if "series_index" in list(self.raw_metadata.keys()):
                res["series_index"] = int(float(self.raw_metadata["series_index"]))

        except Exception as err:
            print("!!!!! ", err, "!!!! \n")
            return None
        self.is_complete = True
        self.was_refreshed = True
        self.metadata = res

if __name__ == "__main__":
    md = EpubMetadata("test.epub")
    print(md.metadata)
    print(md.author)
