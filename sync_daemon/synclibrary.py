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
    

zotero_creds = json.loads(open('user_writing_config.json').read())  # library credentials
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


def processZoteroItem(item, zotero_date, most_recent):
     tmp_date_added = dateutil.parser.parse(item.dateAdded)

        
     #We are retrieving the items in decening order of them being created in Zotero.
     #if we come accross an item that has been added since we last ran the update daemon,
     #we have processed all new items
     if (zotero_date is not None):
          if (tmp_date_added > zotero_date):
               if (tmp_date_added > most_recent):
                    most_recent = tmp_date_added
          else:
               return False, most_recent


     skipItem = False

     #We only know how to deal with these types of entries for the moment.
     if not ((item.itemType == 'journalArticle') or (item.itemType == 'bookSection') or (item.itemType == 'book') or (item.itemType == 'thesis') or
             (item.itemType == 'report') or (item.itemType == 'conferencePaper')):
          return True, most_recent

     #Check if we have the entry in our linking database already.
     try:
          cur.execute("SELECT * FROM id_links WHERE zotero_id = \"" + item.itemKey + "\"")
          rows = cur.fetchall()
     except e:
          print e 
          return True, most_recent
     if len(rows) > 0:
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
     zotero_item = zlib.fetchItem(sys.argv[1])
     processZoteroItem(zotero_item, None, None)
     hasMoreItems = False

while (hasMoreItems):

    #Due to memory problems, create a new zlib object everytime
    zlib = zotero.Library(zotero_creds['libraryType'], zotero_creds['libraryID'], zotero_creds['librarySlug'], zotero_creds['apiKey'])
    items = zlib.fetchItems({'limit': 20, 'start': start, 'collectionKey': collectionKey, 'order': 'dateAdded', 'sort': 'desc'})
    
    print "Starting to iterate over items!"
    print zotero_date

    for i in items:
         hasMoreItems, most_recent = processZoteroItem(i, zotero_date, most_recent)

    db.commit()

    
    if 'next' in zlib._lastFeed.links:
        start += len(items)
    else:
        hasMoreItems = False

print most_recent

#unlock database
cur.execute("UPDATE updater SET zotero_date='" + str(most_recent) + "', running=0 WHERE running = 1")
db.commit()
