from apydia.descriptors import AttributeOrMethodDesc

def href(desc, anchor=None):
    if isinstance(desc, AttributeOrMethodDesc):
        return "#" + desc.name
    else:
        return "Docs_" + "".join(path.name.capitalize() for path in desc.path)


def filename(desc):
    return "Docs_" + "".join(path.name.capitalize() for path in desc.path) + ".wiki"

