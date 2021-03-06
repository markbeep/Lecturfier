import requests
from bs4 import BeautifulSoup as bs
from helper.lecture_scraper.dm import dm_check
from helper.lecture_scraper.ep import ep_check
from helper.lecture_scraper.ad import ad_check
from helper.lecture_scraper.la import la_check

class Lecture:
    """Lecture Scraper

    :name: Full lecture name
    :short: Lecture name abbreviation
    :url: url of lecture website
    :check_fn: scraping function specific to url
    """
    def __init__(self, full_name: str, short: str, url: str, check):
        self.name = full_name
        self.url = url
        self.html_path = f'websites/{short}.html'
        open(self.html_path, 'a').close()  # creates file if not existing
        self.check_fn = check

    def scrape_for_events(self):
        """
        :return: [dict]: [{
            "event": "edit" or "new" or "other"
            "type": "exercise" or "lecture"
                only if event != "other"
            "new_entries": exercise or lecture dicts
                only if event == "new"
            "edited_entries": {
                "old_version": exercise or lecture dict
                "new_version": exercise or lecture dict
                "edited_keys": list of keys which are different in above dicts
            }
                only if event == "edit"
        }]
        """
        response = requests.get(self.url, headers={'User-Agent': 'Custom'})

        with open(self.html_path, "rb") as f:
            file_html = f.read()
        changes = response.content != file_html
        if changes:
            # make soups
            #  echt
            online_s = bs(response.content, "html.parser")
            local_s = bs(file_html, "html.parser")
            # test
            # print("found change:", self.name)
            # local_s = bs(response.content, "html.parser")
            # online_s = bs(file_html, "html.parser")
            # update local
            with open(self.html_path, "wb") as f:
                f.write(response.content)

            # go to Lecture specific check and return dict
            return self.check_fn(self.url, online_s, local_s)
        else:
            return []


if __name__ == "__main__":
    dm_url = "https://crypto.ethz.ch/teaching/DM20/"
    ad_url = "https://www.cadmo.ethz.ch/education/lectures/HS20/DA/index.html"
    ep_url = "https://www.lst.inf.ethz.ch/education/einfuehrung-in-die-programmierung-i--252-0027-.html"
    la_url = "https://igl.ethz.ch/teaching/linear-algebra/la2020/"
    lectures = {
        "DM": Lecture("Discrete Mathematics", "dm", dm_url, dm_check),
        "AD": Lecture("Algorithms and Data Structures", "ad", ad_url, ad_check),
        "EP": Lecture("Introduction to Programming", "ep", ep_url, ep_check),
        "LA": Lecture("Linear Algebra", "la", la_url, la_check),
    }
    for key in lectures:
        print(lectures[key].scrape_for_events())


def scraper():
    dm_url = "https://crypto.ethz.ch/teaching/DM20/"
    ad_url = "https://www.cadmo.ethz.ch/education/lectures/HS20/DA/index.html"
    ep_url = "https://www.lst.inf.ethz.ch/education/einfuehrung-in-die-programmierung-i--252-0027-.html"
    la_url = "https://igl.ethz.ch/teaching/linear-algebra/la2020/"
    changes = {}
    lesson_links = {}
    lectures = {
        "DM": Lecture("Discrete Mathematics", "dm", dm_url, dm_check),
        "AD": Lecture("Algorithms and Data Structures", "ad", ad_url, ad_check),
        "EP": Lecture("Introduction to Programming", "ep", ep_url, ep_check),
        "LA": Lecture("Linear Algebra", "la", la_url, la_check),
    }
    for key in lectures:
        changes[lectures[key].name] = lectures[key].scrape_for_events()
        lesson_links[lectures[key].name] = lectures[key].url
    return changes, lesson_links


if __name__ == '__main__':
    print(scraper())