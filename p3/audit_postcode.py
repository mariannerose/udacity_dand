POSTCODE = re.compile(r'^(\d{4}) ([A-Z]{2})')

def audit_postcode(file):
    context = ET.iterparse(file, events=('end',))
    list=[]
    for event, elem in context:
        for child in elem:
            if child.tag == 'tag':
                # find tags that host the postcodes
                if child.attrib['k'] == 'addr:postcode':
                    postcode = child.attrib['v'] 
                    # check if the postcode is in XXXX AA format
                    if POSTCODE.search(postcode) is None:
                        if len(postcode) != 6:
                            list.append(postcode)
    return list                    
        