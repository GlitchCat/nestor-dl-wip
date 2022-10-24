import string

import requests

from constants import BASE_URL, OUTPUT_DIR


# TODO: rewrite html gen

def content_item_attachments_template(attachments):
    """
    Generates the html for the attachments page
    Args:
        attachments: Attachments, with a name and a (local file) link

    Returns:
    partial HTML
    """
    with open('./html/content_item_attachments.html', 'r') as file:
        template = file.read().replace('\n', '')
        links_html = ""
        for attachment in attachments:
            links_html += content_item_attachment_template(attachment)
        template = template.replace('[ITEMS]', links_html)
        return template


def content_item_attachment_template(attachment):
    """
    Individual attachments, for the for loop
    """

    name = attachment['name']
    link = attachment['link']

    with open('./html/content_item_attachment.html', 'r') as file:
        template = file.read().replace('\n', '')
        template = template.replace('[LINK]', link)
        template = template.replace('[NAME]', name)
        return template


def content_area_template(title, course, links, items, dir_level):
    """Main html page base template"""
    with open('./html/content_area.html', 'r') as file:
        # Remove newlines from html
        template = file.read().replace('\n', '')

        # Add title and course title
        template = template.replace('[TITLE]', title)
        template = template.replace('[COURSE]', course['courseTitle'])

        # Add links to template
        links_html = ""
        for link in links:
            links_html += content_area_link_template(link)
        template = template.replace('[LINKS]', links_html)

        # ??? Add items?
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


def save_css(session: requests.Session):
    """
    Download & store the CSS from nestor
    Args:
        session: An authenticated nestor session
    """
    theme_css = session.get(f"{BASE_URL}/branding/themes/StudentPortalv3800.200609/theme.css").content
    with open(OUTPUT_DIR + "/theme.css", "wb") as f:
        f.write(theme_css)

    shared_css = session.get(f"{BASE_URL}/common/shared.css").content
    with open(OUTPUT_DIR + "/shared.css", "wb") as f:
        f.write(shared_css)
