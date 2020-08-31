#############################################
#	PARSING U OF T COURSE OUTLINE WEB PAGE	#
#	WRITTEN BY DANIEL KATS					#
#############################################

#####################
# 	MODULES			#
#####################

import logging
import os
import pickle as pickler  # for saving inventory...
import re  # for soup matching
import sqlite3
import sys  # for exiting the program
import traceback  # for tracing SQL exceptions
import urllib.error
import urllib.parse
import urllib.request  # for downloading web pages
from argparse import ArgumentParser
from pprint import pprint
from typing import List

import coloredlogs
from bs4 import BeautifulSoup

#####################
# 	GLOBAL VARS		#
#####################

course_code_pattern = r"\w\w\w\d\d\d\w\d"
pages_dir = "pages"
DATA_FILE = "calendar_inventory.data"
DB_PATH = "./data/archive-capture-2012-2013/courses-new.db"
# DB_PATH = "./courses.db"


#####################
# 	CODE			#
#####################


class PageParsingError(Exception):
	pass


def get_functional_soup(all_soup: BeautifulSoup, name: str) -> BeautifulSoup:
	"""Given the entire web page soup and the name of the department, get a partial soup.
	This will exclude the program description and professors, only including courses.
	Also exclude standard university footer.
	Remove junk characters from the soup."""

	top_sep = all_soup.find(text="%s Courses" % name)
	bottom_sep_node = all_soup.find("div", id="footer")

	if top_sep is None:
		raise PageParsingError("Could not find %s Courses as heading" % name)
	elif bottom_sep_node is None:
		raise PageParsingError("Could not find footer")
	else:
		top_sep_node = top_sep.parent

		all_soup_str = html_str_replace(str(all_soup))
		# print repr(all_soup_str)

		top_gone = all_soup_str.split(str(top_sep_node))[1] # get the second (bottom) portion
		bottom_gone = top_gone.split(str(bottom_sep_node))[0] # get the first (top) portion
		return BeautifulSoup(bottom_gone, "html.parser")


def get_name(soup: BeautifulSoup) -> str:
	"""Given the HTML soup for a page, extract the department name and return it.
	If cannot extract it, return None.
	It is assumed to be the first h1 element on the page."""

	heading_list = soup('h1')

	if len(heading_list) >= 1:
		return str(heading_list[0].text)
	else:
		raise PageParsingError("[WARNING] Could not find heading in soup")


def get_course_list(soup: BeautifulSoup) -> List[str]:
	"""Given a soup of course codes, course descriptions and such, return a list of sections that represent the courses."""

	assert soup is not None
	pattern = r"<a name=.?%s.?>*?</a>" % course_code_pattern
	l = re.split(pattern, str(soup))
	if len(l) == 1:
		raise PageParsingError("Failed to find course anchors on page")
	return l[1:]


def html_str_replace(html_string: str) -> str:
	return html_string.replace("\\u2018", "'").replace("\\u2019", "'").replace("&nbsp;", " ")


def get_course_info(html_string: str) -> dict:
	"""Course info is in the form of a dictionary."""

	d = {}

	other_keywords = ["Prerequisite", "Exclusion", "Recommended Preparation", "Distribution Requirement Status", "Breadth Requirement"]
	soup = BeautifulSoup(html_string, "html.parser")
	strong_elem = soup.find("span", attrs={"class" : "strong"})
	p_elems = soup.findAll('p')

	if strong_elem:
		m = re.search("(%s)(\s*)(.*?)(\[(\d+\w/?)+\])?$" % course_code_pattern, str(strong_elem.text))

		# first group catches course code
		# third group catches name
		# fourth group catches number of lectures/labs

		if m:
			d["code"] = m.group(1)
			d["name"] = m.group(3)

			# re.groups() does not include group 0 (whole match)
			if len(m.groups()) >= 4 and m.group(4) is not None:
				d["lectimes"] = m.group(4).strip("[]")
	else:
		# print "[WARNING] Could not find strong span element with course name"
		# print "Dumping soup"
		# print soup
		pass

	if len(p_elems) > 0:
		try:
			d["desc"] = str(p_elems[0].text)
		except Exception:
			print("Broke on string %s" % repr(p_elems[0].text))

	for k in other_keywords:
		other_match = re.search("(%s:\s*)(.*?)<br />" % k, html_string)

		if other_match and len(other_match.groups()) == 2:
			m = BeautifulSoup(other_match.group(2), "html.parser").text

			try:
				d[k.replace(" ", "")] = str(m)
			except UnicodeEncodeError:
				# not really sure what to do here
				# can't print the error
				# print "Could not parse %s" % m
				pass

	return d


