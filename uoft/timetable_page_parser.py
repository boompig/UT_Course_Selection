#################################################
#	PARSING U OF T COURSE TIMETABLE WEB PAGE	#
#	WRITTEN BY DANIEL KATS						#
#################################################

#####################
# 	MODULES			#
#####################

import logging
import os
import pickle as pickler  # for saving inventory...
import re  # for soup matching
import sqlite3
import traceback  # for tracing SQL exceptions
import urllib.error
import urllib.parse
import urllib.request  # for downloading web pages
from argparse import ArgumentParser
from typing import List

import coloredlogs
import requests
from bs4 import BeautifulSoup
from pprint import pprint

#########################
# 	GLOBAL VARS			#
#########################

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)

course_code_pattern = r"\w\w\w\d\d\d\w\d"
PAGES_DIR = "tables"
DATA_FILE = "timetable_inventory.data"
DB_PATH = "./data/archive-capture-2012-2013/courses-new.db"

#########################
# 	UTILITY FUNCTIONS	#
#########################

def html_to_str(html):
	'''Convert HTML special characters into normal characters.'''

	convert_dict = {"&amp;": "&",
					"&gt;": ">",
					"&lt;": "<",
					"&nbsp;": " "
					}

	for k, v in convert_dict.items():
		html = str(html).replace(k, v)

	return html

#####################
# 	CODE			#
#####################

class PageParseException(Exception):
	pass


class TimetableParser:
	'''This object is used to extract information from the timetable webpage.'''

	@staticmethod
	def parse(page_file_path: str) -> List[dict]:
		'''The main method. Given a path to the web page, extract timetable info and return it as a list of dictionaries.'''

		logger.debug("Trying to parse file %s", page_file_path)

		l = [] # type: List[dict]

		try:
			page_file = open(page_file_path, "r")
			soup = BeautifulSoup(page_file.read(), features="html.parser")

			dept_name = TimetableParser._get_department_name(soup)

			if dept_name is None:
				print("[ERROR] Could not extract department name")
			else:
				main_soup = TimetableParser._get_functional_soup(soup, dept_name)
				# print main_soup

				if main_soup is None:
					print("[ERROR] Failed to extract functional soup")
				else:
					course_list = TimetableParser._get_course_list(main_soup)

					if len(course_list) == 0:
						print("[WARNING] No courses found on page")

					for course_html in course_list:
						last_row = l[-1] if len(l) > 0 else None
						d = TimetableParser._get_course_info(course_html, last_row)

						if d is None:
							pass # no info extracted, junk row
						elif len(d) == 0:
							# this is a sign that there is an error
							print("[WARNING] No info extracted from matched row")
							print(course_html)
						else:
							l.append(d)

			# close the page
			page_file.close()
			return l
		except PageParseException as e:
			logging.error("Failed to parse file: %s", page_file_path)
			logging.error(e)
			raise e

	@staticmethod
	def _get_department_name(all_soup: BeautifulSoup) -> str:
		'''Given the HTML soup for a page, extract the department name and return it.
		If cannot extract it, return None.
		It is assumed to be the first h1 element on the page.'''

		heading = all_soup.h2.font
		if heading is None:
			heading = all_soup.find("h2")
		txt = heading.text

		# raise PageParseException("failed to get department name")

		if txt:
			m = re.search(r"(.*?)\s*?(\[\w\w\w (.*?)courses?(.*?)\])", txt)

			if m:
				# first group is name, second is code prefix
				return m.groups(1)  # type: ignore
			else:
				raise PageParseException("Could not match name and dept. code in %s" % txt)
		else:
			raise PageParseException("Could not extract department name tag")

	@staticmethod
	def _get_functional_soup(all_soup: BeautifulSoup, name: str) -> BeautifulSoup:
		'''Given the entire web page soup and the name of the department, get a partial soup.
		This will exclude the program description and professors, only including courses.
		Also exclude standard university footer.
		Remove junk characters from the soup.'''

		# remove HTML special characters
		all_soup = BeautifulSoup(html_to_str(all_soup), "html.parser")

		return all_soup.table

	@staticmethod
	def _get_course_list(fsoup):
		'''Given a soup of course codes, course descriptions and such, return a list of sections that represent the courses.'''

		return [str(item) for item in fsoup.findAll("tr")]

	@staticmethod
	def _get_course_info(html_string, last_row=None):
		'''html_string here is a row element in the table.
		Course info is in the form of a dictionary.'''

		d = {}

		row_soup = BeautifulSoup(html_string, "html.parser")
		cols = row_soup.findAll("td")

		col_headings = ["code", "term", "name", "section", "waitlist", "time", "location", "instructor", "EnrollmentCode", "EnrollmentControlLink"]

		for index, col in enumerate(cols):
			txt = col.text.strip()

			if index == 0:
				code = re.search(course_code_pattern, txt)

				if code is None and last_row is None:
					# that means this is not a valid row
					# invalid rows are at the top of the table
					return None
			if index < len(col_headings) and len(txt) > 0:
				try:
					d[col_headings[index]] = str(col.text)
				except UnicodeEncodeError:
					print("Broke on text %s" % repr(txt))

		if last_row is not None and "code" not in d:
			repeating_fields = ["code", "term", "name"]

			if "section" in d:
				for field in repeating_fields:
					if field in last_row:
						d[field] = last_row[field]
			else:
				TimetableParser._update_last_row(d, last_row)
				return None

		return d

	@staticmethod
	def _update_last_row(this_row, last_row):
		'''Update the previous row with information from this row.'''

		fields = ["time", "location", "instructor"]

		for field in fields:
			if field in this_row:
				if field not in last_row:
					last_row[field] = this_row[field]
				elif field in last_row and last_row[field] != this_row[field]:
					last_row[field] += ", " + this_row[field]


