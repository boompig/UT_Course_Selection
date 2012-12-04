#############################################
#	PARSING U OF T COURSE OUTLINE WEB PAGE	#
#	WRITTEN BY DANIEL KATS					#
#############################################

#####################
# 	MODULES			#
#####################

import re # for soup matching
from BeautifulSoup import BeautifulSoup
import sqlite3 
import sys # for exiting the program
import traceback # for tracing SQL exceptions
import urllib # for downloading web pages
import cPickle as pickler # for saving inventory...

#####################
# 	KEY ITEMS		#
#####################

course_code_pattern = r"\w\w\w\d\d\d\w\d"
pages_dir = "pages"

#####################
# 	CODE			#
#####################
	
def get_functional_soup(all_soup, name):
	'''Given the entire web page soup and the name of the department, get a partial soup.
	This will exclude the program description and professors, only including courses.
	Also exclude standard university footer.
	Remove junk characters from the soup.'''
	
	top_sep = all_soup.find(text=re.compile("%s Courses" % name))
	bottom_sep_node = all_soup.find("div", id="footer")
	
	if top_sep and bottom_sep_node:
		top_sep_node = top_sep.parent
		
		all_soup_str = html_str_replace(str(all_soup))
		# print repr(all_soup_str)
		
		top_gone = all_soup_str.split(str(top_sep_node))[1] # get the second (bottom) portion
		bottom_gone = top_gone.split(str(bottom_sep_node))[0] # get the first (top) portion
		return BeautifulSoup(bottom_gone)
	else:
		if top_sep is None:
			print "[WARNING] Could not find %s Courses as heading" % name
		elif bottom_sep_node is None:
			print "[WARNING] Could not find footer"
	
		# could not separate
		return None
	
def get_name(soup):
	'''Given the HTML soup for a page, extract the department name and return it.
	If cannot extract it, return None.
	It is assumed to be the first h1 element on the page.'''
	
	heading_list = soup('h1')
	
	if len(heading_list) >= 1:
		return str(heading_list[0].text)
	else:
		print "[WARNING] Could not find heading in soup"
		# in the wrong format
		return None
	
def get_course_list(soup):
	'''Given a soup of course codes, course descriptions and such, return a list of sections that represent the courses.'''
	
	pattern = r"<a name=.?%s.?>*?</a>" % course_code_pattern
	l = re.split(pattern, str(soup))
	
	if len(l) == 1:
		print "[WARNING] soup was not split"
		print "Dumping soup:"
		print soup
	
	return l
	
def html_str_replace(html_string):
	return html_string.replace("\u2018", "'").replace("\u2019", "'").replace("&nbsp;", " ")
	
def get_course_info(html_string):
	'''Course info is in the form of a dictionary.'''
	
	d = {}
	
	other_keywords = ["Prerequisite", "Exclusion", "Recommended Preparation", "Distribution Requirement Status", "Breadth Requirement"]
	soup = BeautifulSoup(html_string)
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
			print "Broke on string %s" % repr(p_elems[0].text)
	
	for k in other_keywords:
		other_match = re.search("(%s:\s*)(.*?)<br />" % k, html_string)
		
		if other_match and len(other_match.groups()) == 2:
			m = BeautifulSoup(other_match.group(2)).text
		
			try:
				d[k.replace(" ", "")] = str(m)
			except UnicodeEncodeError:
				# not really sure what to do here
				# can't print the error
				# print "Could not parse %s" % m 
				pass
			
	return d
	
def make_table():
	'''Create the table if it doesn't exist, return a tuple with the cursor and connection object.
	Primary key on course code.
	'''
	
	conn = sqlite3.connect("courses.db")
	c = conn.cursor()
	c.execute("CREATE TABLE IF NOT EXISTS courses (code VARCHAR, name VARCHAR, desc TEXT, Prerequisite VARCHAR, Corequisite VARCHAR, RecommendedPreparation VARCHAR, DistributionRequirementStatus VARCHAR, BreadthRequirement VARCHAR, Exclusion VARCHAR, lectimes VARCHAR, PRIMARY KEY (code))")
	conn.commit()
	
	return (c, conn)
	
