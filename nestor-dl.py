#
# nestor-dl v0.1
#
# As you can probably tell, there's lots of refractoring to be done here.
# THIS IS AN ALPHA RELEASE!!!
#
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import os
import webbrowser
import inquirer

# Import constants used across project
from constants import BASE_URL, OUTPUT_DIR, BLACKBOARD_COLLAB_TOOL_ID

# Import module for downloading blackboard lectures
from blackboard import download_blackboard_lectures


# for converting lecture filenames to safe names

# parsing response url

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

# TODO: move html generation to another function!!


def save_css():
    theme_css = session.get(f"{BASE_URL}/branding/themes/StudentPortalv3800.200609/theme.css").content
    with open(OUTPUT_DIR + "/theme.css", "wb") as f:
        f.write(theme_css)

    shared_css = session.get(f"{BASE_URL}/common/shared.css").content
    with open(OUTPUT_DIR + "/shared.css", "wb") as f:
        f.write(shared_css)


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
    request = session.get(
        BASE_URL + "/webapps/RuG-MyCourses-bb_bb60/do/coursesJson")
    for resp in request.history:
        print("[DEBUG history: ]" + resp.url)

    courses = request.json()
    available_courses = []
    for course in courses["enrollmentList"]:
        if course['available']:
            available_courses.append(course)
    return available_courses


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
                # FIXME: FLAWED BROKEN UGLY IMPLEMENTATION. CURRENTLY OPENS THE '/lectures.html' FOLDER!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                os.makedirs(OUTPUT_DIR + "/" +
                            course["courseCode"] + "/lectures.html")
            # download lecture videos as requested by user
            download_blackboard_lectures(session,
                                         course, OUTPUT_DIR + "/" + course["courseCode"] + "/lectures.html")
            # TODO: download p2go lectures here!

        content_areas = []
        all_files = []

        coursemenu = soup.find('ul', {'class': 'courseMenu'})
        if coursemenu:
            for file_link in coursemenu.findAll('a'):
                if "listContent.jsp" in file_link["href"]:
                    content_areas.append({"title": file_link.get_text(), "id": file_link["href"].split(
                        "content_id=")[1].split('&')[0]})

                # TODO: REMOVEEE!!!!! DEBUG!!!! check for blackboard link and show if found.
                if save_lectures and "launchLink.jsp" in file_link["href"] and "tool_id=" + BLACKBOARD_COLLAB_TOOL_ID in \
                        file_link["href"]:
                    pass
                    # print("!blackboard collaborate link: ", file_link["href"])

        content_areas_in_menu = content_areas.copy()

        # add lecture page to menu
        if save_lectures is True:
            # FLAWED BROKEN UGLY TEMP DEV IMPLEMENTATION. CURRENTLY OPENS THE './lectures.html' FOLDER!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            # TODO: WIP generate actual lectures.html page for displaying lectures, instead of it being a folder
            # FIXME: generate only if lectures actually there for course
            content_areas_in_menu.append(
                {"title": "Lectures", "id": "./lectures"})

        # go through all found content areas one by one
        for content_area in content_areas:
            print("[Content Area] " + content_area["title"])
            response = session.get(
                BASE_URL + "/webapps/blackboard/content/listContent.jsp?course_id=" + course[
                    "courseId"] + "&content_id=" + content_area["id"])
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
                            file_path = f"{OUTPUT_DIR}/{course['courseCode']}/attachments/{attachment.a['href'].split('/')[-1]}_{name}"
                            file_link = f"./attachments/{attachment.a['href'].split('/')[-1]}_{name}"

                            # Add link for file to files, used to generate the links in the html output
                            files.append({'name': name, 'link': file_link})
                            all_files.append({'name': name, 'link': file_link})

                            if os.path.exists(file_path):
                                # File already exists
                                print(f"[Attachment] '{name}' skipping, already downloaded")
                            else:
                                print("[Attachment] " + name)
                                # TODO: stream maybe?
                                # download to memory & save file
                                response = session.get(BASE_URL + attachment.a["href"])

                                with open(file_path, "wb") as f:
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
                "<h3><span style=\"color: #000000;\">Attachments</span></h3>",
                "<div class=\"details\">" + content_item_attachments_template(all_files) + "</div>")

        with open(OUTPUT_DIR + "/" + course['courseCode'] + "/index.html", "w") as f:
            f.write(content_area_template(
                course['courseTitle'], course, content_areas_in_menu, items, 1))

    with open(OUTPUT_DIR + "/index.html", "w") as f:
        f.write(content_area_template("nestor-dl dump homepage",
                                      {'courseTitle': 'NESTOR-DL'}, homepage_links, "", 0))


def refresh_nestor_cookie(r: requests.Response, *args, **kwargs):
    """
    Requests session hook that asks the user for a new auth cookie, if needed. Will then resend the current request.
    Triggered by a 401 status code or by being redirected to `/webapps/login/`
    """
    if r.status_code == 401 or urlparse(r.headers.get('Location')).path == '/webapps/login/':
        session_cookie = inquirer.prompt([inquirer.Text(
            'session_cookie', message="Nestor cookie expired/invalid, enter a new cookie (s_session_id)"), ])[
            'session_cookie']

        request = r.request

        # Force-clear currently set cookies, as prepare_cookies only works if this header is not set (see:
        # https://requests.readthedocs.io/en/latest/api/#requests.PreparedRequest.prepare_cookies)
        if 'Cookie' in request.headers:
            del request.headers['Cookie']

        # Set/Overwrite auth cookie for both the session and the current request (in that order!)
        session.cookies.set('s_session_id', session_cookie)
        request.prepare_cookies(session.cookies.get_dict())

        return session.send(request)


def main():
    global session, OUTPUT_DIR, save_lectures
    session = requests.Session()

    # refresh auth automatically
    session.hooks['response'].append(refresh_nestor_cookie)

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
    # ask for saving lecture videos
    save_lectures = inquirer.confirm("Save lecture videos?", default=False)
    for course in courses:
        if course['courseTitle'] + " [" + course['courseCode'] + "]" in answers['courses']:
            selected_courses.append(course)
    save_css()
    download_courses(selected_courses)
    webbrowser.open('file://' + os.path.realpath(OUTPUT_DIR + "/index.html"))


if __name__ == "__main__":
    main()