def make_table(db_path: str) -> tuple:
	"""Create the table if it doesn't exist, return a tuple with the cursor and connection object.
	Primary key on course code.
	"""

	conn = sqlite3.connect(db_path)
	c = conn.cursor()
	c.execute("""CREATE TABLE IF NOT EXISTS courses
		(code VARCHAR, name VARCHAR, desc TEXT, Prerequisite VARCHAR, Corequisite VARCHAR, RecommendedPreparation VARCHAR,
		DistributionRequirementStatus VARCHAR, BreadthRequirement VARCHAR, Exclusion VARCHAR, lectimes VARCHAR,
		PRIMARY KEY (code))""")
	conn.commit()
	return (c, conn)


def confirm_add_to_table(d: dict, c, conn) -> None:
	"""Confirm before adding the extracted info to the table."""

	user_input = input("Put in row %s? " % d)
	if user_input == "q":
		sys.exit(0)
	elif user_input == "y":
		add_info_to_table(d, c, conn)
	elif user_input == "n":
		return
	else:
		# go again
		confirm_add_to_table(d, c, conn)


def add_info_to_table(d: dict, c, conn) -> int:
	"""Add information in d to the table.
	Tries to avoid duplicate inserts.
	d is a dict mapping table columns to values.
	c is a cursor object.
	conn is a connection object."""

	if "code" in d:
		code = d.pop("code")

		# add the course code first, as primary key
		c.execute("INSERT OR IGNORE INTO courses (code) VALUES (?)", (code, ))

		# prepare update query
		keys = list(d.keys()) # do this because d is unordered
		placeholder = ", ".join(["%s=?" % k for k in keys]) # placeholder for update values
		q = "UPDATE courses SET %s WHERE code=?" % (placeholder)

		# execute the update query
		t = tuple([d[k] for k in keys]) + (code, )

		try:
			c.execute(q, t)
		except sqlite3.OperationalError as e:
			print("Problem with query %s" % q)
			print("Modifier is %s" % str(t))
			print("Stack trace: ")
			traceback.print_stack()
			print("Error:")
			print(e)

			return 0 # failure

		# re-add code to the dictionary
		d["code"] = code

		return 1 # success
	else:
		return 0 # failure


def parse_course_page(page_file: str) -> List[dict]:
	assert page_file is not None
	soup = None
	name = None
	with open(page_file) as fp:
		soup = BeautifulSoup(fp.read(), "html.parser")
		name = get_name(soup)
		assert name is not None
	fsoup = get_functional_soup(soup, name)
	course_list = get_course_list(fsoup)
	if len(course_list) == 0:
		print("[WARNING] No courses found on page")
	courses = [get_course_info(item) for item in course_list]
	return courses


def insert_courses_into_db(courses: List[dict], source_file: str, db_path: str) -> int:
	# create/open the SQL DB
	c, conn = make_table(db_path)

	num_inserts = 0 # keep track of the number of inserts made

	for d in courses:
		if "code" in d and "name" in d:
			# add gathered information into the table, if enough info gathered
			num_inserts += add_info_to_table(d, c, conn)
		else:
			logging.warning("Found a course without a name or course code. File: %s", source_file)
			logging.warning("Course was %s", str(d))

	conn.commit() # push all changes
	c.close() # get rid of the cursor
	return num_inserts


def add_course_page_info_to_table(page_file: str, db_path: str) -> int:
	"""Get all course info out of a single page.
	Return number of inserts made."""

	assert page_file is not None
	courses = parse_course_page(page_file)
	return insert_courses_into_db(courses, page_file, db_path)


