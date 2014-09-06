from lxml import etree

ns = {
        'n':'urn:oasis:names:tc:opendocument:xmlns:container',
        'pkg':'http://www.idpf.org/2007/opf',
        'dc':'http://purl.org/dc/elements/1.1/'
     }

METADATA_ALIASES = {
    "year": "date",
    "author": "creator",
    }

def sanitize(name, result, author_aliases):
    if name in METADATA_ALIASES.keys():
        name = METADATA_ALIASES[name]
    if name == "creator":
        #TODO:
        #if len(self.raw_metadata["dc:creator"]) >= 2:
            #res["author"] = "Various"
        if ',' in result:
            parts = result.split(",")
            if len(parts) == 2:
                result = "%s %s"%(parts[1].strip(), parts[0].strip())
            if len(parts) > 2:
                result = "Various"
        result = result.title()
        if result in author_aliases.keys():
            result = author_aliases[result]
        return result

    if name == "series_index":
        try:
            return result
        except:
            return ""
    if name == "date":
        try:
            return result[:4]
        except:
            return ""
    if name == "title":
        return result.replace("/", "-")

    return result

class FakeOpfFile(object):
    def __init__(self, entries, author_aliases):
        object.__setattr__(self, "author_aliases", author_aliases)
        object.__getattribute__(self, "__dict__").update(entries)
    def __getattribute__(self, name):
        if name == "keys":
            all_keys = [el for el in object.__getattribute__(self, "__dict__").keys() if el != "author_aliases"]
            all_keys.extend(METADATA_ALIASES.keys())
            return sorted(all_keys)
        name = METADATA_ALIASES.get(name, name)
        return sanitize(name, object.__getattribute__(self, "__dict__").get(name, ""), object.__getattribute__(self, "author_aliases"))

class OpfFile(object):
    def __init__(self, opf, author_aliases):
        object.__setattr__(self, "opf", opf)
        object.__setattr__(self, "author_aliases", author_aliases)
        object.__setattr__(self, "tree", etree.parse(self.opf))
        object.__setattr__(self, "metadata_element", self.tree.xpath('/pkg:package/pkg:metadata',namespaces = ns)[0])
        object.__setattr__(self, "epub_version", self.tree.xpath('/pkg:package',namespaces = ns)[0].get("version"))
        object.__setattr__(self, "has_changed", False)

    #TODO: return list when more than one element of type name exists!!
    def get_element(self, name):
        hits = []
        for node in self.metadata_element:
            tag = etree.QName(node.tag)
            short_tag = tag.localname
            if short_tag == name:
                hits.append(node)
            elif short_tag == "meta":
                if node.get("name") == "calibre:" + name:
                    hits.append(node)
        if len(hits) >= 1:
            return hits[0]
        else:
            return None

    @property
    def keys(self):
        all_keys = list(self.to_dict().keys())
        all_keys.extend(METADATA_ALIASES.keys())
        return sorted(all_keys)

    @property
    def is_complete(self):
        return ("title" in self.keys and "date" in self.keys and "creator" in self.keys)

    def to_dict(self):
        #TODO: manage multiple elements of same type
        metadata_dict = {}
        for node in self.metadata_element:
            tag = etree.QName(node.tag)
            short_tag = tag.localname
            if short_tag == "meta" and self.epub_version == "2.0":
                #TODO: test
                try:
                    metadata_dict[node.get("name").split("calibre:")[1]] = sanitize(node.get("name").split("calibre:")[1], node.get("content"), self.author_aliases)
                except:
                   # print("non calibre: ", node.get("name"))
                    pass
            else:
                metadata_dict[short_tag] = sanitize(short_tag, node.text, self.author_aliases) #TODO: test
        return metadata_dict

    def save(self):
        with open(self.opf, 'w') as file_handle:
            file_handle.write(etree.tostring(self.tree, pretty_print=True, encoding='utf8', xml_declaration=True).decode("utf8"))

    def __getattr__(self, name):
        name = METADATA_ALIASES.get(name, name)

        if name not in self.keys:
            return "" # None?

        node = self.get_element(name)
        if node.text is None: # meta
            return sanitize(name, node.get("content").title(), self.author_aliases)
        else:
            return sanitize(name, node.text.title(), self.author_aliases)

    def __setattr__(self, name, value, replace = False):
        name = METADATA_ALIASES.get(name, name)

        node = self.get_element(name)
        if node is None or replace == False:
            print("Unsupported: Creating new metadata", name, '=', value)
            if name in ["series", "series_index"]:
                new_node = etree.Element("meta")
                new_node.set("name", "calibre:"+name)
                new_node.set("content", value)
                self.metadata_element.append(new_node)
            else:
                node_tag = etree.QName("http://purl.org/dc/elements/1.1/", name)
                new_node = etree.Element(node_tag)
                new_node.text = value
                self.metadata_element.append(new_node)
        else:
            if node.text is None: # meta
                node.set("content", value)
            else:
                node.text = value
        object.__setattr__(self, "has_changed", True)
        self.save()

