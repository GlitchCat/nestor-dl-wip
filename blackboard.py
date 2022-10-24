import datetime
import mimetypes
import os.path
from urllib.parse import urlparse, parse_qs

import requests
# from requests_toolbelt import sessions
import httpx
from bs4 import BeautifulSoup
from tqdm import tqdm

from constants import BB_BASE_URL, BASE_URL, BB_API_REC_PATH, REQ_NUM_RETRIES, REQ_TIMEOUT

# filename sanitation
from pathvalidate import sanitize_filename


# Auth

# TODO: idea, maybe make super class for Bearer Auth and pass a function for getting the new token
# E.g: https://python-patterns.guide/gang-of-four/composition-over-inheritance/#solution-4-beyond-the-gang-of-four-patterns

class BearerAuth(httpx.Auth):
    def __init__(self, get_token_func):
        self.get_token = get_token_func
        pass


class BlackboardAuth(httpx.Auth):
    def __init__(self, nestor_session: requests.Session, course: dict):
        """

        Args:
            nestor_session: The nestor session, used for refreshing the auth automatically
            course: The course for which to generate the auth token
        """
        # TODO: change course to courseId, with str as type. Only the id used for auth currently
        self.nestor = nestor_session
        self.course = course
        self.bearer_token = self.new_bearer_token()

    def auth_flow(self, request):
        request.headers['Authorization'] = self.bearer_token
        response = yield request

        if response.status_code == 401:
            # If the server issues a 401 response then resend the request,
            # with a new auth token.
            self.bearer_token = self.new_bearer_token()
            request.headers['Authorization'] = self.bearer_token
            yield request

    def new_bearer_token(self):
        """ Get a (new) bearer token """
        token = self._get_bbcollab_token()

        return f"Bearer {token}"

    def _get_bbcollab_token(self):
        """ Get a blackboard auth token from nestor """
        course_id = self.course['courseId']
        nestor = self.nestor

        # get the data needed for the POST request
        response = nestor.get(
            f"{BASE_URL}/webapps/collab-ultra/tool/collabultra/lti/launch?course_id={course_id}")

        # Parse the nestor html and grab only the post request form html code from it
        post_request_form = BeautifulSoup(response.text, 'html.parser').find('form', {'id': 'bltiLaunchForm'})

        # extract the form details & data for the post request
        form_details = _get_form_details(post_request_form)
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

        # perform the POST request with the form data manually, to get the bbcollab token for this course
        response_bbcollab_token = requests.post(
            BB_BASE_URL + "/lti", data=post_data)

        # url with token as a parameter
        url = response_bbcollab_token.request.url
        # extract token from query parameters
        query = urlparse(url).query
        token = parse_qs(query)['token'][0]

        return token


def download_blackboard_lectures(nestor_session: requests.Session, course: dict, folder: str):
    """
    Function for downloading the blackboard lecture videos from a course

    Args:
        nestor_session (requests.Session): Nestor session that is authentication
        course:
        folder:
    """

    # Init httpx client with retries on timeout & automatic (re)auth
    transport = httpx.HTTPTransport(retries=REQ_NUM_RETRIES)
    bb_auth = BlackboardAuth(nestor_session, course)
    blackboard = httpx.Client(base_url=BB_BASE_URL, transport=transport, auth=bb_auth, timeout=REQ_TIMEOUT)

    # 1. Get the list of lecture videos

    current_date_time = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()

    param_data = {'startTime': '2015-01-01T00:00:00+0100', 'endTime': current_date_time,
                  'sort': 'endTime', 'order': 'desc', 'limit': 1000, 'offset': 0}

    lectures = blackboard.get(url=BB_API_REC_PATH, params=param_data).json()

    # print lecture job and amount of lectures
    print(f"[Lectures] {str(lectures['size'])} lecture(s)")

    # download each video and add it to the output html
    for video in lectures["results"]:
        download_video(folder, video, blackboard)


def download_video(folder, video, blackboard):
    """
    Download the specified video to a folder

    Args:
        folder: The folder to download the video to
        video: The full json data for the video
        blackboard: The authenticated client session for the blackboard api
    """

    # 1. Get the video link
    response_1 = blackboard.get(url=f"{BB_API_REC_PATH}{video['id']}/url",
                                params={"validHours": "24", "validMinutes": "59"}).json()
    video_link = response_1["url"]

    # Setup session
    bb_vid = httpx.Client(transport=httpx.HTTPTransport(retries=REQ_NUM_RETRIES), timeout=REQ_TIMEOUT)

    # 2. Get the token specific for the video, given by the redirect for the generated video link
    # TODO: implement auth class / use blackboard client for reauth
    redirect_url = bb_vid.get(video_link).headers['Location']
    url_query = urlparse(redirect_url).query
    video_token = parse_qs(url_query)['authToken'][0]

    # 3. Get direct video url & download

    # TODO: auth
    response_3 = bb_vid.get(f"{BB_BASE_URL}{BB_API_REC_PATH}{video['id']}/data/secure",
                            headers={"Authorization": "Bearer " + video_token})

    # raise exceptions
    response_3.raise_for_status()

    # get direct video url and download it
    response_json = response_3.json()
    file_url = response_json['streams']['WEB']
    # Append the id to the video name, so each video name is unique (otherwise videos might be skipped)
    video_unique_name = f"{response_json['name']} - {video['id']}"
    _download(file_url, video_unique_name, folder)


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

    # Final filename + path (renamed to when finished downloading, to prevent finished file redownload)
    file_name = name + extension
    path_final = folder + "/" + file_name
    # temp file name + path (used while downloading)
    path_temp = folder + "/" + file_name + ".part"

    if os.path.exists(path_final):
        # File already exists
        print(f"[Lecture video] '{file_name}' skipping, already downloaded")
    else:
        try:
            # Setup client for retry / timeout behaviour
            video = httpx.Client(transport=httpx.HTTPTransport(retries=REQ_NUM_RETRIES), timeout=REQ_TIMEOUT)

            with open(path_temp, 'wb') as file:
                with video.stream("GET", url) as resp:
                    total = int(resp.headers["Content-Length"])

                    with tqdm(
                            desc="[Lecture video] " + file_name,
                            total=total,
                            unit_scale=True,
                            unit_divisor=1024,
                            unit="iB"
                    ) as progress:
                        num_bytes_downloaded = resp.num_bytes_downloaded
                        for chunk in resp.iter_bytes():
                            file.write(chunk)
                            progress.update(resp.num_bytes_downloaded - num_bytes_downloaded)
                            num_bytes_downloaded = resp.num_bytes_downloaded
                # Raise exceptions
                resp.raise_for_status()
            # Rename file if successfully finished without any exceptions
            os.rename(path_temp, path_final)
        except httpx.HTTPError as exc:
            # FIXME: [ERROR peer closed connection without sending complete message body (received 10152234 bytes, expected 194611756)] while downloading Lecture  Tutorial - recording_2.mp4
            print(f"[ERROR] '{exc}' while downloading '{file_name}'")


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
