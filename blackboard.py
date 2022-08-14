import datetime
import mimetypes
import re
import unicodedata
from urllib.parse import urlparse, parse_qs

import requests
from requests_toolbelt import sessions
from bs4 import BeautifulSoup
from tqdm import tqdm

from constants import BB_BASE_URL, BASE_URL, BB_API_REC_URL

# filename sanitation
from pathvalidate import sanitize_filename


def download_blackboard_lectures(nestor_session: requests.Session, course: dict, folder: str):
    """
    Function for downloading the blackboard lecture videos from a course

    Args:
        nestor_session (requests.Session): Nestor session that is authentication
        course:
        folder:
    """

    # get the token
    token = _get_bbcollab_token(nestor_session, course)

    # TODO: create session with auth headers


    # get the list of videos

    current_date_time = datetime.datetime.now(
    ).astimezone().replace(microsecond=0).isoformat()

    param_data = {'startTime': '2015-01-01T00:00:00+0100', 'endTime': current_date_time,
                  'sort': 'endTime', 'order': 'desc', 'limit': 1000, 'offset': 0}

    lectures = requests.get(BB_API_REC_URL,
                            headers={"Authorization": "Bearer " + token}, params=param_data).json()

    # print lecture job and download amount
    print("[Lectures] " + str(lectures["size"]) + " lectures")

    # download each video and add it to the output html
    for video in lectures["results"]:
        download_video(folder, token, video)


def download_video(folder, token, video):
    """
    Download the specified video to a folder

    Args:
        folder: The folder to download the video to
        token: The auth token for bbcollab
        video: The full json data for the video
    """

    # 1. Get the video link
    response_1 = requests.request("GET", f"{BB_API_REC_URL}/{video['id']}/url",
                                  headers={"Authorization": "Bearer " + token},
                                  params={"validHours": "24", "validMinutes": "59"}).json()
    video_link = response_1["url"]

    # 2. Get the token specific for the video, given by the redirect for the generated video link
    redirect_url = requests.get(video_link, allow_redirects=False).headers['Location']
    url_query = urlparse(redirect_url).query
    video_token = parse_qs(url_query)['authToken'][0]

    # 3. Get direct video url & download
    try:
        response_3 = requests.request("GET", f"{BB_API_REC_URL}/{video['id']}/data/secure",
                                      headers={"Authorization": "Bearer " + video_token})

        # raise exceptions
        response_3.raise_for_status()

        # get direct video url and download it
        response_json = response_3.json()
        file_url = response_json['streams']['WEB']
        _download(file_url, response_json["name"], folder)
    except requests.exceptions.ConnectionError as e:
        # Retry?
        print('Connection Error:', e)

    except requests.exceptions.HTTPError as e:
        message = "ERROR getting video '" + video["name"] + "':"
        if e.response.status_code == 404:
            print(message, e.response.json()['errorMessage'])
        else:
            print(message, e)


def _download(url: str, file_name: str, folder: str):
    """
    Download a file from a direct file url with a nice progress bar

    Args:
        url: Direct link to the file
        file_name: The name of the file
        folder: Folder to save the file to
    """

    # Create a file-safe filename with the correct file extension, based on the mime-type
    name = sanitize_filename(file_name)

    content_type = requests.head(url).headers['content-type']
    extension = mimetypes.guess_extension(content_type)

    file_name = name + extension
    file_temp_name = name + ".part"

    # TODO: check if file already exists, if it does tell user and skip download
    resp = requests.get(url, stream=True)
    total = int(resp.headers.get('content-length', 0))
    # TODO: use file_temp_name instead of file_name
    with open(folder + "/" + file_name, 'wb') as file, tqdm(
            desc="[Lecture video] " + file_name,
            total=total,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
    ) as bar:
        for data in resp.iter_content(chunk_size=1024):
            size = file.write(data)
            bar.update(size)
    # TODO: rename to file_name

# TODO: implement re-auth
# session = requests.Session()
# session.headers.update({"Authorization": f"Bearer deliberate-wrong-token"})
#
# def refresh_token(r, *args, **kwargs):
#     if r.status_code == 401:
#         logger.info("Fetching new token as the previous token expired")
#         token = get_token()
#         session.headers.update({"Authorization": f"Bearer {token}"})
#         r.request.headers["Authorization"] = session.headers["Authorization"]
#         return session.send(r.request, verify=False)
#
# session.hooks['response'].append(refresh_token)


def _get_bbcollab_token(nestor: requests.Session, course):
    # get the data needed for the POST request
    response = nestor.get(f"{BASE_URL}/webapps/collab-ultra/tool/collabultra/lti/launch?course_id={course['courseId']}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # grab only the post request form as html
    post_request_form = soup.find('form', {'id': 'bltiLaunchForm'})

    # extract the form details
    form_details = _get_form_details(post_request_form)

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
        BB_BASE_URL + "/lti", data=post_data)

    # debug
    # print("! request url:")
    # print(response_bbcollab_token.request.url)

    # url with token as a parameter
    url = response_bbcollab_token.request.url
    # extract token from query parameters
    query = urlparse(url).query
    token = parse_qs(query)['token'][0]

    return token


def _get_form_details(form):
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
