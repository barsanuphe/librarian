from lxml import etree
from collections import defaultdict

ns = {
    'n': 'urn:oasis:names:tc:opendocument:xmlns:container',
    'pkg': 'http://www.idpf.org/2007/opf',
    'dc': 'http://purl.org/dc/elements/1.1/'
    }

METADATA_ALIASES = {
    "year": "date",
    "author": "creator",
    }


def sanitize(name, result, author_aliases):
    if name in METADATA_ALIASES.keys():
        name = METADATA_ALIASES[name]
    if name == "creator":
        if ',' in result:
            parts = result.split(",")
            if len(parts) == 2:
                result = "%s %s" % (parts[1].strip(), parts[0].strip())
            if len(parts) > 2:
                result = "Various"
        result = result.title()
        if result in author_aliases.keys():
            result = author_aliases[result]
        return result

    if name == "date":
        try:
            return result[:4]
        except:
            return ""
    if name == "title":
        return result.replace("/", "-")

    return result


class EbookMetadata(object):

    def show_fields(self, field_list=None):
        info = ""
        for key in self.keys:
            if (field_list and key in field_list) or not field_list:
                info += "\t%s : \t%s\n" % \
                    (key, ",".join(self.get_values(key)))
        info += "\n"
        return info

    def __str__(self):
        return self.show_fields()


class FakeOpfFile(EbookMetadata):
    def __init__(self, entries, author_aliases):
        self.author_aliases = author_aliases
        self.metadata_dict = defaultdict(list)
        self.metadata_dict.update(entries)

    @property
    def keys(self):
        return sorted(self.metadata_dict.keys())

    def get_values(self, name):
        name = METADATA_ALIASES.get(name, name)
        return self.metadata_dict.get(name, [])


class OpfFile(EbookMetadata):
    def __init__(self, opf, author_aliases):
        self.opf = opf
        self.author_aliases = author_aliases
        self.tree = etree.parse(self.opf)
        self.metadata_element = self.tree.xpath('/pkg:package/pkg:metadata',
                                                namespaces=ns)[0]
        self.epub_version = self.tree.xpath('/pkg:package',
                                            namespaces=ns)[0].get("version")
        self.has_changed = False
        self.metadata_dict = defaultdict(list)
        self.parse()

    def get_elements(self, name):
        return self.metadata_dict.get(name, None)

    @property
    def keys(self):
        return sorted(self.metadata_dict.keys())

    @property
    def is_complete(self):
        return ("title" in self.keys and
                "date" in self.keys and
                "creator" in self.keys)

    def parse(self):
        for node in self.metadata_element:
            # passing comments
            if node.tag == etree.Comment:
                continue
            tag = etree.QName(node.tag)
            short_tag = tag.localname
            if short_tag == "meta" and self.epub_version == "2.0":
                if "calibre" in node.get("name"):
                    calibre_tag = node.get("name").split("calibre:")[1]
                    self.metadata_dict[calibre_tag].append(
                        sanitize(calibre_tag,
                                 node.get("content"),
                                 self.author_aliases))
                # TODO: librarian tags
            else:
                self.metadata_dict[short_tag].append(
                    sanitize(short_tag, node.text, self.author_aliases))
        for alias in METADATA_ALIASES.keys():
            self.metadata_dict[alias] = self.metadata_dict[
                METADATA_ALIASES[alias]]

    def save(self):
        with open(self.opf, 'w') as file_handle:
            file_handle.write(etree.tostring(self.tree,
                                             pretty_print=True,
                                             encoding='utf8',
                                             xml_declaration=True
                                             ).decode("utf8"))

    def get_values(self, name):
        name = METADATA_ALIASES.get(name, name)

        if name not in self.keys:
            return []  # None?

        return self.get_elements(name)

    def set_value(self, name, value, replace=False):
        name = METADATA_ALIASES.get(name, name)

        nodes = self.get_elements(name)

        # if replace, must be unambiguous
        if replace:
            assert len(nodes) == 1

        # modify or insert new metadata
        found = False
        for node in nodes:
            if not node or not replace:
                continue
            else:
                if node.text is None:  # meta
                    if node.get("name") == name and replace:
                        node.set("content", value)
                        found = True
                else:
                    if replace:
                        node.text = value
                        found = True

        if not found:
            print(" -- Creating new metadata", name, '=', value)
            if name in ["series", "series_index"]:
                self.insert_new_node(name, value, is_meta=True)
            else:
                self.insert_new_node(name, value, is_meta=False)

        self.has_changed = True
        self.save()

    def remove_value(self, name, value):
        pass  # TODO!

    def insert_new_node(self, name, value, is_meta=False):
        if is_meta:
            new_node = etree.Element("meta")
            new_node.set("name", "calibre:" + name)
            new_node.set("content", value)
            self.metadata_element.append(new_node)
        else:
            node_tag = etree.QName("http://purl.org/dc/elements/1.1/", name)
            new_node = etree.Element(node_tag)
            new_node.text = value
            self.metadata_element.append(new_node)