def add_all_course_pages_to_db(inventory_dict: dict, db_path: str):
	for name in inventory_dict:
		fname = "%s/%s.htm" % (pages_dir, name)
		print("Processing courses for [%s] " % (name))
		n = add_course_page_info_to_table(fname, db_path)
		print("Made %d inserts" % n)


def get_links_from_main_page() -> dict:
	"""Return a dictionary of all the links found on the main page.
	Keys are department names, values are links."""

	page_file = "main.htm"
	# base = "http://www.artsandscience.utoronto.ca/ofr/calendar/"
	with open(page_file, "r") as f:
		page_soup = BeautifulSoup(f.read())

		d = {}
		main_list = page_soup.find("div", attrs={"class": "items"}).find("ul", attrs={"class": "simple"})
		link_elems = main_list.findAll("a")

		for link in link_elems:
			# find the name and url of each element
			url = str(link["href"])
			name = str(link.text).replace("/", "")
			d[name] = url

			# create a file for each entry
			page = urllib.request.urlopen(url)
			newpg = open("%s/%s.html" % (pages_dir, name), "w")
			newpg.write(page.read())
			newpg.close()

		# save the inventory of links
		inv = open(DATA_FILE, "wb")
		pickler.dump(d, inv)
		inv.close() # close the main inventory file

	return d



def get_course_files(dir: str) -> List[str]:
	l = []
	for fname in os.listdir(dir):
		if fname.endswith(".html") or fname.endswith(".htm"):
			l.append(os.path.join(dir, fname))
	return l


def print_or_write(courses: List[dict], db_path: str, source_file: str, output: str = "stdout"):
	if output == "database":
		num_inserts = insert_courses_into_db(courses, source_file, db_path)
		print("Parsed file %s. Wrote %d new courses to database" % (source_file, num_inserts))
	else:
		for course in courses:
			pprint(course)


if __name__ == "__main__":
	parser = ArgumentParser()
	parser.add_argument("--database", default=DB_PATH,
		help="path to SQLite file to use")
	parser.add_argument("-f", "--file",
		help="File to parse")
	parser.add_argument("-d", "--dir",
		help="Parse all files in this directory")
	parser.add_argument("-o", "--output", default="stdout",
		choices=["stdout", "database"],
		help="Where to output the parsed file. Default is stdout")
	parser.add_argument("-v", "--verbose", action="store_true",
		help="Use this flag for verbose output")
	args = parser.parse_args()

	log_level = (logging.DEBUG if args.verbose else logging.WARNING)
	logging.basicConfig(level=log_level)
	coloredlogs.install(log_level)

	if args.file:
		try:
			assert args.file is not None
			courses = parse_course_page(args.file)
			print_or_write(courses, args.database, args.file, args.output)
		except PageParsingError as e:
			logging.error("Failed to parse file %s", args.file)
			logging.error(e)
			sys.exit(1)
	elif args.dir:
		blacklist = frozenset([
			# this is an aggregation of courses by a few different departments
			"data/archive-capture-2012-2013/calendar-files/2012-2013 Calendar - Life Sciences.htm",
			# no courses on this page
			"data/archive-capture-2012-2013/calendar-files/2012-2013 Calendar - 199299398399.htm",
			# this is an aggregation of courses by a few different departments
			"data/archive-capture-2012-2013/calendar-files/2012-2013 Calendar - Joint Courses.htm",
			# no courses on this page
			"data/archive-capture-2012-2013/calendar-files/2012-2013 Calendar - Writing in the Faculty of Arts & Science.htm",
			# this is an aggregation of courses by a few different departments
			"data/archive-capture-2012-2013/calendar-files/2012-2013 Calendar - Modern Languages and Literatures.htm",
			# this is an aggregation of courses by a few different departments
			"data/archive-capture-2012-2013/calendar-files/2012-2013 Calendar - Biology.htm",
		])
		for path in get_course_files(args.dir):
			if path in blacklist:
				logging.debug("Skipping blacklisted file: %s", path)
				continue
			try:
				courses = parse_course_page(path)
				print_or_write(courses, args.database, path, args.output)
			except PageParsingError as e:
				logging.error("Failed to parse file: %s", path)
				logging.error(e)
				sys.exit(1)
	else:
		print("nothing to do")

