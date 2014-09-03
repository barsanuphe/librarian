from lxml import etree

ns = {
        'n':'urn:oasis:names:tc:opendocument:xmlns:container',
        'pkg':'http://www.idpf.org/2007/opf',
        'dc':'http://purl.org/dc/elements/1.1/'
     }

def sanitize(name, result, author_aliases):
    if name == "creator" or name == "author":
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
        if result in list(author_aliases.keys()):
            result = author_aliases[result]
        return result

    if name == "series_index":
        try:
            return float(result)
        except:
            return ""
    if name == "year":
        try:
            return int(result[:4])
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
            return sorted([el for el in list(object.__getattribute__(self, "__dict__").keys()) if el != "author_aliases"])
        if name == "author":
            name = "creator"
        if name == "year": #TODO: do better
            return sanitize(name, object.__getattribute__(self, "__dict__").get("date", ""), object.__getattribute__(self, "author_aliases"))
        return sanitize(name, object.__getattribute__(self, "__dict__").get(name, ""), object.__getattribute__(self, "author_aliases"))

class OpfFile(object):
    def __init__(self, opf, author_aliases):
        object.__setattr__(self, "opf", opf)
        object.__setattr__(self, "author_aliases", author_aliases)
        object.__setattr__(self, "tree", etree.parse(self.opf))
        object.__setattr__(self, "metadata_element", self.tree.xpath('/pkg:package/pkg:metadata',namespaces = ns)[0])
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
        return hits[0]

    @property
    def keys(self):
        return sorted(list(self.to_dict().keys()))

    @property
    def is_complete(self):
        return ("title" in self.keys and "date" in self.keys and "creator" in self.keys)

    def to_dict(self):
        #TODO: manage multiple elements of same type
        metadata_dict = {}
        for node in self.metadata_element:
            tag = etree.QName(node.tag)
            short_tag = tag.localname
            if short_tag == "meta":
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
        if name == "year":
            node = self.get_element("date")
            return sanitize(name, node.text, self.author_aliases)

        #TODO: metadata aliases
        if name == "author":
            name = "creator"

        if name not in self.keys:
            return "" # None?

        node = self.get_element(name)
        if node.text is None: # meta
            return sanitize(name, node.get("content").title(), self.author_aliases)
        else:
            return sanitize(name, node.text.title(), self.author_aliases)

    def __setattr__(self, name, value):
        if name == "author":
            name = "creator"
        #TODO: year

        node = self.get_element(name)
        if node.text is None: # meta
            node.set("content", value)
        else:
            node.text = value
        object.__setattr__(self, "has_changed", True)
        self.save()