class DBHelp:
	'''Helps out with some insertion logistics.'''

	def __init__(self, db_path: str):
		'''Create the table, connection, and other resources to interact with DB.'''

		self._db_path = db_path
		self.conn = sqlite3.connect(self._db_path) # create a connection
		self.cursor = self.conn.cursor()

		# create table just in case
		self._query("""CREATE TABLE IF NOT EXISTS timetable
			(code VARCHAR, term CHAR(1), name VARCHAR, section VARCHAR, waitlist VARCHAR, time VARCHAR, location VARCHAR, instructor VARCHAR,
			EnrollmentCode VARCHAR, EnrollmentControlLink VARCHAR,
			PRIMARY KEY (code))""")
		self.conn.commit() # commit so can insert later

	def _insert(self, d):
		'''Insert given dictionary as a row into the table.'''

		if "code" in d:
			code = d.pop("code")

			# add the course code first, as primary key
			self._query("INSERT OR IGNORE INTO timetable (code) VALUES (?)", (code, ))

			# prepare update query
			keys = list(d.keys()) # do this because d is unordered
			placeholder = ", ".join(["%s=?" % k for k in keys]) # placeholder for update values

			if len(placeholder.strip()) > 0:
				q = "UPDATE timetable SET %s WHERE code=?" % (placeholder)

				# execute the update query
				t = tuple([d[k] for k in keys]) + (code, )

				# re-add code to the dictionary
				d["code"] = code

				return self._query(q, t) # success/failure status
			else:
				return 0 # failure
		else:
			return 0 # failure

	def close(self):
		'''Close all the resources.'''

		self.conn.commit()
		self.cursor.close()

	def _query(self, q, arg_tuple=None):
		'''Execute the query.'''

		if arg_tuple is None:
			self.cursor.execute(q)
		else:
			try:
				self.cursor.execute(q, arg_tuple)
			except sqlite3.OperationalError as e:
				print("Problem with query %s" % q)
				print("Modifier is %s" % str(arg_tuple))
				print() #newline
				print("Stack trace: ")
				traceback.print_stack()
				print() # newline
				print("Error:")
				print(e)

				return 0 # failure

		return 1 # success

