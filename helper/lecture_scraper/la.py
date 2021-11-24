from urllib.parse import urljoin

from bs4 import BeautifulSoup as bs

from helper.lecture_scraper.helpers import check_wrapper, other_event


def la_check(url: str, online_soup: bs, local_soup: bs):
    """
    compares online_soup to local_soup
    specifically for LinAl website
    """

    # LECTURES
    sel_path_lec = "table:nth-of-type(1) > tr:not(:first-child)"

    def decode_lec(tr):
        """
        Returns a dict with the changes or None if theres's no matching lecture updates.
        """
        tds = tr.select("td")
        if len(tds) < 3:
            return
        a = tds[2].select_one("a")
        return {
            "date": tds[0].text.strip(),
            "name": f"Kapitel {tds[1].text.strip()}",
            "links": [{
                "text": "notes",
                "url": urljoin(url, a.attrs["href"])
            }] if a else []
        }

    events = check_wrapper(online_soup, local_soup, sel_path_lec, decode_lec, "lecture")
    
    # LECTURES
    sel_path_ex = "table:nth-of-type(2) > tr:not(:first-child)"

    def decode_ex(tr):
        tds = tr.select("td")
        links = [{
            "text": a.text.strip(),
            "url": urljoin(url, a.attrs["href"])
        } for a in tr.select("a")]
        return {
            "name": tds[1].text.strip(),
            "date": tds[0].text.strip(),
            "abgabe_date": tds[4].text.strip(),
            "links": links
        }

    events += check_wrapper(online_soup, local_soup, sel_path_ex, decode_ex, "exercise")

    return events if events else [other_event()]
