#
# Example python script to generate a BOM from a KiCad generic netlist
#
# Example: Sorted and Grouped CSV BOM
#

"""
    @package
    Output: CSV (comma-separated)
    Grouped By: Value
    Sorted By: Ref
    Fields: Item, Qty, Reference(s), Value, LibPart, Footprint, Datasheet, all additional symbol fields

    Outputs ungrouped components first, then outputs grouped components.

    Command line:
    python "pathToFile/bom_csv_grouped_by_value.py" "%I" "%O.csv"
"""

from __future__ import print_function

# Import the KiCad python helper module and the csv formatter
import kicad_netlist_reader
import csv
import sys

# A helper function to convert a UTF8/Unicode/locale string read in netlist
# for python2 or python3 (Windows/unix)
def fromNetlistText( aText ):
    currpage = sys.stdout.encoding      #the current code page. can be none
    if currpage is None:
        return aText
    if currpage != 'utf-8':
        try:
            return aText.encode('utf-8').decode(currpage)
        except UnicodeDecodeError:
            return aText
    else:
        return aText

def myEqu(self, other):
    """myEqu is a more advanced equivalence function for components which is
    used by component grouping. Normal operation is to group components based
    on their value and footprint.

    In this example of a custom equivalency operator we compare the
    value, the part name and the footprint.
    """
    result = True
    if self.getValue() != other.getValue():
        result = False
    elif self.getPartName() != other.getPartName():
        result = False
    elif self.getFootprint() != other.getFootprint():
        result = False

    return result



def groupComponents(self, components = None):
    """Return a list of component lists. Components are grouped together
    when the value, library and part identifiers match.

    Keywords:
    components -- is a list of components, typically an interesting subset
    of all components, or None.  If None, then all components are looked at.
    """
    if not components:
        components = self.components

    groups = []

    # Make sure to start off will all components ungrouped to begin with
    for c in components:
        c.grouped = False

    # Group components based on the value, library and part identifiers
    for c in components:
        if c.grouped == False:
            c.grouped = True
            newgroup = []
            newgroup.append(c)

            # Check every other ungrouped component against this component
            # and add to the group as necessary
            for ci in components:
                if ci.grouped == False and ci == c:
                    newgroup.append(ci)
                    ci.grouped = True

            # Add the new component group to the groups list
            groups.append(newgroup)

    # The key to sort the components in the BOM
    # This sorts using a natural sorting order (e.g. 100 after 99), and if it wasn't used
    # the normal sort would place 100 before 99 since it only would look at the first digit.
    def sortKey( str ):
        return [ int(t) if t.isdigit() else t.lower()
                for t in re.split( '(\d+)', str ) ]

    for g in groups:
        #g = sorted(g, key=lambda g: sortKey(g.getRef()))
        g.sort(key=lambda g: sortKey(g.getRef()))

    # Finally, sort the groups to order the references alphabetically
    groups.sort(key=lambda group: sortKey(group[0].getRef()))

    return groups




# Override the component equivalence operator - it is important to do this
# before loading the netlist, otherwise all components will have the original
# equivalency operator.
kicad_netlist_reader.comp.__eq__ = myEqu

if len(sys.argv) != 3:
    print("Usage ", __file__, "<generic_netlist.xml> <output.csv>", file=sys.stderr)
    sys.exit(1)


# Generate an instance of a generic netlist, and load the netlist tree from
# the command line option. If the file doesn't exist, execution will stop
net = kicad_netlist_reader.netlist(sys.argv[1])

# Open a file to write to, if the file cannot be opened output to stdout
# instead
try:
    f = open(sys.argv[2], 'w')
except IOError:
    e = "Can't open output file for writing: " + sys.argv[2]
    print( __file__, ":", e, sys.stderr )
    f = sys.stdout

row = []

# subset the components to those wanted in the BOM, controlled
# by <configure> block in kicad_netlist_reader.py
components = net.getInterestingComponents()

compfields = net.gatherComponentFieldUnion(components)
partfields = net.gatherLibPartFieldUnion()

# remove Reference, Value, Datasheet, and Footprint, they will come from 'columns' below
partfields -= set( ['Reference', 'Value', 'Datasheet', 'Footprint'] )

columnset = compfields | partfields     # union

# prepend an initial 'hard coded' list and put the enchillada into list 'columns'
columns = ['Item', 'Qty', 'Reference(s)', 'Value', 'LibPart', 'Footprint', 'Datasheet'] + sorted(list(columnset))

# Create a new csv writer object to use as the output formatter
out = csv.writer( f, lineterminator='\n', delimiter=',', quotechar='\"', quoting=csv.QUOTE_ALL )

# override csv.writer's writerow() to support encoding conversion (initial encoding is utf8):
def writerow( acsvwriter, columns ):
    utf8row = []
    for col in columns:
        utf8row.append( fromNetlistText( str(col) ) )
    acsvwriter.writerow( utf8row )

# Output a set of rows as a header providing general information
# writerow( out, ['Source:', net.getSource()] )
# writerow( out, ['Date:', net.getDate()] )
# writerow( out, ['Tool:', net.getTool()] )
# writerow( out, ['Generator:', sys.argv[0]] )
# writerow( out, ['Component Count:', len(components)] )
writerow( out, [] )


writerow( out, ['Collated Components:'] )
writerow( out, [] )                        # blank line
writerow( out, columns )                   # reuse same columns



# Get all of the components in groups of matching parts + values
# (see kicad_netlist_reader.py)
grouped = net.groupComponents(components)


# Output component information organized by group, aka as collated:
item = 0
for group in grouped:
    del row[:]
    refs = ""

    # Add the reference of every component in the group and keep a reference
    # to the component so that the other data can be filled in once per group
    for component in group:
        if len(refs) > 0:
            refs += ", "
        refs += component.getRef()
        c = component

    # Fill in the component groups common data
    # columns = ['Item', 'Qty', 'Reference(s)', 'Value', 'LibPart', 'Footprint', 'Datasheet'] + sorted(list(columnset))
    item += 1
    row.append( item )
    row.append( len(group) )
    row.append( refs );
    row.append( c.getValue() )
    row.append( c.getLibName() + ":" + c.getPartName() )
    row.append( net.getGroupFootprint(group) )
    row.append( net.getGroupDatasheet(group) )

    # from column 7 upwards, use the fieldnames to grab the data
    for field in columns[7:]:
        row.append( net.getGroupField(group, field) );

    writerow( out, row  )

f.close()
