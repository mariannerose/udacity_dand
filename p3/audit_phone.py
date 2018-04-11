PHONE = re.compile(r'(\+31) (\d{2}) (\d{3}) (\d{4})$')

def audit_phone(file):
    context = ET.iterparse(file, events=('end',))
    list=[]
    for event, elem in context:
        for child in elem:
            if child.tag == 'tag':
                # find tags that host the phonenumber
                if child.attrib['k'] == 'phone':
                    phone_num = child.attrib['v'] 
                    # check if the phone number is in +31 ## ### #### format
                    if PHONE.search(phone_num) is None:
                        list.append(phone_num)
    return list 