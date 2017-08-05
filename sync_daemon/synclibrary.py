#!/usr/bin/python

# This file is part of WikiPapers2.

# WikiPapers2 is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# WikiPapers2 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with WikiPapers2.  If not, see <http://www.gnu.org/licenses/>.

#Copyright Kai Krueger 2015
#Copyright Kai Krueger 2017

import sys
import json
import pprint
import MySQLdb
import os
import dateutil.parser
from libZotero import zotero
from unidecode import unidecode
from datetime import datetime
import pytz
import string
import re
import urllib2


zotero_creds = json.loads(open('zotero_config.json').read())  # library credentials
db_creds = json.loads(open('database_config.json').read())  # library credentials

pp = pprint.PrettyPrinter(indent=4)

#These are used to filter out special characters from names
not_letters_or_digits = u'!"#%\'()*+,./:;<=>?@[\]^_`{|}~ '
not_letters_or_digits_d = u'!"#%\'()*+,./:;<=>?@[\]^_`{|}~ -'

translate_table = dict((ord(char), None) for char in not_letters_or_digits)
translate_table_d = dict((ord(char), None) for char in not_letters_or_digits_d)

translate_table[8220] = None
translate_table[8221] = None




db = MySQLdb.connect(host=db_creds["host"], # your host, usually localhost
                     user=db_creds["user"], # your username
                     passwd=db_creds["passwd"], # your password
                     db=db_creds["db"],
                     charset='utf8') # name of the data base

cur = db.cursor()

if (len(sys.argv) > 1):
     if (sys.argv[1] == "help"):
          print "Please use one of 5 commands: \"add\", \"addbibkey\", \"del\", \"delbibkey\" and \"resync\",  \"unlock\" or \"lockcheck\". Add and del each take a zotero ID. Addbibkey and delbibkey take a bibkey"
          exit()
     if (sys.argv[1] == "unlock"):
          hasMoreItems = False;
          sql = "UPDATE updater SET running=0;";
          try:
               cur.execute(sql)
          except MySQLdb.IntegrityError:
               print "Error, could not unlock database"
          db.commit()
          exit()
     if (sys.argv[1] == "lockcheck"):
          sql = "SELECT update_date FROM updater WHERE running=1"
          try:
               cur.execute(sql)
          except MySQLdb.IntegrityError:
               print "Error, could not check locking database"
          rows = cur.fetchall();
          if (len(rows) > 0):
               print rows[0][0]
          exit()
          

#Lock database to ensure we aren't running multiple copies of the updater script
try:
     cur.execute("SELECT pid FROM updater")
except:
    print "Failed to get details of update process from database"
    exit()
    
rows = cur.fetchall()
if (len(rows) < 1):
    try:
        cur.execute("INSERT INTO updater VALUES('2015-05-01', '" + str(datetime.now()) + "', " + str(os.getpid()) + ", 1)")
    except:
        print "Failed to insert initial value into database"
else:
    try:
        cur.execute("UPDATE updater SET pid=" + str(os.getpid()) + ", running=1, update_date='" + str(datetime.now()) + "' WHERE running = 0")
        db.commit()
    except:
        print "Failed to lock update table"
        exit()
cur.execute("SELECT zotero_date FROM updater WHERE pid=" + str(os.getpid()) + " AND running=1")
rows = cur.fetchall();
if (len(rows) < 1):
    print "Update process already locked. Exiting!"
    exit()
zotero_date = pytz.utc.localize(rows[0][0])

db.commit()


def testWikiKeyDuplicate(wikiid, item):
    try:
        cur.execute("SELECT zotero_id FROM id_links WHERE wiki_id = \"" + wikiid + "\"")
    except:
        return wikiid
    rows = cur.fetchall()
    if (len(rows) < 1):
        print wikiid + " not in db"
        return wikiid
    else:
        for letter in list(string.ascii_lowercase):
            wikiid_tmp = wikiid + letter
            try:
                cur.execute("SELECT zotero_id FROM id_links WHERE wiki_id = \"" + wikiid_tmp + "\"")
            except:
                return wikiid
            rows = cur.fetchall()
            if (len(rows) < 1):
                if letter == 'a':
                    continue
                return wikiid_tmp