def get_links_from_main_page(main_page_name: str) -> dict:
	'''Given the main timetable page, extract names and locations for links to subpages.'''

	main_pg = open(main_page_name, "r")
	soup = BeautifulSoup(main_pg.read())

	d = {}

	list_elems = soup.find("div", attrs={"id": "content"}).findAll("li")

	for list_elem in list_elems:
		link = list_elem.find("a")

		# find the name and url of each element
		url = str(link["href"])
		name = str(link.text).replace("/", "").replace("\n", " ")

		m = re.search(r"^(.*?)\s*?\[.*?$", name)

		if m:
			proper_name = m.group(1).strip()

			d[proper_name] = url

			# create a file for each entry
			page = urllib.request.urlopen(url)
			newpg = open("%s/%s.html" % (PAGES_DIR, proper_name), "w")
			newpg.write(page.read())
			newpg.close()

			print("[TRACE] Saved page for %s" % proper_name)
		else:
			print("[ERROR] Could not match proper name for %s" % repr(name))

	# save the inventory of links
	inv = open(DATA_FILE, "wb")
	pickler.dump(d, inv)
	inv.close() # close the main inventory file
	print("[TRACE] Inventoried all links")

	main_pg.close()

	return d

def write_to_db(l: list, db) -> int:
	'''Given a list of rows to write to the database, write them.'''

	num_inserts = 0

	for row_dict in l:
		if "code" in row_dict:
			num_inserts += db._insert(row_dict)

	return num_inserts


def read_write_pg(html_file_path: str, db_path: str) -> None:
	l = TimetableParser.parse(html_file_path)

	db = DBHelp(db_path)
	num_lines = write_to_db(l, db)
	logger.info("[TRACE] Parsed file %s. Wrote %d rows to DB", html_file_path, num_lines)
	db.close()


def read_write_all_links(db_path: str):
	inv = open(DATA_FILE, "rb")
	link_dict = pickler.load(inv)

	try:
		os.makedirs(PAGES_DIR)
	except FileExistsError:
		pass

	for name, url in link_dict.items():
		if name[0] == "A":
			continue
		logger.info("Processing courses for %s; link= %s", name, url)
		html_file_path = "%s/%s.html" % (PAGES_DIR, name)
		if not os.path.exists(html_file_path):
			# download the page
			r = requests.get(url)
			assert r.ok
			contents = r.text
			logger.info("Downloaded and saved page contents for course %s", name)
			with open(path, "w") as fp:
				fp.write(contents)
		read_write_pg(html_file_path, db_path)
	inv.close()


def get_offering_files(dir: str) -> List[str]:
	l = []
	for fname in os.listdir(dir):
		if fname.endswith(".htm") or fname.endswith(".html"):
			l.append(os.path.join(dir, fname))
	return l


def print_or_write(offerings: List[dict], db_path: str, source_file: str, output: str = "stdout"):
	if output == "database":
		db = DBHelp(db_path)
		num_lines = write_to_db(offerings, db)
		logger.info("[TRACE] Parsed file %s. Wrote %d rows to DB", source_file, num_lines)
		db.close()
	else:
		for offering in offerings:
			pprint(offering)


if __name__ == "__main__":
	parser = ArgumentParser()
	parser.add_argument("-f", "--file",
		help="Parse the given timetable file")
	parser.add_argument("-d", "--dir",
		help="Parse all of the timetable files in the given directory")
	parser.add_argument("--database", default=DB_PATH,
		help="Path to SQLite database")
	parser.add_argument("-o", "--output", choices=["stdout", "database"],
		help="By default output everything to database")
	parser.add_argument("-v", "--verbose", action="store_true",
		help="Enable verbose logging")
	args = parser.parse_args()

	log_level = (logging.INFO if args.verbose else logging.WARNING)
	logging.basicConfig(level=log_level)
	coloredlogs.install(log_level)
	logger.setLevel(log_level)

	if args.file:
		offerings = TimetableParser.parse(args.file)
		print_or_write(offerings, args.database, output=args.output, source_file=args.file)
	elif args.dir:
		blacklist = frozenset([
			# NOTE: currently cannot parse this file
			"data/archive-capture-2012-2013/timetable-files/Arts & Science 2012-2013 Fall_Winter Session Timetable for_ Anatomy [First Year Seminars].htm"
		])
		for path in get_offering_files(args.dir):
			if path in blacklist:
				logging.debug("Skipping blacklisted file: %s", path)
				continue
			offerings = TimetableParser.parse(path)
			print_or_write(offerings, args.database, output=args.output, source_file=path)
	else:
		print("nothing to do")
