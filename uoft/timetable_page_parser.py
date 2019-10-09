#################################################
#	PARSING U OF T COURSE TIMETABLE WEB PAGE	#
#	WRITTEN BY DANIEL KATS						#
#################################################

#####################
# 	MODULES			#
#####################

import os
import pickle as pickler  # for saving inventory...
import re  # for soup matching
import sqlite3
import traceback  # for tracing SQL exceptions
import urllib.error
import urllib.parse
import urllib.request  # for downloading web pages

from bs4 import BeautifulSoup

#####################
# 	KEY ITEMS		#
#####################

course_code_pattern = r"\w\w\w\d\d\d\w\d"
pages_dir = "tables"

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



class TimetableParser(object):
	'''This object is used to extract information from the timetable webpage.'''

	@staticmethod
	def parse(page_file_path):
		'''The main method. Given a path to the web page, extract timetable info and return it as a list of dictionaries.'''

		l = [] # container for dictionaries

		page_file = open(page_file_path, "r")
		soup = BeautifulSoup(page_file.read())

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

	@staticmethod
	def _get_department_name(all_soup):
		'''Given the HTML soup for a page, extract the department name and return it.
		If cannot extract it, return None.
		It is assumed to be the first h1 element on the page.'''

		txt = all_soup.h2.font.text

		if txt:
			m = re.search(r"(.*?)\s*?(\[\w\w\w courses.*?\])", txt)

			if m:
				return m.groups(1) # first group is name, second is code prefix
			else:
				print("[ERROR] Could not match name and dept. code in %s" % txt)
				return None
		else:
			print("[ERROR] Could not extract department name tag")
			return None

	@staticmethod
	def _get_functional_soup(all_soup, name):
		'''Given the entire web page soup and the name of the department, get a partial soup.
		This will exclude the program description and professors, only including courses.
		Also exclude standard university footer.
		Remove junk characters from the soup.'''

		# remove HTML special characters
		all_soup = BeautifulSoup(html_to_str(all_soup))

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

		row_soup = BeautifulSoup(html_string)
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


class DBHelp(object):
	'''Helps out with some insertion logistics.'''

	def __init__(self):
		'''Create the table, connection, and other resources to interact with DB.'''

		self.conn = sqlite3.connect("courses.db") # create a connection
		self.cursor = self.conn.cursor()

		# create table just in case
		self._query("CREATE TABLE IF NOT EXISTS timetable (code VARCHAR, term CHAR(1), name VARCHAR, section VARCHAR, waitlist VARCHAR, time VARCHAR, location VARCHAR, instructor VARCHAR, EnrollmentCode VARCHAR, EnrollmentControlLink VARCHAR, PRIMARY KEY (code))")
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

def get_links_from_main_page(main_page_name):
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
			newpg = open("%s/%s.html" % (pages_dir, proper_name), "w")
			newpg.write(page.read())
			newpg.close()

			print("[TRACE] Saved page for %s" % proper_name)
		else:
			print("[ERROR] Could not match proper name for %s" % repr(name))

	# save the inventory of links
	inv = open("timetable_inventory.data", "w")
	pickler.dump(d, inv)
	inv.close() # close the main inventory file
	print("[TRACE] Inventoried all links")

	main_pg.close()

	return d

def write_to_db(l, db):
	'''Given a list of rows to write to the database, write them.'''

	num_inserts = 0

	for row_dict in l:
		if "code" in row_dict:
			num_inserts += db._insert(row_dict)

	return num_inserts

def read_write_pg(path):
	l = TimetableParser.parse(path)
	# print l[0]

	db = DBHelp()

	num_lines = write_to_db(l, db)
	print("[TRACE] Wrote %d rows to DB" % num_lines)

	db.close()

def read_write_all_links():
	inv = open("timetable_inventory.data", "rb")
	link_dict = pickler.load(inv)

	for name in link_dict:
		path = "%s/%s.html" % (pages_dir, name)
		print("Processing courses for [%s] " % (name))
		read_write_pg(path)

	inv.close()

if __name__ == "__main__":
	# fname = "psych"
	# path = "%s/%s.htm" % (pages_dir, fname)
	# read_write_pg(path)

	# d = get_links_from_main_page("timetable_main.htm")

	assert os.path.exists(pages_dir), "%s directory does not exist" % pages_dir
	read_write_all_links()