def processZoteroItem(item, zotero_date, most_recent, verbose):
     tmp_date_added = dateutil.parser.parse(item.dateAdded)

        
     #We are retrieving the items in decening order of them being created in Zotero.
     #if we come accross an item that has been added since we last ran the update daemon,
     #we have processed all new items
     if (zotero_date is not None):
          if (tmp_date_added > zotero_date):
               if (tmp_date_added > most_recent):
                    most_recent = tmp_date_added
          else:
               if verbose:
                    print "Not processing entry, as its older than the reference data"
               return False, most_recent


     skipItem = False

     #We only know how to deal with these types of entries for the moment.
     if not ((item.itemType == 'journalArticle') or (item.itemType == 'bookSection') or (item.itemType == 'book') or (item.itemType == 'thesis') or
             (item.itemType == 'report') or (item.itemType == 'conferencePaper')):
          if verbose:
               print "Not processing item, as it is not one of the supported types"
          return True, most_recent

     #Check if we have the entry in our linking database already.
     print item.itemKey;
     try:
          cur.execute("SELECT * FROM id_links WHERE zotero_id = \"" + item.itemKey + "\"")
          rows = cur.fetchall()
     except e:
          print e 
          return True, most_recent
     if len(rows) > 0:
          if verbose:
               print "Not processing item, as it is already in the database"
          return True, most_recent

     #Check if we have a bibkey entry in the extra field of the zotero database. If yes, we will use that. If not we try and create our own bibkey
     if ('extra' in item.pristine) and ('bibtex' in item.pristine['extra']):
          m = re.search('.*bibtex: (\S+).*',item.pristine['extra'])
          wikiid = m.group(1)
     else:
          #If we don't have a year, we can't process the corresponding wiki key
          if item.year == "":
               print "****** No year available for " + item.itemKey + " ******"
               return True, most_recent
        
          wikiid = ""
          noAuthors = 0
          for a in item.creators:
               if a['creatorType'] != 'author':
                    continue
               if noAuthors == 3:
                    wikiid += "EtAl"
                    break
               if not 'lastName' in a:
                    skipItem = True
                    break
               wikiid += unidecode(a['lastName'].translate(translate_table))
               noAuthors += 1
            
          if (item.itemType == 'book' and noAuthors == 0):
               for a in item.creators:
                    if a['creatorType'] != 'editor':
                         continue
                    if noAuthors == 3:
                         wikiid += "EtAl"
                         break
                    if not 'lastName' in a:
                         skipItem = True
                         break
                    wikiid += unidecode(a['lastName'].translate(translate_table))
                    noAuthors += 1

          if skipItem:
               print "****** No valid authors provided for " + item.itemKey + " ******"
               return True, most_recent

          wikiid += item.year[-2:]

            
     sql = "INSERT INTO id_links (wiki_id, zotero_id) VALUES ( \"" + wikiid + "\", \"" + item.itemKey + "\")"
     try:
          cur.execute(sql)
     except MySQLdb.IntegrityError:
          #We already have this wiki key. Check if this entry might have been deleted
          print "Duplicate key detected for wiki_id " + wikiid
          #Querry what the zotero id is for this wiki entry.
          sql = "SELECT zotero_id FROM id_links WHERE wiki_id = \"" + wikiid + "\""
          try:
               cur.execute(sql)
               rows = cur.fetchall()
          except:
               print "*!*!*! Really couldn't deal with this entry"
               return True, most_recent
          print "Duplicate was " + rows[0][0]
          try:
               zotero_item2 = zlib.fetchItem(rows[0][0])
               if (not zotero_item2):
                    raise exception()
          except:
               print "Item was deleted for which we are creating a duplicate "
               sql = "DELETE FROM id_links WHERE zotero_id=\"" + rows[0][0] + "\"";
               try:
                    cur.execute(sql)
               except MySQLdb.IntegrityError:
                    print "Error, could not delete item "
               #Now that we have deleted the entry, try reinserting it
               sql = "INSERT INTO id_links (wiki_id, zotero_id) VALUES ( \"" + wikiid + "\", \"" + item.itemKey + "\")"
               try:
                    cur.execute(sql)
                    print(item.itemKey + " => " + wikiid)
                    return True, most_recent
               except:
                    print "Failed to add entry"
          #We already have this wiki key. Create a new key with a lettered suffix
          wikiid = testWikiKeyDuplicate(wikiid, item)
          sql = "INSERT INTO id_links (wiki_id, zotero_id) VALUES ( \"" + wikiid + "\", \"" + item.itemKey + "\")"
          try:
               cur.execute(sql)
          except MySQLdb.IntegrityError:
                    print "*!*!*! " + wikiid + " duplicate !*!*!*"
                    return True, most_recent
     except MySQLdb.ProgrammingError:
          print "ERROR: " + sql
          exit()
        
     print(item.itemKey + " => " + wikiid)

     return True, most_recent
        

