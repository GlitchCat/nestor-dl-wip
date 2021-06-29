#
# nestor-dl v0.1
#
# As you can probably tell, there's lots of refractoring to be done here.
# THIS IS AN ALPHA RELEASE!!!
#

import requests
from bs4 import BeautifulSoup
import os
import webbrowser
import inquirer
from pprint import pprint

BASE_URL = "https://nestor.rug.nl"
OUTPUT_DIR = './nestor-dl-out'


def save_css():
    response = session.get(
        BASE_URL + "/branding/themes/StudentPortalv3800.200609/theme.css")
    with open(OUTPUT_DIR + "/theme.css", "wb") as f:
        f.write(response.content)
    response = session.get(
        BASE_URL + "/common/shared.css")
    with open(OUTPUT_DIR + "/shared.css", "wb") as f:
        f.write(response.content)


def content_item_attachments_template(files):
    with open('./html/content_item_attachments.html', 'r') as file:
        template = file.read().replace('\n', '')
        links_html = ""
        for file in files:
            links_html += content_item_attachment_template(file)
        template = template.replace('[ITEMS]', links_html)
        return template


def content_item_attachment_template(file):
    name = file['name']
    link = file['link']

    with open('./html/content_item_attachment.html', 'r') as file:
        template = file.read().replace('\n', '')
        template = template.replace('[LINK]', link)
        template = template.replace('[NAME]', name)
        return template


def content_area_template(title, course, links, items, dir_level):
    with open('./html/content_area.html', 'r') as file:
        template = file.read().replace('\n', '')
        template = template.replace('[TITLE]', title)
        template = template.replace('[COURSE]', course['courseTitle'])
        links_html = ""
        for link in links:
            links_html += content_area_link_template(link)
        template = template.replace('[LINKS]', links_html)
        template = template.replace('[ITEMS]', items)
        css_theme = "theme.css"
        css_shared = "shared.css"
        overview_btn = ""
        if dir_level > 0:
            css_theme = "../" + css_theme
            css_shared = "../" + css_shared
            overview_btn = "<a href=\"../index.html\"><li class=\"root coursePath\">Course Overview</li></a>"
        template = template.replace('[CSS_THEME]', css_theme)
        template = template.replace('[CSS_SHARED]', css_shared)
        template = template.replace('[OVERVIEW_BTN]', overview_btn)
        return template


def content_area_link_template(content_area):
    with open('./html/content_area_link.html', 'r') as file:
        template = file.read().replace('\n', '')
        template = template.replace('[LINK]', content_area['id'] + ".html")
        template = template.replace('[TEXT]', content_area['title'])
        return template


def content_item_template(title, details):
    with open('./html/content_item.html', 'r') as file:
        return file.read().replace('\n', '').replace('[TITLE]', title).replace('[DETAILS]', details)


def get_courses():
    courses = session.get(
        BASE_URL + "/webapps/RuG-MyCourses-bb_bb60/do/coursesJson").json()
    available_courses = []
    for course in courses["enrollmentList"]:
        if course['available']:
            available_courses.append(course)
    return available_courses


