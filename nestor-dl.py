#
# nestor-dl v0.1
#
# As you can probably tell, there's lots of refractoring to be done here.
# THIS IS AN ALPHA RELEASE!!!
#

import json
import requests
from bs4 import BeautifulSoup
import os
import webbrowser
import inquirer
from pprint import pprint

from requests.api import post
import datetime
from tqdm import tqdm

# for converting lecture filenames to safe names
import unicodedata
import re

# debug logging
# import logging

# # These two lines enable debugging at httplib level (requests->urllib3->http.client)
# # You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
# # The only thing missing will be the response.body which is not logged.
# import http.client as http_client
# http_client.HTTPConnection.debuglevel = 1

# # You must initialize logging, otherwise you'll not see debug output.
# logging.basicConfig()
# logging.getLogger().setLevel(logging.DEBUG)
# requests_log = logging.getLogger("requests.packages.urllib3")
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True

BASE_URL = "https://nestor.rug.nl"
BBCOLLAB_BASE_URL = "https://eu-lti.bbcollab.com"
OUTPUT_DIR = './nestor-dl-out'
BLACKBOARD_COLLAB_TOOL_ID = "_4680_1"


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


# function for downloading the bbcollab lecture videos from a course
def download_bbcollab_lectures(course, folder):
    # get the token
    token = get_bbcollab_token(course)

    # debug
    # print("Token: " + token)
    # print("! Time: " + datetime.datetime.utcnow().isoformat() + "\nOther time: " + datetime.datetime.now().astimezone().replace(microsecond=0).isoformat())

    # get the list of videos

    currentDateTime = datetime.datetime.now(
    ).astimezone().replace(microsecond=0).isoformat()

    param_data = {'startTime': '2015-01-01T00:00:00+0100', 'endTime': currentDateTime,
                  'sort': 'endTime', 'order': 'desc', 'limit': 1000, 'offset': 0}

    lectures = requests.get(BBCOLLAB_BASE_URL + "/collab/api/csa/recordings",
                            headers={"Authorization": "Bearer "+token}, params=param_data).json()

    # print lecture job and download amount
    print("[Lectures] " + str(lectures["size"]) + " lectures")

    # download each video and add it to the output html
    available_courses = []
    for video in lectures["results"]:
        try:
            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! DOES NOT WORK ANYMORE, FIND OTHER METHOD TO GET DIRECT VIDEO URL!!
            url = BBCOLLAB_BASE_URL + \
                "/collab/api/csa/recordings/" + video["id"] + " /url"
            response = requests.request("GET", url, data="", headers={
                                        "Authorization": "Bearer "+token}, params={"disposition": "download"})

            # raise exceptions
            response.raise_for_status()

            # get direct video url and download it
            file_url = response.json()['url']
            download(file_url, slugify(video["name"]) + ".mp4", folder)
        except requests.exceptions.ConnectionError as e:
            # Retry?
            print('Connection Error:', e)

        except requests.exceptions.HTTPError as e:
            message = "ERROR getting video '" + video["name"] + "':"
            if e.response.status_code == 404:
                print(message, e.response.json()['errorMessage'])
            else:
                print(message, e)

# download the video from the direct file url with a nice progress bar


def download(url: str, fname: str, folder: str):
    resp = requests.get(url, stream=True)
    total = int(resp.headers.get('content-length', 0))
    with open(folder + "/" + fname, 'wb') as file, tqdm(
            desc="[Lecture video] " + fname,
            total=total,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
    ) as bar:
        for data in resp.iter_content(chunk_size=1024):
            size = file.write(data)
            bar.update(size)

# used for turning the video name into a name that is safe to store for every filesystem