#Setup zoteroLib
zlib = zotero.Library(zotero_creds['libraryType'], zotero_creds['libraryID'], zotero_creds['librarySlug'], zotero_creds['apiKey'])
collectionKey = None


hasMoreItems = True
start = 0;

most_recent = zotero_date


if (len(sys.argv) > 1):
          
     if (sys.argv[1] == "add"):
          hasMoreItems = False;
          if (len(sys.argv) > 2): 
               zotero_item = zlib.fetchItem(sys.argv[2])
               if (not zotero_item):
                    print "Failed to retrieve zotero item for ID " + sys.argv[2]
                    exit()
               print zotero_item
               zotero_date = pytz.utc.localize(datetime(1900, 1, 1, 0, 0, 0));
               processZoteroItem(zotero_item, None, None, True)

     if (sys.argv[1] == "del"):
          hasMoreItems = False;
          if (len(sys.argv) > 2):
               sql = "DELETE FROM id_links WHERE zotero_id=\"" + sys.argv[2] + "\"";
               try:
                    cur.execute(sql)
               except MySQLdb.IntegrityError:
                    print "Error, could not delete item "

     if (sys.argv[1] == "delbibkey"):
          hasMoreItems = False;
          if (len(sys.argv) > 2):
               sql = "DELETE FROM id_links WHERE wiki_id=\"" + sys.argv[2] + "\"";
               try:
                    cur.execute(sql)
               except MySQLdb.IntegrityError:
                    print "Error, could not delete item "

     if (sys.argv[1] == "addbibkey"):
          hasMoreItems = False;
          print "Processing bibkey " + sys.argv[2]
          if (len(sys.argv) > 2):
               # The search functionality doesn't seem to find bibkey entries in the normal extra field. So we need to hack a workaround
               # The attachment titels use the bibkey, so the search allows to find those. So use that, and then chain up to the parent entry to add.
               # Also libZotero doesn't seem to support this at this point. So manually implement this call to the API
               contents = urllib2.urlopen("https://api.zotero.org/groups/" + str(zotero_creds['libraryID']) + "/items?qmode=everything&itemType=attachment&q=" + str(sys.argv[2])).read()
               zotero_api_entry = json.loads(contents)
               if (zotero_api_entry is not None):
                    if (len(zotero_api_entry) > 0):
                         print "Found Zotero ID for entry: " + zotero_api_entry[0]["data"]["parentItem"]

                         #We also need to add the old zotero id from the database, in case that was linked wrongly as well. E.g. before renaming key.
                         sql = "DELETE FROM id_links WHERE zotero_id=\"" + zotero_api_entry[0]["data"]["parentItem"] + "\"";
                         try:
                              cur.execute(sql)
                         except MySQLdb.IntegrityError:
                              print "Error, could not delete item "
                         zotero_item = zlib.fetchItem(zotero_api_entry[0]["data"]["parentItem"])
                         if (not zotero_item):
                              print "Failed to retrieve zotero item for ID " + zotero_api_entry[0]["data"]["parentItem"]
                              exit()
                         print zotero_item
                         zotero_date = pytz.utc.localize(datetime(1900, 1, 1, 0, 0, 0));
                         processZoteroItem(zotero_item, None, None, True)

               
               
     if (sys.argv[1] == "resync"):
          zotero_date = pytz.utc.localize(datetime(1900, 1, 1, 0, 0, 0));
          

while (hasMoreItems):

    #Due to memory problems, create a new zlib object everytime
    zlib = zotero.Library(zotero_creds['libraryType'], zotero_creds['libraryID'], zotero_creds['librarySlug'], zotero_creds['apiKey'])
    items = zlib.fetchItems({'limit': 20, 'start': start, 'collectionKey': collectionKey, 'order': 'dateAdded', 'sort': 'desc'})
    
    print "Starting to iterate over items!"
    print zotero_date

    for i in items:
         hasMoreItems, most_recent = processZoteroItem(i, zotero_date, most_recent, False)

    db.commit()

    
    if 'next' in zlib._lastFeed.links:
        start += len(items)
    else:
        hasMoreItems = False

print most_recent

#unlock database
cur.execute("UPDATE updater SET zotero_date='" + str(most_recent) + "', running=0 WHERE running = 1")
db.commit()