def download_courses(courses):
    homepage_links = []
    for course in courses:
        print("[Course] " + course['courseTitle'])

        homepage_links.append(
            {'id': course['courseCode'] + "/index", 'title': course['courseTitle']})

        response = session.get(
            BASE_URL + "/webapps/blackboard/execute/announcement?course_id=" + course["courseId"])
        soup = BeautifulSoup(response.text, 'html.parser')

        if not os.path.exists(OUTPUT_DIR + "/" + course["courseCode"]):
            os.makedirs(OUTPUT_DIR + "/" + course["courseCode"])

        if not os.path.exists(OUTPUT_DIR + "/" + course["courseCode"] + "/attachments"):
            os.makedirs(OUTPUT_DIR + "/" +
                        course["courseCode"] + "/attachments")

        content_areas = []
        all_files = []

        coursemenu = soup.find('ul', {'class': 'courseMenu'})
        if coursemenu:
            for link in coursemenu.findAll('a'):
                if "listContent.jsp" in link["href"]:
                    content_areas.append({"title": link.get_text(), "id": link["href"].split(
                        "content_id=")[1].split('&')[0]})

        content_areas_in_menu = content_areas.copy()

        for content_area in content_areas:
            print("[Content Area] " + content_area["title"])
            response = session.get(
                BASE_URL + "/webapps/blackboard/content/listContent.jsp?course_id="+course["courseId"]+"&content_id="+content_area["id"])
            soup = BeautifulSoup(response.text, 'html.parser')

            content_items_html = ""
            content_items = soup.find('ul', {'id': 'content_listContainer'})

            if content_items:
                for content_item in content_items.findAll('li', {'class': 'liItem'}):
                    title = content_item.find('h3')
                    details = content_item.find('div', {'class': 'details'})

                    if content_item.img["alt"] == "Content Folder":
                        content_areas.append({"title": content_item.a.get_text(
                        ), "id": content_item.a["href"].split("content_id=")[1].split('&')[0]})
                        title.a["href"] = "./" + content_item.a["href"].split(
                            "content_id=")[1].split('&')[0] + ".html"

                    # extract attachments
                    attachments = details.find('ul', {'class': 'attachments'})
                    if attachments:
                        files = []

                        for attachment in attachments.findAll('li', {'class': ''}):
                            name = attachment.a.get_text()
                            print("[Attachment] " + name)
                            link = "./attachments/" + \
                                attachment.a["href"].split(
                                    '/')[-1] + "_" + name
                            files.append({'name': name, 'link': link})
                            all_files.append({'name': name, 'link': link})

                            # save file
                            response = session.get(
                                BASE_URL + attachment.a["href"])
                            with open(OUTPUT_DIR + "/" + course["courseCode"] + "/attachments/" + attachment.a["href"].split(
                                    '/')[-1] + "_" + name, "wb") as f:
                                f.write(response.content)

                        new_attachments = BeautifulSoup(
                            content_item_attachments_template(files), 'html.parser')
                        details.find(
                            'div', {'class': 'contextItemDetailsHeaders'}).replace_with(new_attachments)

                    content_items_html += content_item_template(
                        title.__str__(), details.__str__())

            with open(OUTPUT_DIR + "/" + course['courseCode'] + "/" + content_area['id'] + ".html", "w") as f:
                f.write(content_area_template(
                    content_area['title'], course, content_areas_in_menu, content_items_html, 1))

        items = ""
        if all_files:
            items = content_item_template(
                "<h3><span style=\"color: #000000;\">Attachments</span></h3>", "<div class=\"details\">" + content_item_attachments_template(all_files) + "</div>")

        with open(OUTPUT_DIR + "/" + course['courseCode'] + "/index.html", "w") as f:
            f.write(content_area_template(
                course['courseTitle'], course, content_areas_in_menu, items, 1))

    with open(OUTPUT_DIR + "/index.html", "w") as f:
        f.write(content_area_template("nestor-dl dump homepage",
                {'courseTitle': 'NESTOR-DL'}, homepage_links, "", 0))


session = requests.Session()
session.cookies["s_session_id"] = inquirer.prompt([inquirer.Text(
    'session_cookie', message="Enter your nestor session cookie (s_session_id)"), ])['session_cookie']

OUTPUT_DIR = inquirer.prompt([inquirer.Text(
    'dir', message="Enter output directory", default=OUTPUT_DIR), ])['dir']
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
courses = get_courses()
selected_courses = []
course_names = []
for course in courses:
    course_names.append(course['courseTitle'] +
                        " [" + course['courseCode'] + "]")
questions = [
    inquirer.Checkbox('courses',
                      message="Which courses would you like to save?",
                      choices=course_names),


]
answers = inquirer.prompt(questions)
for course in courses:
    if course['courseTitle'] + " [" + course['courseCode'] + "]" in answers['courses']:
        selected_courses.append(course)

save_css()
download_courses(selected_courses)

webbrowser.open('file://' + os.path.realpath(OUTPUT_DIR + "/index.html"))