def slugify(value, allow_unicode=False):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode(
            'ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


def get_bbcollab_token(course):
    # get the data needed for the POST request
    response = session.get(
        BASE_URL + "/webapps/collab-ultra/tool/collabultra/lti/launch?course_id=" +
        course["courseId"]
    )
    soup = BeautifulSoup(response.text, 'html.parser')

    # grab only the post request form as html
    post_request_form = soup.find('form', {'id': 'bltiLaunchForm'})

    # extract the form details
    form_details = get_form_details(post_request_form)

    # debug
    # print("form_details:\n")
    # print(form_details)

    post_data = {}
    for input_tag in form_details["inputs"]:
        if input_tag["type"] == "hidden":
            # if it's hidden, use the default value
            post_data[input_tag["name"]] = input_tag["value"]
        elif input_tag["type"] != "submit":
            # all others except submit, prompt the user to set it
            value = input(
                f"Enter the value of the field '{input_tag['name']}' (type: {input_tag['type']}): ")
            post_data[input_tag["name"]] = value

    # perform a POST request to get the bbcollab token for this course
    response_bbcollab_token = requests.post(
        BBCOLLAB_BASE_URL + "/lti", data=post_data)

    # debug
    # print("! request url:")
    # print(response_bbcollab_token.request.url)

    # url with token as a parameter
    url = response_bbcollab_token.request.url
    # extract parameters
    query = requests.utils.urlparse(url).query
    params = dict(x.split('=') for x in query.split('&'))
    # save token
    bbcollab_token = params['token']

    # debug
    # print("! token:")
    # print(bbcollab_token)

    return bbcollab_token


def get_form_details(form):
    """Returns the HTML details of a form,
    including action, method and list of form controls (inputs, etc)"""
    details = {}
    # get the form action (requested URL)
    action = form.attrs.get("action").lower()
    # get the form method (POST, GET, DELETE, etc)
    # if not specified, GET is the default in HTML
    method = form.attrs.get("method", "get").lower()
    # get all form inputs
    inputs = []
    for input_tag in form.find_all("input"):
        # get type of input form control
        input_type = input_tag.attrs.get("type", "text")
        # get name attribute
        input_name = input_tag.attrs.get("name")
        # get the default value of that input tag
        input_value = input_tag.attrs.get("value", "")
        # add everything to that list
        inputs.append(
            {"type": input_type, "name": input_name, "value": input_value})
    # put everything to the resulting dictionary
    details["action"] = action
    details["method"] = method
    details["inputs"] = inputs
    return details

# Download the selected courses


def download_courses(courses):
    homepage_links = []

    # go through all courses one by one
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

        # create directory to save lectures to
        if save_lectures is True:
            if not os.path.exists(OUTPUT_DIR + "/" + course["courseCode"] + "/lectures.html"):
                # FLAWED BROKEN UGLY IMPLEMENTATION. CURRENTLY OPENS THE '/lectures.html' FOLDER!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                os.makedirs(OUTPUT_DIR + "/" +
                            course["courseCode"] + "/lectures.html")
            # download lecture videos as requested by user
            download_bbcollab_lectures(
                course, OUTPUT_DIR + "/" + course["courseCode"] + "/lectures.html")

        content_areas = []
        all_files = []

        coursemenu = soup.find('ul', {'class': 'courseMenu'})
        if coursemenu:
            for link in coursemenu.findAll('a'):
                if "listContent.jsp" in link["href"]:
                    content_areas.append({"title": link.get_text(), "id": link["href"].split(
                        "content_id=")[1].split('&')[0]})
                # check for blackboard link and show if found.                                  REMOVEEE!!!!! DEBUG!!!!
                if save_lectures and "launchLink.jsp" in link["href"] and "tool_id="+BLACKBOARD_COLLAB_TOOL_ID in link["href"]:
                    print("!blackboard collaborate link: ", link["href"])

        content_areas_in_menu = content_areas.copy()

        # debug
        # print("content_areas_in_menu")
        # print(content_areas_in_menu)

        # add lecture page to menu
        if save_lectures is True:
            # FLAWED BROKEN UGLY IMPLEMENTATION. CURRENTLY OPENS THE './lectures.html' FOLDER!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            content_areas_in_menu.append(
                {"title": "Lectures", "id": "./lectures"})

        # go through all found content areas one by one
        for content_area in content_areas:
            print("[Content Area] " + content_area["title"])
            response = session.get(
                BASE_URL + "/webapps/blackboard/content/listContent.jsp?course_id=" + course["courseId"] + "&content_id=" + content_area["id"])
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

# ask for saving BBcollab lectures
save_lectures = inquirer.confirm("Save BBCollab lectures?", default=False)


for course in courses:
    if course['courseTitle'] + " [" + course['courseCode'] + "]" in answers['courses']:
        selected_courses.append(course)

save_css()
download_courses(selected_courses)

webbrowser.open('file://' + os.path.realpath(OUTPUT_DIR + "/index.html"))
