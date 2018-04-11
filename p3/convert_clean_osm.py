import csv
import codecs
import pprint
import re
import xml.etree.cElementTree as ET

import cerberus

import schema

OSM_PATH = "leiden.osm"

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')
# two additional regular expressions
PHONE = re.compile(r'(\+31) (\d{2}) (\d{3}) (\d{4})$')
POSTCODE = re.compile(r'^(\d{4}) ([A-Z]{2})')

SCHEMA = schema.schema

# Make sure the fields order in the csvs matches the column order in the sql table schema
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']


# helper code to clean postcodes to correct XXXX AA format
def fix_postcode(postcode):
    if POSTCODE.search(postcode) is None:
        if len(postcode)==6:
            return postcode[:4] + ' ' + postcode[4:7]
        # return placeholder for postcodes which are incomplete, these entries can then easily identified in sql
        else:
            return 'XXXX AA'
    else:
        return postcode

# helper code to clean phonenumbers to correct +31 ## ### #### format
def fix_phone_num(phone_num): 
    # if the phonenumber is not in the correct format
    if PHONE.search(phone_num) is None:    
        # remove dashes
        if "-" in phone_num:
            phone_num = phone_num.replace('-','')
        # remove spaces
        if " " in phone_num:
            phone_num = phone_num.replace(' ','')
        # remove (0)
        if "(0)" in phone_num:
            phone_num = phone_num.replace('(0)','')
        # replace starting 0 with +31
        if phone_num[0] == '0':
            phone_num = '+31' + phone_num[1:]
        # replace starting 3 with +31
        if phone_num[0] == '3':
            phone_num = '+31' + phone_num[2:]
        # add country code to number
        if phone_num[0] == '7':
            phone_num = '+31' + phone_num[0:] 
        # remove extra 0 after country code
        if '+310' in phone_num:
            phone_num = phone_num[:3] + phone_num[4:]
        # put phonenumber in correct format
        return phone_num[:3] + ' ' + phone_num[3:5] + ' ' + phone_num[5:8] + ' ' + phone_num[8:12]
    else:
        return phone_num        
        

def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""
    
    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = []  
    i = 0
    if element.tag == 'node':
        for field in NODE_FIELDS:
            node_attribs[field]=element.attrib[field]           
    if element.tag == 'way':
        for field in WAY_FIELDS:
            way_attribs[field]=element.attrib[field]
            
    for child in element:
        if child.tag == 'tag':
            d={}
            # check if there are any problem char if None found contine, 
            # if found tag is not taken into account
            if PROBLEMCHARS.search(child.attrib['k']) == None:
                d['id']=element.attrib['id']                    
            
                # fixing phone numbers
                if child.attrib['k'] == 'phone':
                    phone_num = child.attrib['v']
                    phone_number = fix_phone_num(phone_num)
                    d['value'] = phone_number

                # fixing postcodes
                elif child.attrib['k'] == 'addr:postcode':
                    postcode = child.attrib['v']
                    postal_code = fix_postcode(postcode)
                    d['value'] = postal_code
                
                # if now key is not related to phonenumber or postcode
                else:
                    d['value']=child.attrib['v']                  
            
                # if key has colon
                if LOWER_COLON.search(child.attrib['k']):
                    d['key'] = (child.attrib['k']).split(':',1)[1]
                    d['type'] = (child.attrib['k']).split(':',1)[0]
                else:
                    d['key']=child.attrib['k']
                    d['type']='regular'
                tags.append(d)
                d={}
        
        elif child.tag == 'nd':
            d={}
            d['id'] = element.attrib['id']
            d['node_id'] = child.attrib['ref'] 
            d['position'] = i
            i +=1
            way_nodes.append(d)
            d={}
    
    if element.tag == 'node':
        return {'node': node_attribs, 'node_tags': tags}
    elif element.tag == 'way':
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}



# ================================================== #
#               Helper Functions                     #
# ================================================== #
def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)
        
        raise Exception(message_string.format(field, error_string))


class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# ================================================== #
#               Main Function                        #
# ================================================== #
def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'w') as nodes_file, \
         codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
         codecs.open(WAYS_PATH, 'w') as ways_file, \
         codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file, \
         codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                if validate is True:
                    validate_element(el, validator)

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])


if __name__ == '__main__':
    # Note: Validation is ~ 10X slower. For the project consider using a small
    # sample of the map when validating.
    process_map(OSM_PATH, validate=True)