def confirm_add_to_table(d, c, conn):
	'''Confirm before adding the extracted info to the table.'''
	
	input = raw_input("Put in row %s? " % d)
	if input == "q":
		sys.exit(0)
	elif input == "y":
		add_info_to_table(d, c, conn)
	elif input == "n":
		return
	else:
		# go again
		confirm_add_to_table(d, c, conn)
	
def add_info_to_table(d, c, conn):
	'''Add information in d to the table.
	Tries to avoid duplicate inserts.
	d is a dict mapping table columns to values.
	c is a cursor object.
	conn is a connection object.'''
	
	if d.has_key("code"):
		code = d.pop("code")
		
		# add the course code first, as primary key
		c.execute("INSERT OR IGNORE INTO courses (code) VALUES (?)", (code, ))
		
		# prepare update query
		keys = d.keys() # do this because d is unordered
		placeholder = ", ".join(["%s=?" % k for k in keys]) # placeholder for update values
		q = "UPDATE courses SET %s WHERE code=?" % (placeholder)
		
		# execute the update query
		t = tuple([d[k] for k in keys]) + (code, )
		
		try:
			c.execute(q, t)
		except sqlite3.OperationalError as e:
			print "Problem with query %s" % q
			print "Modifier is %s" % str(t)
			print "Stack trace: "
			traceback.print_stack()
			print "Error:"
			print e
			
			return 0 # failure
		
		# re-add code to the dictionary
		d["code"] = code
		
		return 1 # success
	else:
		return 0 # failure

def add_course_page_info_to_table(page_file):
	'''Get all course info out of a single page.
	Return number of inserts made.'''

	# create/open the SQL DB
	c, conn = make_table()
	
	# get the functional soup
	f = open(page_file, "r")
	soup = BeautifulSoup(f.read())
	name = get_name(soup)
	fsoup = get_functional_soup(soup, name)
	
	num_inserts = 0 # keep track of the number of inserts made
	
	# a substep...
	l = get_course_list(fsoup)
	
	if len(l) == 0:
		print "[WARNING] No courses found on page"
	
	for item in l:
		# this is the info extracted for one course
		d = get_course_info(item)
	
		if d.has_key("code") and d.has_key("name"):
			# add gathered information into the table, if enough info gathered
			num_inserts += add_info_to_table(d, c, conn)
		else:
			print "[WARNING] Could not find a name or code for a course"
	
	conn.commit() # push all changes
	c.close() # get rid of the cursor
	f.close() # close the file
	
	return num_inserts
	
def add_all_course_pages_to_db(inventory_dict):
	for name in inventory_dict:
		fname = "%s/%s.htm" % (pages_dir, name)
		print "Processing courses for [%s] " % (name)
		n = add_course_page_info_to_table(fname)
		print "Made %d inserts" % n
	
def get_links_from_main_page():
	'''Return a dictionary of all the links found on the main page.
	Keys are department names, values are links.'''
	
	page_file = "main.htm"
	f = open(page_file, "r")
	page_soup = BeautifulSoup(f.read())
	
	d = {}
	base = "http://www.artsandscience.utoronto.ca/ofr/calendar/"
	main_list = page_soup.find("div", attrs={"class": "items"}).find("ul", attrs={"class": "simple"})
	link_elems = main_list.findAll("a")
	
	for link in link_elems:
		# find the name and url of each element
		url = str(link["href"])
		name = str(link.text).replace("/", "")
		d[name] = url
		
		# create a file for each entry
		page = urllib.urlopen(url)
		newpg = open("%s/%s.html" % (pages_dir, name), "w")
		newpg.write(page.read())
		newpg.close()
		
	# save the inventory of links
	inv = open("inventory.data", "w")
	pickler.dump(d, inv)
	inv.close() # close the main inventory file
	
	f.close() # close the main HTML file
		
	return d
		
if __name__ == "__main__":
	# d = get_links_from_main_page()
	
	
	inv = open("inventory.data", "r")
	d = pickler.load(inv)
	inv.close() # close the main inventory file
	
	add_all_course_pages_to_db(d)
	
	
